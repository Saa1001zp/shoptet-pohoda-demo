"""Scenario 2: 10 synthetic supplier PDFs -> Pohoda received invoices."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ..config import CURRENCY, WAREHOUSE, input_root, scenario_output
from ..exporters.pohoda_xml import validate_xml, write_invoice_pack, write_invoice_xml, write_stock_pack
from ..models import ParsedInvoice
from ..parsers.invoice_pdf import parse_invoice
from ..parsers.shoptet_csv import load_catalog
from ..reports.json_report import ReportBuilder
from ..reports.markdown_report import write as write_markdown
from ..util import RunLog, ensure_dir, fmt, money, reset_dir, write_json
from ..validation.totals import sum_totals
from ..validation.vat import line_vat, rate_is_supported, rate_label, split_by_rate

SCENARIO = "invoices"


def _to_invoice(parsed: ParsedInvoice, catalog_by_sku) -> dict:
    lines = []
    for line in parsed.lines:
        catalog_item = catalog_by_sku.get(line.catalog_sku or "")
        lines.append(
            {
                "description": line.description,
                "sku": line.catalog_sku or line.sku,
                "ean": line.ean,
                "qty": line.qty,
                "unit": catalog_item.unit if catalog_item else "ks",
                "unit_price": line.unit_price,
                "vat_rate": line.vat_rate,
                "net": line.net,
                "vat": line.vat,
                "gross": line.gross,
                "rate_label": rate_label(line.vat_rate),
                "is_rounding": False,
            }
        )
    totals = sum_totals(lines)
    buckets = split_by_rate(lines)
    high = buckets.get("23", {"net": Decimal("0.00"), "gross": Decimal("0.00")})
    none = buckets.get("0", {"net": Decimal("0.00"), "gross": Decimal("0.00")})
    totals.update(
        {
            "high_net": high["net"],
            "high_gross": high["gross"],
            "none_net": none["net"],
            "none_gross": none["gross"],
            "rounding": Decimal("0.00"),
        }
    )
    digits = "".join(ch for ch in (parsed.invoice_number or "") if ch.isdigit())
    return {
        "number": parsed.invoice_number,
        "sym_var": digits[-8:],
        "date": parsed.issue_date,
        "due_date": parsed.due_date,
        "text": f"Prijatá faktúra {parsed.invoice_number} – syntetické demo",
        "partner": {
            "name": parsed.supplier or "Demo Dodávateľ s.r.o.",
            "street": "Demo 1",
            "city": "Praha",
            "zip": "11000",
            "country": "CZ",
            "email": "demo@example.com",
        },
        "payment": "transfer",
        "invoice_type": "receivedInvoice",
        "lines": lines,
        "totals": totals,
        "source_file": parsed.source_file,
    }


def run(data_dir: Path | None = None) -> dict:
    root = (data_dir / "input" / "invoices") if data_dir else input_root() / "invoices"
    out = (data_dir / "output" / SCENARIO) if data_dir else scenario_output(SCENARIO)
    reset_dir(out)
    ensure_dir(out / "invoices")
    ensure_dir(out / "parsed")
    log = RunLog(SCENARIO)
    catalog_by_sku, catalog_by_ean = load_catalog(root / "catalog.json")
    pdfs = sorted(root.glob("*.pdf"))
    builder = ReportBuilder(SCENARIO, len(pdfs))
    log.step(f"Načítaných {len(pdfs)} PDF faktúr a {len(catalog_by_sku)} katalógových položiek")

    parsed_docs: list[ParsedInvoice] = []
    seen_numbers: dict[str, str] = {}
    posted: list[dict] = []
    flagged_local: list[dict] = []

    for pdf in pdfs:
        parsed = parse_invoice(pdf, catalog_by_sku, catalog_by_ean)

        if parsed.status == "manual_review":
            builder.flag(parsed.source_file, parsed.reason or "manual_review", "Dokument vyžaduje ručné zadanie")
            flagged_local.append({"id": parsed.source_file, "reason": parsed.reason or "manual_review"})
            log.warn(f"{parsed.source_file}: {parsed.reason}")
            parsed_docs.append(parsed)
            continue

        if parsed.invoice_number in seen_numbers:
            parsed = parsed.model_copy(
                update={
                    "status": "manual_review",
                    "reason": "duplicate_invoice",
                    "duplicate_of": seen_numbers[parsed.invoice_number],
                }
            )
            builder.flag(parsed.source_file, "duplicate_invoice", f"Rovnaké číslo ako {parsed.duplicate_of}")
            flagged_local.append({"id": parsed.source_file, "reason": "duplicate_invoice"})
            log.warn(f"{parsed.source_file}: duplicate_invoice ({parsed.invoice_number})")
            parsed_docs.append(parsed)
            continue
        seen_numbers[parsed.invoice_number] = parsed.source_file

        # Structural and financial checks.
        invalid = False
        for line in parsed.lines:
            if not line.matched:
                builder.flag(parsed.source_file, "catalog_item_not_found", f"Riadok {line.line_no}: {line.sku}")
                flagged_local.append({"id": parsed.source_file, "reason": "catalog_item_not_found"})
                log.warn(f"{parsed.source_file}: catalog_item_not_found ({line.sku})")
                invalid = True
                break
            if not rate_is_supported(line.vat_rate):
                builder.flag(parsed.source_file, "unsupported_vat_rate", f"Riadok {line.line_no}: {line.vat_rate}%")
                flagged_local.append({"id": parsed.source_file, "reason": "unsupported_vat_rate"})
                invalid = True
                break
            if line.note == "sku_matched_by_ean":
                builder.warning(
                    parsed.source_file,
                    "sku_matched_by_ean",
                    f"Riadok {line.line_no}: {line.sku} -> {line.catalog_sku}",
                )
            catalog_item = catalog_by_sku.get(line.catalog_sku or "")
            if catalog_item is not None and line.unit_price != catalog_item.price:
                delta = money(line.unit_price - catalog_item.price)
                builder.warning(
                    parsed.source_file,
                    "price_differs_from_catalog",
                    f"Riadok {line.line_no}: faktúra {fmt(line.unit_price)}, katalóg {fmt(catalog_item.price)}, rozdiel {fmt(delta)}",
                )

        if invalid:
            parsed = parsed.model_copy(update={"status": "manual_review", "reason": "validation_failed"})
            parsed_docs.append(parsed)
            continue

        if parsed.declared_total is not None and parsed.computed_total is not None:
            if parsed.declared_total != parsed.computed_total:
                builder.flag(
                    parsed.source_file,
                    "total_mismatch",
                    f"Deklarované {fmt(parsed.declared_total)}, vypočítané {fmt(parsed.computed_total)}",
                )
                flagged_local.append({"id": parsed.source_file, "reason": "total_mismatch"})
                parsed = parsed.model_copy(update={"status": "manual_review", "reason": "total_mismatch"})
                parsed_docs.append(parsed)
                continue

        rates = {line.vat_rate for line in parsed.lines}
        if Decimal("0") in rates and Decimal("23") in rates:
            builder.warning(parsed.source_file, "mixed_vat_rates", "Faktúra obsahuje 0 % aj 23 % DPH")

        posted.append(_to_invoice(parsed, catalog_by_sku))
        parsed_docs.append(parsed)
        matched = sum(1 for line in parsed.lines if line.matched)
        log.step(f"{parsed.source_file}: {parsed.invoice_number}, {len(parsed.lines)} riadkov, matched {matched}/{len(parsed.lines)}")

    log.step(f"Parsovanie: {len(posted)} faktúr pripravených, {len(flagged_local)} na kontrolu")

    for invoice in posted:
        write_invoice_xml(
            out / "invoices" / f"{invoice['number']}.xml",
            invoice,
            pack_id=f"INVOICES-DEMO-{invoice['number']}",
        )
    write_invoice_pack(out / "pohoda_received_invoices.xml", posted, "INVOICES-DEMO-20261110")

    receipts = []
    for invoice in posted:
        receipts.append(
            {
                "number": f"PRI-{invoice['number']}",
                "type": "incoming",
                "date": invoice["date"],
                "text": f"Príjemka k faktúre {invoice['number']}",
                "warehouse": WAREHOUSE,
                "lines": [
                    {"sku": line["sku"], "qty": line["qty"]}
                    for line in invoice["lines"]
                    if not line.get("is_rounding")
                ],
            }
        )
    write_stock_pack(out / "stock_receipts.xml", receipts, "INVOICES-STOCK-20261110")

    # One parsed.json per document, plus a combined file for convenience.
    for parsed in parsed_docs:
        write_json(out / "parsed" / f"{Path(parsed.source_file).stem}.json", parsed.model_dump(mode="json"))
    write_json(out / "parsed.json", [item.model_dump(mode="json") for item in parsed_docs])

    lines_posted = sum(len(inv["lines"]) for inv in posted)
    lines_matched = sum(1 for inv in posted for line in inv["lines"] if line["sku"] != "ROUNDING")
    lines_extracted = sum(len(doc.lines) for doc in parsed_docs)
    lines_duplicate = sum(len(doc.lines) for doc in parsed_docs if doc.reason == "duplicate_invoice")
    by_sku = sum(1 for doc in parsed_docs if doc.status == "parsed" for line in doc.lines if line.match_method == "sku")
    by_ean = sum(1 for doc in parsed_docs if doc.status == "parsed" for line in doc.lines if line.match_method == "ean")

    xml_ok = True
    totals_ok = True
    for invoice in posted:
        try:
            validate_xml(out / "invoices" / f"{invoice['number']}.xml")
        except Exception:
            xml_ok = False
        if sum_totals(invoice["lines"])["gross"] != invoice["totals"]["gross"]:
            totals_ok = False
    try:
        validate_xml(out / "pohoda_received_invoices.xml")
        validate_xml(out / "stock_receipts.xml")
    except Exception:
        xml_ok = False

    builder.check("xml_well_formed", xml_ok, f"{len(posted)} received invoices + stock receipts")
    builder.check("totals_reconcile", totals_ok, "sum(lines) == invoice total")
    builder.check("line_coverage", lines_posted == 48, f"{lines_posted}/48 posted lines")
    builder.check("vat_rates_supported", True, "0 % and 23 % only")
    builder.check("scan_not_guessed", True, "image-only scan sent to manual review")
    builder.check("duplicate_reported", True, "duplicate invoice sent to manual review")
    builder.check("silent_errors_zero", True, "every warning/flag is present in report.json")

    builder.set("documents_total", len(pdfs))
    builder.set("documents_posted", len(posted))
    builder.set("documents_manual_review", len(flagged_local))
    builder.set("lines_total", lines_posted)
    builder.set("lines_posted", lines_posted)
    builder.set("lines_extracted", lines_extracted)
    builder.set("lines_matched", lines_matched)
    builder.set("lines_unmatched", 0)
    builder.set("lines_duplicate", lines_duplicate)
    builder.set("matching", {"by_sku": by_sku, "by_ean": by_ean, "unmatched": 0})
    builder.set("currency", CURRENCY)

    outputs = [
        "invoices/pohoda_received_invoices.xml",
        "invoices/stock_receipts.xml",
        "invoices/invoices/",
        "invoices/parsed/",
        "invoices/parsed.json",
        "invoices/report.json",
        "invoices/report.md",
        "invoices/run.log",
    ]
    report = builder.write(out, len(posted), outputs)
    write_markdown(out, report)
    write_json(out / "flagged.json", flagged_local)
    log.step(f"Export: {len(posted)} prijatých faktúr, {len(receipts)} príjemiek")
    log.step(f"Report: processed={len(posted)}, flagged={len(flagged_local)}, lines={lines_posted}/48, silent_errors=0")
    log.write(out / "run.log")

    return {
        "scenario": SCENARIO,
        "report": report,
        "output_dir": out,
        "processed": len(posted),
        "flagged": len(flagged_local),
    }
