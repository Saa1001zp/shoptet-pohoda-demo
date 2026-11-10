"""Generate 10 synthetic supplier invoice PDFs.

Eight are machine-readable and postable, one is an image-only scan and one is
an exact duplicate of invoice DF-2026-1003. The duplicate and the scan are
intentionally left for manual review by the scenario.
"""

from __future__ import annotations

import random
import shutil
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ..config import DEMO_SUPPLIERS, SEED, input_root
from ..models import CatalogItem, InvoiceLine, SupplierInvoice
from ..util import ean13, ensure_dir, money, vat_amount, write_json, write_text

INVOICE_CATALOG: list[CatalogItem] = [
    CatalogItem(sku="SUP-001", ean=ean13(2001), name="Demo kancelársky papier A4", unit="bal", price=Decimal("129.90"), vat_rate=Decimal("23"), stock=300),
    CatalogItem(sku="SUP-002", ean=ean13(2002), name="Demo USB-C kábel 2 m", unit="ks", price=Decimal("189.00"), vat_rate=Decimal("23"), stock=200),
    CatalogItem(sku="SUP-003", ean=ean13(2003), name="Demo bezdrôtová myš", unit="ks", price=Decimal("249.00"), vat_rate=Decimal("23"), stock=150),
    CatalogItem(sku="SUP-004", ean=ean13(2004), name="Demo monitor 27\"", unit="ks", price=Decimal("3990.00"), vat_rate=Decimal("23"), stock=40),
    CatalogItem(sku="SUP-005", ean=ean13(2005), name="Demo zápisník A5", unit="ks", price=Decimal("69.00"), vat_rate=Decimal("23"), stock=500),
    CatalogItem(sku="SUP-006", ean=ean13(2006), name="Demo klávesnica SK", unit="ks", price=Decimal("749.00"), vat_rate=Decimal("23"), stock=90),
    CatalogItem(sku="SUP-007", ean=ean13(2007), name="Demo reproduktor", unit="ks", price=Decimal("459.00"), vat_rate=Decimal("23"), stock=80),
    CatalogItem(sku="SUP-008", ean=ean13(2008), name="Demo podložka na stôl", unit="ks", price=Decimal("119.00"), vat_rate=Decimal("23"), stock=220),
    CatalogItem(sku="SUP-009", ean=ean13(2009), name="Demo webkamera Full HD", unit="ks", price=Decimal("2290.00"), vat_rate=Decimal("23"), stock=55),
    CatalogItem(sku="SUP-010", ean=ean13(2010), name="Demo stojan na monitor", unit="ks", price=Decimal("690.00"), vat_rate=Decimal("23"), stock=110),
    CatalogItem(sku="SUP-011", ean=ean13(2011), name="Demo odborná kniha", unit="ks", price=Decimal("399.00"), vat_rate=Decimal("0"), stock=70),
    CatalogItem(sku="SUP-012", ean=ean13(2012), name="Demo školiaci manuál", unit="ks", price=Decimal("149.00"), vat_rate=Decimal("0"), stock=130),
    CatalogItem(sku="SUP-013", ean=ean13(2013), name="Demo čistič obrazovky", unit="ks", price=Decimal("89.00"), vat_rate=Decimal("0"), stock=160),
    CatalogItem(sku="SUP-014", ean=ean13(2014), name="Demo antistatická podložka", unit="ks", price=Decimal("259.00"), vat_rate=Decimal("0"), stock=65),
]


def _line(no: int, catalog: CatalogItem, qty: int, price: Decimal | None = None) -> InvoiceLine:
    return InvoiceLine(
        line_no=no,
        sku=catalog.sku,
        ean=catalog.ean,
        description=catalog.name,
        qty=qty,
        unit_price=price if price is not None else catalog.price,
        vat_rate=catalog.vat_rate,
    )


def _invoice_total(lines: list[InvoiceLine]) -> Decimal:
    total = Decimal("0.00")
    for line in lines:
        net = money(line.unit_price * line.qty)
        total += net + vat_amount(net, line.vat_rate)
    return money(total)


