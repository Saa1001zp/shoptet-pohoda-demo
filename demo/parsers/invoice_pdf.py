"""Extract and parse synthetic supplier invoice PDFs with pdfplumber.

This is deliberately text extraction, not OCR. An image-only scan therefore
goes to manual review instead of being guessed.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pdfplumber

from ..models import CatalogItem, ParsedInvoice, ParsedInvoiceLine
from ..util import money, vat_amount

HEADER_PATTERNS = {
    "invoice_number": re.compile(r"ČÍSLO:\s*(DF-\d{4}-\d{4})"),
    "supplier": re.compile(r"DODÁVATEĽ:\s*(.+)"),
    "issue_date": re.compile(r"DÁTUM VYSTAVENIA:\s*(\d{4}-\d{2}-\d{2})"),
    "due_date": re.compile(r"SPLATNOSŤ:\s*(\d{4}-\d{2}-\d{2})"),
    "currency": re.compile(r"MENA:\s*([A-Z]{3})"),
    "declared_total": re.compile(r"CELKOM:\s*([0-9 ]+[.,][0-9]{2})\s*(?:CZK|EUR)"),
}

LINE_RE = re.compile(
    r"^(?P<description>.+?)\s+(?P<ean>\d{13})\s+(?P<sku>[A-Z]{2,}-\d{2,})\s+"
    r"(?P<qty>\d+)\s+(?P<price>\d+\.\d{2})\s+(?P<vat>\d+)%\s+(?P<gross>\d+\.\d{2})$",
    re.MULTILINE,
)


def extract_text(path: Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def _parse_header(text: str) -> dict:
    result: dict = {}
    for key, pattern in HEADER_PATTERNS.items():
        match = pattern.search(text)
        result[key] = match.group(1).strip() if match else None
    return result


def _parse_lines(text: str) -> list[dict]:
    rows = []
    for match in LINE_RE.finditer(text):
        rows.append(
            {
                "description": match.group("description").strip(),
                "ean": match.group("ean").strip(),
                "sku": match.group("sku").strip(),
                "qty": int(match.group("qty")),
                "unit_price": Decimal(match.group("price")),
                "vat_rate": Decimal(match.group("vat")),
            }
        )
    return rows


def parse_invoice(
    path: Path,
    by_sku: dict[str, CatalogItem],
    by_ean: dict[str, CatalogItem],
) -> ParsedInvoice:
    text = extract_text(path)
    if not text:
        return ParsedInvoice(
            source_file=path.name,
            status="manual_review",
            reason="scan_requires_ocr",
        )

    header = _parse_header(text)
    if not header.get("invoice_number"):
        return ParsedInvoice(
            source_file=path.name,
            status="manual_review",
            reason="unreadable_header",
        )

    rows = _parse_lines(text)
    if not rows:
        return ParsedInvoice(
            source_file=path.name,
            invoice_number=header.get("invoice_number"),
            supplier=header.get("supplier"),
            status="manual_review",
            reason="no_line_items",
        )

    parsed_lines: list[ParsedInvoiceLine] = []
    for number, row in enumerate(rows, start=1):
        net = money(row["unit_price"] * row["qty"])
        vat = vat_amount(net, row["vat_rate"])
        gross = money(net + vat)

        catalog_item = by_sku.get(row["sku"])
        method = "sku" if catalog_item else None
        note = None
        if catalog_item is None:
            # Supplier SKU can differ from our internal SKU. EAN is the fallback.
            catalog_item = by_ean.get(row.get("ean", ""))
        if catalog_item is not None and method is None:
            method = "ean"
            note = "sku_matched_by_ean"

        parsed_lines.append(
            ParsedInvoiceLine(
                line_no=number,
                sku=row["sku"],
                ean=catalog_item.ean if catalog_item else None,
                description=row["description"],
                qty=row["qty"],
                unit_price=row["unit_price"],
                vat_rate=row["vat_rate"],
                net=net,
                vat=vat,
                gross=gross,
                catalog_sku=catalog_item.sku if catalog_item else None,
                matched=catalog_item is not None,
                match_method=method,
                note=note,
            )
        )

    computed_total = money(sum((line.gross for line in parsed_lines), Decimal("0.00")))
    declared_total = None
    if header.get("declared_total"):
        declared_total = money(header["declared_total"].replace(" ", "").replace(",", "."))

    return ParsedInvoice(
        source_file=path.name,
        invoice_number=header.get("invoice_number"),
        supplier=header.get("supplier"),
        issue_date=_parse_date(header.get("issue_date")),
        due_date=_parse_date(header.get("due_date")),
        currency=header.get("currency"),
        declared_total=declared_total,
        lines=parsed_lines,
        computed_total=computed_total,
        status="parsed",
    )