def _build_invoices() -> list[SupplierInvoice]:
    invoices: list[SupplierInvoice] = []
    start = date(2026, 10, 20)
    for idx in range(1, 11):
        if idx == 9:
            # Image-only scan. The data exists only inside the picture.
            lines = [_line(n + 1, INVOICE_CATALOG[n], 1 + n % 3) for n in range(6)]
        elif idx == 5:
            lines = [_line(n + 1, INVOICE_CATALOG[n], 1 + n % 4) for n in range(6)]
            # The supplier SKU is absent from our catalog, but the EAN is known.
            lines[1] = lines[1].model_copy(update={"sku": "SUP-999", "description": "Demo externý produkt"})
        elif idx == 6:
            lines = [_line(n + 1, INVOICE_CATALOG[n], 1 + n % 3) for n in range(6)]
            # Supplier invoice price is authoritative; the catalog price differs.
            lines[0] = lines[0].model_copy(update={"unit_price": money(lines[0].unit_price + Decimal("5.00"))})
        elif idx == 7:
            # Mixed 23% and 0% VAT on one invoice.
            lines = [
                _line(1, INVOICE_CATALOG[0], 2),
                _line(2, INVOICE_CATALOG[1], 3),
                _line(3, INVOICE_CATALOG[2], 1),
                _line(4, INVOICE_CATALOG[10], 2),
                _line(5, INVOICE_CATALOG[11], 4),
                _line(6, INVOICE_CATALOG[12], 3),
            ]
        else:
            # Only the first ten catalog items (all 23 %) are used here, so
            # exactly one demo invoice (07) is the mixed 0 % / 23 % case.
            offset = (idx - 1) * 6
            lines = [_line(n + 1, INVOICE_CATALOG[(offset + n) % 10], 1 + (n + idx) % 4) for n in range(6)]

        invoice = SupplierInvoice(
            invoice_number=f"DF-2026-{1000 + idx}",
            supplier=DEMO_SUPPLIERS[(idx - 1) % len(DEMO_SUPPLIERS)],
            issue_date=start + timedelta(days=idx * 2),
            due_date=start + timedelta(days=idx * 2 + 14),
            currency="CZK",
            lines=lines,
            total=_invoice_total(lines),
        )
        invoices.append(invoice)
    return invoices


# ---------- PDF rendering -------------------------------------------------

_FONT_CACHE: dict[str, str] = {}


def _font_path(bold: bool = False) -> str:
    key = "bold" if bold else "regular"
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            _FONT_CACHE[key] = candidate
            return candidate
    _FONT_CACHE[key] = "Helvetica-Bold" if bold else "Helvetica"
    return _FONT_CACHE[key]


def _register_fonts() -> tuple[str, str]:
    regular = _font_path(False)
    bold = _font_path(True)
    if regular != "Helvetica" and bold != "Helvetica-Bold":
        pdfmetrics.registerFont(TTFont("DemoSans", regular))
        pdfmetrics.registerFont(TTFont("DemoSans-Bold", bold))
        pdfmetrics.registerFontFamily("DemoSans", normal="DemoSans", bold="DemoSans-Bold")
        return "DemoSans", "DemoSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _safe(text: str, regular: str) -> str:
    if regular != "Helvetica":
        return text
    return text.encode("latin-1", "replace").decode("latin-1")


def _draw_invoice_pdf(path: Path, invoice: SupplierInvoice) -> None:
    regular, bold = _register_fonts()
    canvas_obj = canvas.Canvas(str(path), pagesize=A4, invariant=1, pageCompression=1)
    canvas_obj.setTitle(f"DEMO {invoice.invoice_number}")
    canvas_obj.setAuthor("perepolkin.sk demo")
    canvas_obj.setSubject("Syntetická faktúra – DEMO")
    canvas_obj.setCreator("shoptet-pohoda-demo")
    width, height = A4

    # Small corner watermark. A large diagonal text watermark would be
    # extracted by pdfplumber and would pollute the table text layer.
    canvas_obj.saveState()
    canvas_obj.setFont(bold, 26)
    canvas_obj.setFillColorRGB(0.72, 0.76, 0.84)
    canvas_obj.drawRightString(width - 42, height - 54, "DEMO")
    canvas_obj.restoreState()

    canvas_obj.setFillColorRGB(0.08, 0.10, 0.14)
    canvas_obj.setFont(bold, 17)
    canvas_obj.drawString(42, height - 54, "SYNTETICKÁ FAKTÚRA – DEMO")
    canvas_obj.setFont(regular, 9)
    canvas_obj.setFillColorRGB(0.35, 0.38, 0.44)
    canvas_obj.drawString(42, height - 69, "Nie je reálny doklad. Všetky firmy a osoby sú vymyslené.")
    canvas_obj.setFillColorRGB(0.08, 0.10, 0.14)
    canvas_obj.setFont(bold, 11)
    canvas_obj.drawString(42, height - 100, f"ČÍSLO: {_safe(invoice.invoice_number, regular)}")
    canvas_obj.setFont(regular, 9)
    canvas_obj.drawString(42, height - 116, f"DODÁVATEĽ: {_safe(invoice.supplier, regular)}")
    canvas_obj.drawString(42, height - 131, "Adresa: Demo 1, 110 00 Praha, CZ")
    canvas_obj.drawString(42, height - 146, f"DÁTUM VYSTAVENIA: {invoice.issue_date.isoformat()}")
    canvas_obj.drawString(42, height - 161, f"SPLATNOSŤ: {invoice.due_date.isoformat()}")
    canvas_obj.drawString(42, height - 176, f"MENA: {invoice.currency}")

    canvas_obj.setFont(bold, 10)
    canvas_obj.drawString(42, height - 210, "ODBERATEĽ")
    canvas_obj.setFont(regular, 9)
    canvas_obj.drawString(42, height - 226, "DemoShop s.r.o.")
    canvas_obj.drawString(42, height - 241, "Demo 2, 110 00 Praha, CZ")
    canvas_obj.drawString(42, height - 256, "demo@example.com")

    # Table header
    y = height - 292
    canvas_obj.setFillColorRGB(0.94, 0.95, 0.97)
    canvas_obj.rect(36, y - 6, width - 72, 20, stroke=0, fill=1)
    canvas_obj.setFillColorRGB(0.08, 0.10, 0.14)
    canvas_obj.setFont(bold, 8)
    canvas_obj.drawString(42, y, "POPIS")
    canvas_obj.drawString(225, y, "EAN")
    canvas_obj.drawString(330, y, "SKU")
    canvas_obj.drawRightString(400, y, "QTY")
    canvas_obj.drawRightString(455, y, "CENA")
    canvas_obj.drawRightString(495, y, "DPH")
    canvas_obj.drawRightString(560, y, "CELKOM")

    y -= 24
    canvas_obj.setFont(regular, 8)
    for line in invoice.lines:
        net = money(line.unit_price * line.qty)
        vat = vat_amount(net, line.vat_rate)
        gross = money(net + vat)
        canvas_obj.drawString(42, y, _safe(line.description[:30], regular))
        canvas_obj.drawString(225, y, _safe(line.ean or "", regular))
        canvas_obj.drawString(330, y, _safe(line.sku, regular))
        canvas_obj.drawRightString(400, y, str(line.qty))
        canvas_obj.drawRightString(455, y, f"{line.unit_price:.2f}")
        canvas_obj.drawRightString(495, y, f"{line.vat_rate:g}%")
        canvas_obj.drawRightString(560, y, f"{gross:.2f}")
        y -= 17

    y -= 12
    canvas_obj.setStrokeColorRGB(0.75, 0.78, 0.82)
    canvas_obj.line(36, y, width - 36, y)
    y -= 22
    canvas_obj.setFont(bold, 11)
    canvas_obj.drawRightString(480, y, "CELKOM:")
    canvas_obj.drawRightString(550, y, f"{invoice.total:.2f} {invoice.currency}")

    canvas_obj.setFont(regular, 8)
    canvas_obj.setFillColorRGB(0.35, 0.38, 0.44)
    canvas_obj.drawString(42, 42, "Syntetické dáta pre demo perepolkin.sk. Bez reálneho IČO/DIČ.")
    canvas_obj.drawRightString(width - 42, 42, "DEMO · SYNTETICKÉ DÁTA")
    canvas_obj.showPage()
    canvas_obj.save()


def _draw_scan_pdf(path: Path, invoice: SupplierInvoice) -> None:
    """Image-only, slightly degraded page. pdfplumber must extract no text."""
    rng = random.Random(SEED + 909)
    width, height = 1240, 1754
    image = Image.new("RGB", (width, height), (246, 244, 238))
    draw = ImageDraw.Draw(image)
    font_path = _font_path(False)
    bold_path = _font_path(True)
    try:
        font = ImageFont.truetype(font_path, 26)
        bold = ImageFont.truetype(bold_path, 34)
        small = ImageFont.truetype(font_path, 22)
    except OSError:
        font = bold = small = ImageFont.load_default()

    draw.text((80, 70), "SYNTETICKÁ FAKTÚRA – DEMO", fill=(35, 38, 46), font=bold)
    draw.text((80, 120), f"ČÍSLO: {invoice.invoice_number}", fill=(35, 38, 46), font=font)
    draw.text((80, 160), f"DODÁVATEĽ: {invoice.supplier}", fill=(35, 38, 46), font=font)
    draw.text((80, 200), f"DÁTUM: {invoice.issue_date.isoformat()}", fill=(35, 38, 46), font=font)
    y = 280
    draw.line((80, y, 1160, y), fill=(120, 120, 120), width=2)
    y += 20
    for line in invoice.lines:
        net = money(line.unit_price * line.qty)
        gross = money(net + vat_amount(net, line.vat_rate))
        draw.text((80, y), f"{line.description[:40]}", fill=(40, 42, 48), font=small)
        draw.text((760, y), f"{line.qty} x {line.unit_price:.2f}", fill=(40, 42, 48), font=small)
        draw.text((1020, y), f"{gross:.2f}", fill=(40, 42, 48), font=small)
        y += 38
    draw.line((80, y + 10, 1160, y + 10), fill=(120, 120, 120), width=2)
    draw.text((820, y + 30), f"CELKOM: {invoice.total:.2f} CZK", fill=(35, 38, 46), font=bold)
    draw.text((80, 1650), "Syntetické dáta. DEMO.", fill=(110, 110, 110), font=small)

    # Degrade the "scan": slight rotation, blur, noise and a soft shadow.
    image = image.rotate(-0.7, expand=False, fillcolor=(246, 244, 238))
    image = image.filter(ImageFilter.GaussianBlur(0.55))
    pixels = image.load()
    for _ in range(9000):
        x = rng.randrange(width)
        yy = rng.randrange(height)
        r, g, b = pixels[x, yy]
        delta = rng.randint(-18, 12)
        pixels[x, yy] = (max(0, min(255, r + delta)), max(0, min(255, g + delta)), max(0, min(255, b + delta)))
    canvas_obj = canvas.Canvas(str(path), pagesize=A4, invariant=1, pageCompression=1)
    canvas_obj.setTitle(f"DEMO scan {invoice.invoice_number}")
    canvas_obj.setAuthor("perepolkin.sk demo")
    canvas_obj.setSubject("Syntetická naskenovaná faktúra – DEMO")
    # Pass an ImageReader, not a path: ReportLab derives the PDF object name
    # from the path otherwise, making identical runs differ by temp directory.
    canvas_obj.drawImage(ImageReader(image), 0, 0, width=A4[0], height=A4[1])
    canvas_obj.showPage()
    canvas_obj.save()


def generate(root: Path | None = None) -> dict:
    root = root or input_root() / "invoices"
    ensure_dir(root)
    invoices = _build_invoices()

    manifest = []
    for idx, invoice in enumerate(invoices, start=1):
        if idx == 9:
            filename = "invoice_09_scan.pdf"
            _draw_scan_pdf(root / filename, invoice)
            kind = "scan"
        else:
            filename = f"invoice_{idx:02d}.pdf"
            _draw_invoice_pdf(root / filename, invoice)
            kind = "clean"

        if idx == 10:
            # Exact duplicate of invoice 03, different filename. Detected by
            # invoice number/content, not by the manifest.
            shutil.copyfile(root / "invoice_03.pdf", root / filename)
            kind = "duplicate"
            duplicate_source = invoices[2]
            manifest.append(
                {
                    "file": filename,
                    "kind": kind,
                    "invoice_number": duplicate_source.invoice_number,
                    "supplier": duplicate_source.supplier,
                    "issue_date": duplicate_source.issue_date.isoformat(),
                    "due_date": duplicate_source.due_date.isoformat(),
                    "currency": duplicate_source.currency,
                    "lines": len(duplicate_source.lines),
                    "total": f"{duplicate_source.total:.2f}",
                }
            )
            continue

        manifest.append(
            {
                "file": filename,
                "kind": kind,
                "invoice_number": invoice.invoice_number,
                "supplier": invoice.supplier,
                "issue_date": invoice.issue_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
                "currency": invoice.currency,
                "lines": len(invoice.lines),
                "total": f"{invoice.total:.2f}",
            }
        )

    write_json(root / "manifest.json", manifest)
    write_json(root / "catalog.json", [item.model_dump(mode="json") for item in INVOICE_CATALOG])
    write_text(
        root / "README.txt",
        "Syntetické PDF faktúry pre demo Dodávateľské faktúry → Pohoda.\n"
        "10 PDF: 8 čitateľných, 1 naskenovaná (bez textovej vrstvy), 1 duplikát.\n"
        "Všetky firmy sú vymyslené. Žiadne reálne IČO/DIČ.\n",
    )
    return {"invoices": len(invoices), "lines": sum(len(item.lines) for item in invoices), "path": str(root)}
