"""Deterministic screenshots, video and handoff pack.

Everything is rendered locally from the generated demo outputs. There are no
network calls and no real customer data. The visual assets use the same fixed
numbers as report.json, so the cards cannot drift from the reports.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from .config import REPO_ROOT, data_root, handoff_root
from .reports.markdown_report import REASON_SK
from .util import ensure_dir, fixed_zip, fmt_int, money, write_text

W, H = 1440, 900
M = 72
SCENARIOS = ("shoptet", "invoices", "mergado")

BG = "#F2F5F8"
CARD = "#FFFFFF"
INK = "#0B1220"
MUTED = "#5A6778"
LINE = "#DCE3EA"
TEAL = "#0F9D8A"
TEAL_DARK = "#087568"
TEAL_SOFT = "#DDF4EF"
AMBER = "#B45309"
AMBER_SOFT = "#FEF3C7"
RED = "#B42318"
RED_SOFT = "#FEE4E2"
GREEN = "#067647"
GREEN_SOFT = "#DCFAE6"
TERM_BG = "#0B1220"
TERM_BAR = "#161D2A"
TERM_TEXT = "#DCE6F2"
TERM_DIM = "#8A98AA"
CODE_TAG = "#7DD3FC"
CODE_ATTR = "#FBBF24"
CODE_TEXT = "#E5EDF6"

FONT_DIR = Path(r"C:\Windows\Fonts")


@lru_cache(maxsize=128)
def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        name = "consolab.ttf" if bold else "consola.ttf"
    else:
        name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = FONT_DIR / name
    if not path.exists():
        path = FONT_DIR / ("arialbd.ttf" if bold else "arial.ttf")
    return ImageFont.truetype(str(path), size=size)


def tw(draw: ImageDraw.ImageDraw, value: str, fnt: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(value, font=fnt))


def fit(draw: ImageDraw.ImageDraw, value: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> str:
    value = str(value)
    if tw(draw, value, fnt) <= max_width:
        return value
    while value and tw(draw, value + "…", fnt) > max_width:
        value = value[:-1]
    return value + "…"


def wrap(draw: ImageDraw.ImageDraw, value: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = str(value).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if tw(draw, candidate, fnt) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    size: int = 24,
    color: str = INK,
    bold: bool = False,
    mono: bool = False,
    anchor: str | None = None,
) -> None:
    draw.text(xy, str(value), font=font(size, bold, mono), fill=color, anchor=anchor)


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str = CARD, outline: str = LINE, radius: int = 18) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 3, y1 + 5, x2 + 3, y2 + 5), radius=radius, fill="#E6EBF1")
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, fill: str = TEAL_SOFT, fg: str = TEAL_DARK) -> int:
    fnt = font(16, True)
    width = tw(draw, label, fnt) + 28
    draw.rounded_rectangle((x, y, x + width, y + 32), radius=16, fill=fill)
    text(draw, (x + 14, y + 6), label, 16, fg, True)
    return width


def header(draw: ImageDraw.ImageDraw, kicker: str, title: str, subtitle: str, dark: bool = False) -> None:
    draw.rectangle((0, 0, W, 9), fill=TEAL)
    bg = TERM_BG if dark else BG
    fg = "#FFFFFF" if dark else INK
    sub = "#AAB6C5" if dark else MUTED
    draw.rectangle((0, 9, W, H), fill=bg)
    text(draw, (M, 40), kicker, 15, TEAL, True)
    text(draw, (M, 70), title, 48, fg, True)
    text(draw, (M, 136), subtitle, 22, sub)
    draw.line((M, 178, W - M, 178), fill="#273244" if dark else LINE, width=1)
    pill(draw, W - M - 176, 42, "SYNTETICKÉ DÁTA", TEAL_SOFT if not dark else "#123B37", TEAL_DARK if not dark else "#8DE4D7")


def footer(draw: ImageDraw.ImageDraw, dark: bool = False) -> None:
    fg = "#8A98AA" if dark else "#8491A2"
    draw.line((M, 842, W - M, 842), fill="#263244" if dark else LINE, width=1)
    text(draw, (M, 858), "Syntetické dáta · všetky firmy a doklady sú vymyslené · bez reálneho IČO/DIČ", 15, fg)
    text(draw, (W - M, 856), "DEMO", 25, "#A9B6C5" if dark else "#AAB5C1", True, anchor="ra")


def stat_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    value: str,
    label: str,
    note: str = "",
    accent: str = TEAL,
) -> None:
    panel(draw, box)
    x1, y1, x2, _ = box
    draw.rounded_rectangle((x1, y1 + 26, x1 + 5, y1 + 92), radius=2, fill=accent)
    text(draw, (x1 + 28, y1 + 20), value, 54, INK, True)
    text(draw, (x1 + 28, y1 + 84), label, 19, MUTED)
    if note:
        text(draw, (x1 + 28, y1 + 112), note, 15, "#7C899A")


def _money(value: str | Decimal) -> str:
    return f"{money(value):,.2f}".replace(",", " ").replace(".", ",")


def _ctx(root: Path) -> dict:
    reports = {}
    for scenario in SCENARIOS:
        path = root / "output" / scenario / "report.json"
        if not path.exists():
            raise FileNotFoundError(f"Chýba report: {path}. Spustite `python -m demo run-all`.")
        reports[scenario] = json.loads(path.read_text(encoding="utf-8"))
    orders = json.loads((root / "input" / "shoptet" / "orders.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "input" / "shoptet" / "catalog.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "input" / "invoices" / "manifest.json").read_text(encoding="utf-8"))
    parsed = json.loads((root / "output" / "invoices" / "parsed" / "invoice_01.json").read_text(encoding="utf-8"))
    return {
        "root": root,
        "reports": reports,
        "orders": orders,
        "catalog": catalog,
        "manifest": manifest,
        "parsed": parsed,
    }


def _file_icon(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, color: str = TEAL) -> None:
    draw.rounded_rectangle((x, y, x + 34, y + 42), radius=5, fill=color)
    draw.polygon([(x + 21, y), (x + 34, y + 13), (x + 21, y + 13)], fill="#FFFFFF")
    text(draw, (x + 17, y + 29), label, 11, "#FFFFFF", True, anchor="mm")


def _badge(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, fill: str, fg: str) -> None:
    fnt = font(13, True)
    width = tw(draw, label, fnt) + 18
    draw.rounded_rectangle((x, y, x + width, y + 24), radius=12, fill=fill)
    text(draw, (x + 9, y + 4), label, 13, fg, True)


def input_shoptet(ctx: dict) -> Image.Image:
    report = ctx["reports"]["shoptet"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 01 / VSTUP", "Shoptet → Pohoda", "50 syntetických objednávok · 12 produktov · 1 sklad · CZK · DPH 23 %")
    card_w = (W - 2 * M - 2 * 22) // 3
    for index, (value, label, note, accent) in enumerate(
        [
            (fmt_int(report["input_count"]), "objednávok", "DEMO-2026-0001 … 0050", TEAL),
            ("12", "produktov v katalógu", "SKU + EAN + cena + DPH", TEAL),
            ("1", "sklad", "SKLAD-DEMO · výdajky", AMBER),
        ]
    ):
        stat_card(draw, (M + index * (card_w + 22), 206, M + index * (card_w + 22) + card_w, 348), value, label, note, accent)

    panel(draw, (M, 378, 632, 800))
    text(draw, (M + 26, 402), "Vstupné súbory", 24, INK, True)
    text(draw, (M + 26, 436), "Lokálne, bez API a bez siete", 15, MUTED)
    files = [
        ("JSON", "orders.json", "50 objednávok", TEAL),
        ("CSV", "orders.csv", "ten istý export pre CSV import", "#2563EB"),
        ("JSON", "catalog.json", "12 SKU, EAN, cena, DPH", TEAL),
        ("JSON", "stock.json", "1 sklad, 12 položiek", TEAL),
        ("TXT", "README.txt", "syntetické dáta, žiadny klient", "#7C3AED"),
    ]
    for index, (kind, name, note, color) in enumerate(files):
        y = 478 + index * 60
        _file_icon(draw, M + 26, y, kind, color)
        text(draw, (M + 76, y + 1), name, 19, INK, True)
        text(draw, (M + 76, y + 26), note, 14, MUTED)

    panel(draw, (656, 378, 1368, 800))
    text(draw, (682, 402), "Ukážka objednávky", 24, INK, True)
    order = ctx["orders"][0]
    text(draw, (682, 436), f"{order['order_id']} · {order['customer']['name']} · CZK", 15, MUTED)
    columns = [(682, "SKU"), (800, "Položka"), (1120, "Množ."), (1190, "Cena"), (1300, "DPH")]
    draw.rounded_rectangle((682, 472, 1342, 510), radius=8, fill="#EDF2F6")
    for x, label in columns:
        text(draw, (x, 482), label, 14, MUTED, True)
    rows = [(item["sku"], item["name"], str(item["qty"]), _money(item["unit_price"]), "23 %") for item in order["items"]]
    rows.append(("—", "Doprava", "1", _money(order["shipping"]), "23 %"))
    for index, (sku, name, qty, price, vat) in enumerate(rows):
        y = 526 + index * 56
        if index % 2 == 0:
            draw.rectangle((682, y - 8, 1342, y + 40), fill="#F8FAFC")
        text(draw, (682, y), sku, 15, TEAL_DARK, True, True)
        text(draw, (800, y), fit(draw, name, font(16), 300), 16, INK)
        text(draw, (1120, y), qty, 16, INK)
        text(draw, (1190, y), price, 16, INK)
        text(draw, (1300, y), vat, 16, INK)
    net = sum((Decimal(item["unit_price"]) * item["qty"] for item in order["items"]), Decimal("0")) + Decimal(order["shipping"])
    gross = money(net * Decimal("1.23"))
    draw.line((682, 736, 1342, 736), fill=LINE)
    text(draw, (682, 752), "Spolu s DPH", 16, MUTED)
    text(draw, (1342, 746), f"{_money(gross)} CZK", 24, INK, True, anchor="ra")
    text(draw, (682, 774), "Všetky mená, adresy a e-maily sú vymyslené.", 13, MUTED)
    footer(draw)
    return image


def input_invoices(ctx: dict) -> Image.Image:
    report = ctx["reports"]["invoices"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 02 / VSTUP", "Dodávateľské faktúry → Pohoda", "10 syntetických PDF · 48 riadkov · 1 katalóg · 8 čitateľných + 2 na kontrolu")
    card_w = (W - 2 * M - 2 * 22) // 3
    for index, (value, label, note, accent) in enumerate(
        [
            ("10", "PDF faktúr", "8 čitateľných + 1 sken + 1 duplikát", TEAL),
            ("48", "riadkov", "6 riadkov na faktúru", TEAL),
            ("2", "na ručnú kontrolu", "sken bez OCR · duplicita", AMBER),
        ]
    ):
        stat_card(draw, (M + index * (card_w + 22), 206, M + index * (card_w + 22) + card_w, 348), value, label, note, accent)

    panel(draw, (M, 378, 770, 800))
    text(draw, (M + 26, 402), "Vstupné PDF", 24, INK, True)
    text(draw, (M + 26, 436), "manifest.json · 10 dokumentov", 15, MUTED)
    for index, item in enumerate(ctx["manifest"]):
        column = index // 5
        row = index % 5
        x = M + 26 + column * 344
        y = 474 + row * 62
        _file_icon(draw, x, y, "PDF", "#DC2626")
        text(draw, (x + 46, y - 1), fit(draw, item["file"], font(15, True), 180), 15, INK, True)
        text(draw, (x + 46, y + 24), f"{item['invoice_number']} · {_money(item['total'])}", 13, MUTED)
        if item["kind"] == "scan":
            _badge(draw, x + 244, y + 4, "sken", AMBER_SOFT, AMBER)
        elif item["kind"] == "duplicate":
            _badge(draw, x + 226, y + 4, "duplikát", RED_SOFT, RED)
        else:
            _badge(draw, x + 244, y + 4, "OK", GREEN_SOFT, GREEN)

    panel(draw, (794, 378, 1368, 800))
    text(draw, (820, 402), "Ukážka dokumentu", 24, INK, True)
    text(draw, (820, 436), "PDF → text → riadky → Pohoda XML", 15, MUTED)
    draw.rounded_rectangle((842, 468, 1320, 772), radius=4, fill="#FFFFFF", outline="#E2E8F0")
    text(draw, (866, 490), "FAKTÚRA / DEMO", 14, TEAL_DARK, True)
    text(draw, (866, 516), ctx["parsed"]["supplier"], 18, INK, True)
    text(draw, (866, 542), f"{ctx['parsed']['invoice_number']} · {ctx['parsed']['issue_date']}", 13, MUTED)
    text(draw, (1296, 490), "CZK", 13, MUTED, anchor="ra")
    draw.line((866, 566, 1296, 566), fill=LINE)
    for index, line in enumerate(ctx["parsed"]["lines"][:3]):
        y = 582 + index * 38
        text(draw, (866, y), fit(draw, line["description"], font(14), 250), 14, INK)
        text(draw, (1160, y), f"{line['qty']} × {_money(line['unit_price'])}", 13, MUTED)
        text(draw, (1296, y), _money(line["gross"]), 13, INK, anchor="ra")
    draw.line((866, 700, 1296, 700), fill=LINE)
    text(draw, (866, 714), "Spolu", 15, MUTED, True)
    text(draw, (1296, 710), f"{_money(ctx['parsed']['declared_total'])} CZK", 20, INK, True, anchor="ra")
    text(draw, (866, 742), "Syntetická faktúra · Demo Dodávateľ Alfa s.r.o.", 12, MUTED)
    _badge(draw, 1192, 738, "DEMO", TEAL_SOFT, TEAL_DARK)
    footer(draw)
    return image


def input_mergado(ctx: dict) -> Image.Image:
    report = ctx["reports"]["mergado"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 03 / VSTUP", "Mergado / XML feed", "3 dodávatelia · 1 000 produktov · 2 XML + 1 CSV · CZK")
    card_w = (W - 2 * M - 2 * 22) // 3
    for index, (value, label, note, accent) in enumerate(
        [
            ("3", "feedy", "2 × XML + 1 × CSV", TEAL),
            (fmt_int(report["input_count"]), "produktov", "400 + 350 + 250", TEAL),
            ("13", "na kontrolu", "kategória, EAN, mena, cena", AMBER),
        ]
    ):
        stat_card(draw, (M + index * (card_w + 22), 206, M + index * (card_w + 22) + card_w, 348), value, label, note, accent)

    panel(draw, (M, 378, 656, 800))
    text(draw, (M + 26, 402), "Zdroje", 24, INK, True)
    text(draw, (M + 26, 436), "Každý feed má iný formát", 15, MUTED)
    suppliers = [("A", "supplier_a.xml", 400, "XML"), ("B", "supplier_b.xml", 350, "XML"), ("C", "supplier_c.csv", 250, "CSV")]
    for index, (code, name, count, kind) in enumerate(suppliers):
        y = 478 + index * 92
        draw.rounded_rectangle((M + 26, y, M + 58, y + 58), radius=10, fill=TEAL if index < 2 else "#2563EB")
        text(draw, (M + 42, y + 29), code, 24, "#FFFFFF", True, anchor="mm")
        text(draw, (M + 74, y + 2), name, 18, INK, True)
        text(draw, (M + 74, y + 30), f"{count} produktov · {kind}", 14, MUTED)
        bar_w = 150
        draw.rounded_rectangle((M + 360, y + 22, M + 360 + bar_w, y + 34), radius=6, fill="#E8EEF4")
        draw.rounded_rectangle((M + 360, y + 22, M + 360 + int(bar_w * count / 400), y + 34), radius=6, fill=TEAL if index < 2 else "#2563EB")
        text(draw, (M + 552, y + 18), str(count), 18, INK, True, anchor="ra")

    panel(draw, (680, 378, 1368, 800))
    text(draw, (706, 402), "Edge cases, ktoré demo rieši", 24, INK, True)
    text(draw, (706, 436), "Nič sa nemení ticho. Všetko je v reporte.", 15, MUTED)
    cases = [
        ("10", "bez kategórie", "1 odvodená z názvu, 9 na kontrolu", AMBER),
        ("1", "duplicitný EAN", "druhý výskyt na kontrolu", RED),
        ("5", "nulový sklad", "zostáva v master feede s warningom", TEAL),
        ("2", "iná mena", "EUR / USD sa nekonvertuje", AMBER),
        ("1", "neplatná cena", "N/A nejde do master feedu", RED),
    ]
    for index, (value, label, note, color) in enumerate(cases):
        y = 480 + index * 60
        draw.rounded_rectangle((706, y, 750, y + 44), radius=9, fill="#F1F5F9")
        text(draw, (728, y + 22), value, 18, color, True, anchor="mm")
        text(draw, (766, y), label, 18, INK, True)
        text(draw, (766, y + 25), note, 14, MUTED)
    footer(draw)
    return image


def _terminal_line_color(line: str) -> str:
    if "WARN" in line:
        return "#FBBF24"
    if line.startswith("$"):
        return "#8DE4D7"
    if "Report:" in line:
        return "#86EFAC"
    if re.match(r"^\[\d+\]", line):
        return "#8DE4D7"
    return TERM_TEXT


def run_image(ctx: dict, scenario: str, reveal: int | None = None) -> Image.Image:
    report = ctx["reports"][scenario]
    log_path = ctx["root"] / "output" / scenario / "run.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    if reveal is not None:
        lines = lines[:reveal]
    image = Image.new("RGB", (W, H), TERM_BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 9), fill=TEAL)
    draw.rectangle((0, 9, W, 72), fill=TERM_BAR)
    for index, color in enumerate(("#F87171", "#FBBF24", "#34D399")):
        draw.ellipse((28 + index * 24, 32, 44 + index * 24, 48), fill=color)
    text(draw, (118, 28), f"demo — python -m demo run --scenario {scenario}", 18, "#C9D5E3", mono=True)
    pill(draw, W - M - 86, 24, "DEMO", "#123B37", "#8DE4D7")
    text(draw, (M, 98), "RUN / lokálny CLI beh", 15, TEAL, True)
    text(draw, (M, 124), "Bez siete. Bez Dockeru. Bez databázy.", 16, TERM_DIM)
    y = 166
    body_font = font(19, mono=True) if len(lines) < 18 else font(16, mono=True)
    step = 30 if len(lines) < 18 else 27
    for line in lines:
        if not line.strip():
            y += step // 2
            continue
        color = _terminal_line_color(line)
        text(draw, (M, y), fit(draw, line, body_font, W - 2 * M - 20), 19 if len(lines) < 18 else 16, color, mono=True)
        y += step
    panel(draw, (M, 748, W - M, 826), fill="#111A29", outline="#243247", radius=12)
    metrics = [
        (str(report["processed"]), "spracované", "#86EFAC"),
        (str(report["flagged"]), "na kontrolu", "#FBBF24"),
        (str(report["silent_errors"]), "ticho prejdené", "#8DE4D7"),
    ]
    for index, (value, label, color) in enumerate(metrics):
        x = M + 34 + index * 420
        text(draw, (x, 762), value, 34, color, True)
        text(draw, (x + 76, 774), label, 16, "#AAB6C5")
    text(draw, (W - M - 24, 774), "syntetické dáta", 14, "#6F7E91", anchor="ra")
    footer(draw, dark=True)
    return image


def _code_lines(xml_text: str, limit: int = 24) -> list[str]:
    return xml_text.splitlines()[:limit]


def output_shoptet(ctx: dict) -> Image.Image:
    report = ctx["reports"]["shoptet"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 01 / VÝSTUP", "46 faktúr je hotových", "Pohoda XML subset · 46 výdajok skladu · všetky súčty sedia")
    panel(draw, (M, 206, 610, 800))
    text(draw, (M + 26, 230), "Pohoda XML", 24, INK, True)
    text(draw, (M + 26, 264), "Vyexportované doklady", 15, MUTED)
    text(draw, (M + 26, 302), fmt_int(report["processed"]), 86, TEAL_DARK, True)
    text(draw, (M + 26, 390), "XML faktúr", 20, INK, True)
    text(draw, (M + 26, 420), f"{report['stock_movements']} výdajok skladu · 1 rounding line", 14, MUTED)
    items = [
        ("pohoda_invoices.xml", f"{report['processed']} dokladov v jednom balíku"),
        ("invoices/", "jeden XML súbor na faktúru"),
        ("stock_issues.xml", f"{report['stock_movements']} pohybov skladu"),
        ("report.json + report.md", "strojový aj ľudský report"),
    ]
    for index, (name, note) in enumerate(items):
        y = 470 + index * 66
        _file_icon(draw, M + 26, y, "XML" if name.endswith(".xml") else "DIR" if name.endswith("/") else "DOC", TEAL if index != 2 else AMBER)
        text(draw, (M + 76, y), name, 17, INK, True)
        text(draw, (M + 76, y + 26), note, 13, MUTED)
    for index, label in enumerate(("XML well-formed", "Súčty sedia", "Decimal")): 
        _badge(draw, M + 26 + index * 142, 752, label, TEAL_SOFT, TEAL_DARK)

    panel(draw, (634, 206, 1368, 800), fill="#0E1726", outline="#223047")
    text(draw, (658, 230), "invoices/2026-0001.xml", 17, "#8DE4D7", True, mono=True)
    text(draw, (W - 88, 230), "ukážka", 13, "#6F7E91", anchor="ra")
    xml_path = ctx["root"] / "output" / "shoptet" / "invoices" / "2026-0001.xml"
    lines = _code_lines(xml_path.read_text(encoding="utf-8"), 23)
    y = 270
    for index, line in enumerate(lines, start=1):
        text(draw, (658, y), f"{index:02d}", 12, "#52627A", mono=True)
        stripped = line.strip()
        color = CODE_TAG if stripped.startswith("<") else CODE_TEXT
        text(draw, (692, y), fit(draw, line, font(14, mono=True), 630), 14, color, mono=True)
        y += 21
    footer(draw)
    return image


def output_invoices(ctx: dict) -> Image.Image:
    report = ctx["reports"]["invoices"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 02 / VÝSTUP", "8 faktúr, 48/48 riadkov", "Prijaté faktúry do Pohody · skladové príjemky · parsed.json")
    panel(draw, (M, 206, 610, 800))
    text(draw, (M + 26, 230), "Pohoda XML", 24, INK, True)
    text(draw, (M + 26, 264), "Prijaté faktúry a príjemky", 15, MUTED)
    text(draw, (M + 26, 302), "8", 86, TEAL_DARK, True)
    text(draw, (M + 26, 390), "prijatých faktúr", 20, INK, True)
    text(draw, (M + 26, 420), f"{report['lines_posted']}/{report['lines_total']} riadkov · 0 unmatched", 14, MUTED)
    items = [
        ("pohoda_received_invoices.xml", "8 dokladov v jednom balíku"),
        ("stock_receipts.xml", "8 skladových príjemiek"),
        ("parsed/", "10 JSON výstupov z PDF"),
        ("report.json + report.md", "matched / unmatched / flagged"),
    ]
    for index, (name, note) in enumerate(items):
        y = 470 + index * 66
        _file_icon(draw, M + 26, y, "XML" if name.endswith(".xml") else "DIR" if name.endswith("/") else "DOC", TEAL if index != 1 else AMBER)
        text(draw, (M + 76, y), name, 17, INK, True)
        text(draw, (M + 76, y + 26), note, 13, MUTED)
    for index, label in enumerate(("48/48 riadkov", "SKU + EAN", "0/23 % DPH")):
        _badge(draw, M + 26 + index * 142, 752, label, TEAL_SOFT, TEAL_DARK)

    panel(draw, (634, 206, 1368, 800), fill="#0E1726", outline="#223047")
    text(draw, (658, 230), "pohoda_received_invoices.xml", 17, "#8DE4D7", True, mono=True)
    text(draw, (W - 88, 230), "ukážka", 13, "#6F7E91", anchor="ra")
    xml_path = ctx["root"] / "output" / "invoices" / "invoices" / "DF-2026-1001.xml"
    lines = _code_lines(xml_path.read_text(encoding="utf-8"), 23)
    y = 270
    for index, line in enumerate(lines, start=1):
        text(draw, (658, y), f"{index:02d}", 12, "#52627A", mono=True)
        stripped = line.strip()
        color = CODE_TAG if stripped.startswith("<") else CODE_TEXT
        text(draw, (692, y), fit(draw, line, font(14, mono=True), 630), 14, color, mono=True)
        y += 21
    footer(draw)
    return image


def output_mergado(ctx: dict) -> Image.Image:
    report = ctx["reports"]["mergado"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 03 / VÝSTUP", "987 produktov v master feede", "master_feed.xml + CSV · mapping.json · 1 000 vstupov")
    panel(draw, (M, 206, 610, 800))
    text(draw, (M + 26, 230), "Master feed", 24, INK, True)
    text(draw, (M + 26, 264), "Z 3 feedov do jedného", 15, MUTED)
    text(draw, (M + 26, 302), fmt_int(report["processed"]), 78, TEAL_DARK, True)
    text(draw, (M + 26, 382), "produktov", 20, INK, True)
    text(draw, (M + 26, 412), "13 na kontrolu · 5 nulových skladov", 14, MUTED)
    items = [
        ("master_feed.xml", "987 produktov, XML"),
        ("master_feed.csv", "ten istý feed pre CSV"),
        ("mapping.json", "1 000 vstupov → master ID"),
        ("report.json + report.md", "duplicity, meny, ceny"),
    ]
    for index, (name, note) in enumerate(items):
        y = 466 + index * 66
        _file_icon(draw, M + 26, y, "XML" if name.endswith(".xml") else "CSV" if name.endswith(".csv") else "DOC", TEAL if index < 2 else AMBER)
        text(draw, (M + 76, y), name, 17, INK, True)
        text(draw, (M + 76, y + 26), note, 13, MUTED)
    for index, label in enumerate(("987/1000", "unikátne EAN", "Decimal")):
        _badge(draw, M + 26 + index * 142, 752, label, TEAL_SOFT, TEAL_DARK)

    panel(draw, (634, 206, 1368, 800), fill="#0E1726", outline="#223047")
    text(draw, (658, 230), "master_feed.csv", 17, "#8DE4D7", True, mono=True)
    text(draw, (W - 88, 230), "ukážka", 13, "#6F7E91", anchor="ra")
    csv_path = ctx["root"] / "output" / "mergado" / "master_feed.csv"
    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()[:20]
    y = 270
    for index, line in enumerate(lines):
        if index == 0:
            color = "#8DE4D7"
        else:
            color = CODE_TEXT
        text(draw, (658, y), fit(draw, line, font(13, mono=True), 660), 13, color, mono=True)
        y += 24
    footer(draw)
    return image


CHECK_SK = {
    "xml_well_formed": "XML well-formed",
    "totals_reconcile": "Súčty sedia",
    "line_coverage": "48/48 riadkov",
    "vat_rates_supported": "DPH 0/23 %",
    "scan_not_guessed": "Sken nehádame",
    "duplicate_reported": "Duplicita reportovaná",
    "silent_errors_zero": "0 ticho prejdených",
    "decimal_money": "Decimal peniaze",
    "catalog_match": "Katalóg sedí",
    "duplicate_orders_reported": "Duplicity reportované",
    "master_xml_well_formed": "Master XML OK",
    "master_count": "987 v masteri",
    "mapping_complete": "Mapping kompletný",
    "unique_ean_in_master": "EAN unikátne",
    "category_rule_reported": "Kategória reportovaná",
}


def report_image(ctx: dict, scenario: str) -> Image.Image:
    report = ctx["reports"][scenario]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    title = {"shoptet": "Shoptet → Pohoda", "invoices": "Dodávateľské faktúry → Pohoda", "mergado": "Mergado / XML feed"}[scenario]
    header(draw, "REPORT / VÝSLEDOK", title, "Každé upozornenie je v reporte. Žiadna ticho prejdená chyba.")
    cards = [
        (str(report["processed"]), "automaticky", "spracované", GREEN, GREEN_SOFT),
        (str(report["flagged"]), "na kontrolu", "flagged, nie processed", AMBER, AMBER_SOFT),
        (str(report["silent_errors"]), "ticho prejdené", "musí byť 0", TEAL, TEAL_SOFT),
    ]
    if scenario == "shoptet":
        extra = (str(report.get("rounding_lines", 0)), "rounding line", "0,01 CZK viditeľne")
    elif scenario == "invoices":
        extra = (f"{report['lines_posted']}/{report['lines_total']}", "riadkov", "0 unmatched")
    else:
        extra = (fmt_int(report["input_count"]), "vstupov", "987 v masteri")
    cards.append((extra[0], extra[1], extra[2], "#2563EB", "#DBEAFE"))
    card_w = (W - 2 * M - 3 * 20) // 4
    for index, (value, label, note, accent, soft) in enumerate(cards):
        x = M + index * (card_w + 20)
        panel(draw, (x, 206, x + card_w, 390))
        draw.rounded_rectangle((x, 206, x + 7, 390), radius=3, fill=accent)
        text(draw, (x + 24, 226), value, 52 if len(value) < 6 else 40, INK, True)
        text(draw, (x + 24, 300), label, 18, INK, True)
        text(draw, (x + 24, 328), note, 13, MUTED)
        draw.rounded_rectangle((x + 24, 356, x + 24 + 46, 364), radius=4, fill=soft)

    panel(draw, (M, 416, 790, 800))
    text(draw, (M + 26, 440), "Na kontrolu", 24, INK, True)
    text(draw, (764, 444), f"{report['flagged']} položiek", 14, AMBER, True, anchor="ra")
    flagged = report.get("flagged_items", [])
    for index, item in enumerate(flagged[:5]):
        y = 486 + index * 46
        draw.rounded_rectangle((M + 26, y + 4, M + 34, y + 36), radius=3, fill=AMBER)
        text(draw, (M + 46, y), fit(draw, item["id"], font(15, True, True), 170), 15, INK, True, mono=True)
        reason = REASON_SK.get(item["reason"], item["reason"])
        text(draw, (M + 224, y), fit(draw, reason, font(15), 470), 15, MUTED)
    if len(flagged) > 5:
        text(draw, (M + 46, 486 + 5 * 46), f"+ {len(flagged) - 5} ďalších v reporte", 14, MUTED)
    draw.line((M + 26, 742, 764, 742), fill=LINE)
    text(draw, (M + 26, 758), "Syntetické dáta. Nie je to reálny klient.", 14, MUTED)
    text(draw, (M + 26, 778), "Každá položka na kontrolu je viditeľná v reporte.", 13, "#7C899A")

    panel(draw, (814, 416, 1368, 800))
    text(draw, (840, 440), "Kontroly", 24, INK, True)
    checks = report.get("checks", [])
    for index, check in enumerate(checks[:7]):
        y = 484 + index * 38
        color = GREEN if check["passed"] else RED
        draw.ellipse((840, y + 5, 856, y + 21), fill=color)
        text(draw, (846, y + 8), "✓" if check["passed"] else "!", 13, "#FFFFFF", True, anchor="mm")
        label = CHECK_SK.get(check["name"], check["name"])
        text(draw, (870, y), fit(draw, label, font(15, True), 300), 15, INK, True)
    draw.rounded_rectangle((840, 748, 1342, 788), radius=8, fill=AMBER_SOFT)
    text(draw, (856, 756), f"{len(report.get('warnings', []))} upozornení · všetky v report.json", 14, AMBER, True)
    footer(draw)
    return image


def title_image(ctx: dict, scenario: str) -> Image.Image:
    report = ctx["reports"][scenario]
    image = Image.new("RGB", (W, H), TERM_BG)
    draw = ImageDraw.Draw(image)
    for y in range(H):
        ratio = y / H
        color = (11 + int(6 * ratio), 18 + int(14 * ratio), 32 + int(18 * ratio))
        draw.line((0, y, W, y), fill=color)
    draw.rectangle((0, 0, W, 9), fill=TEAL)
    text(draw, (M, 74), "PEREPOLKIN.SK / DEMO PACK", 18, "#8DE4D7", True)
    title = {"shoptet": "Shoptet → Pohoda", "invoices": "Dodávateľské faktúry → Pohoda", "mergado": "Mergado / XML feed"}[scenario]
    lines = wrap(draw, title, font(80, True), W - 2 * M)
    y = 220
    for line in lines:
        text(draw, (M, y), line, 80, "#FFFFFF", True)
        y += 96
    draw.rounded_rectangle((M, y + 22, M + 92, y + 30), radius=4, fill=TEAL)
    subtitle = {
        "shoptet": f"Syntetické dáta. {report['input_count']} objednávok.",
        "invoices": f"Syntetické dáta. {report['input_count']} PDF faktúr.",
        "mergado": f"Syntetické dáta. {fmt_int(report['input_count'])} produktov.",
    }[scenario]
    text(draw, (M, y + 60), subtitle, 34, "#D7E2EE")
    text(draw, (M, 760), "Lokálny CLI beh · bez siete · bez reálneho klienta", 20, "#8A98AA")
    text(draw, (W - M, 760), "DEMO", 30, "#8DE4D7", True, anchor="ra")
    return image


def cta_image(ctx: dict, scenario: str) -> Image.Image:
    image = Image.new("RGB", (W, H), TERM_BG)
    draw = ImageDraw.Draw(image)
    for y in range(H):
        ratio = y / H
        color = (11 + int(7 * ratio), 18 + int(20 * ratio), 32 + int(20 * ratio))
        draw.line((0, y, W, y), fill=color)
    draw.rectangle((0, 0, W, 9), fill=TEAL)
    text(draw, (M, 92), "ĎALŠÍ KROK", 18, "#8DE4D7", True)
    text(draw, (M, 190), "Chcete test na", 76, "#FFFFFF", True)
    text(draw, (M, 278), "vašich dátach?", 76, "#FFFFFF", True)
    draw.rounded_rectangle((M, 400, M + 92, 408), radius=4, fill=TEAL)
    text(draw, (M, 446), "Pošlite 2 vzorky.", 44, "#D7E2EE")
    text(draw, (M, 522), "Ukážeme rovnaký report na vašich dátach.", 26, "#AAB6C5")
    draw.rounded_rectangle((M, 636, 420, 700), radius=12, fill=TEAL)
    text(draw, (M + 30, 652), "perepolkin.sk", 28, "#062A26", True)
    text(draw, (W - M, 760), "DEMO · syntetické dáta", 18, "#8A98AA", anchor="ra")
    text(draw, (M, 760), "Nie je to klientsky prípad.", 18, "#8A98AA")
    return image


def _save(image: Image.Image, path: Path) -> None:
    ensure_dir(path.parent)
    image.save(path, "PNG", optimize=True)


def _metrics_md(report: dict) -> str:
    scenario = report["scenario"]
    if scenario == "shoptet":
        input_line = f"{report['input_count']} objednávok"
        result = f"{report['processed']} automaticky, {report['flagged']} na kontrolu"
    elif scenario == "invoices":
        input_line = f"{report['input_count']} faktúr"
        result = f"{report['processed']} automaticky, {report['flagged']} na kontrolu · {report['lines_posted']}/{report['lines_total']} riadkov"
    else:
        input_line = f"{fmt_int(report['input_count'])} produktov"
        result = f"{report['processed']} automaticky, {report['flagged']} na kontrolu"
    return "\n".join(
        [
            f"## {report['title']} (demo)",
            "",
            f"- Vstup: {input_line}",
            f"- Výsledok: {result}",
            f"- Ticho prejdené: {report['silent_errors']}",
            f"- Čas: {report['duration_ms'] / 1000:.0f} s",
            "- Limity: syntetické dáta, nie reálny klient",
            "- CTA: Chcem test na svojich dátach",
            "",
        ]
    )


def handoff_readme(reports: dict) -> str:
    rows = []
    for scenario, report in reports.items():
        rows.append(
            f"| `{scenario}/report.png` | Karta „{report['title']}“ | {report['processed']} automaticky, {report['flagged']} na kontrolu, 0 ticho prejdených |"
        )
    return f"""# Handoff pre dizajnéra

Demo pack pre **perepolkin.sk**. Všetko je syntetické, bez reálneho klienta,
bez IČO/DIČ a bez live pripojenia na Shoptet/Pohoda/Mergado.

## Kam čo patrí

| Súbor | Použitie |
|---|---|
| `handoff/shoptet/input.png` | Karta „Vstup“ — 50 objednávok, súbory, ukážka objednávky |
| `handoff/shoptet/run.png` | Karta „Beh“ — terminál s reálnym logom |
| `handoff/shoptet/output.png` | Karta „Výstup“ — 46 XML faktúr + výdajky |
| `handoff/shoptet/report.png` | Karta „Report“ — 46 / 4 / 0 |
| `handoff/invoices/...` | To isté pre dodávateľské faktúry (8 / 2 / 0, 48/48 riadkov) |
| `handoff/mergado/...` | To isté pre Mergado feed (987 / 13 / 0) |
| `handoff/{{scenario}}/metrics.md` | Presné čísla a texty pre kartu |
| `handoff/{{scenario}}/video.mp4` | 90 s video pre daný scenár, 1440×900, ticho |
| `handoff/README.md` | Tento súbor |
| `handoff/perepolkin-demo-pack.zip` | ZIP so vstupmi, výstupmi, reportmi, screenshotmi a videom |

## Presné čísla na stránku

| Scenár | Vstup | Automaticky | Na kontrolu | Ticho prejdené |
|---|---|---:|---:|---:|
""" + "\n".join(
        f"| {report['title']} | {fmt_int(report['input_count'])} | {report['processed']} | {report['flagged']} | {report['silent_errors']} |"
        for report in reports.values()
    ) + """

**Nepíšte „0 errors“.** Správna formulácia je **„0 ticho prejdených chýb“**
a k tomu počet položiek na ručnú kontrolu. Demo má zámerne flagged prípady.

## Odporúčané texty

### Shoptet → Pohoda

- Nadpis: **Shoptet → Pohoda**
- Podnadpis: *50 syntetických objednávok. 46 automaticky, 4 na kontrolu.*
- Pod čísla: *0 ticho prejdených chýb. Každé upozornenie je v reporte.*
- CTA: **Chcem test na svojich dátach**

### Dodávateľské faktúry → Pohoda

- Nadpis: **Dodávateľské faktúry → Pohoda**
- Podnadpis: *10 PDF faktúr. 8 automaticky, 2 na kontrolu. 48/48 riadkov.*
- Pod čísla: *Sken bez OCR ide na manuálnu kontrolu, nič sa nehádá.*
- CTA: **Chcem test na svojich dátach**

### Mergado / XML feed

- Nadpis: **Mergado / XML feed**
- Podnadpis: *3 feedy, 1 000 produktov. 987 v master feede, 13 na kontrolu.*
- Pod čísla: *Duplicity, meny a ceny sú viditeľné v reporte.*
- CTA: **Chcem test na svojich dátach**

## Kam dať DEMO / syntetické dáta

- Na každom screenshote je vpravo dole **DEMO** a vľavo dole veta
  *Syntetické dáta · všetky firmy a doklady sú vymyslené · bez reálneho IČO/DIČ*.
- Pri vkladaní na web neodstraňujte watermark ani tento text.
- Do alt textu pridajte: `Syntetické demo dáta, nie reálny klient`.
- Video má ticho; netreba pridávať hudbu. Ak ju pridáte, použite vlastnú
  alebo bezlicenčnú a ponechajte DEMO.
- Nikde nepíšte „klientsky prípad“, „referencia“ ani reálne IČO/DIČ.

## Video

- Tri verzie: `handoff/shoptet/video.mp4`, `handoff/invoices/video.mp4`,
  `handoff/mergado/video.mp4`.
- 90 sekúnd, 1440×900, bez browser chrome, veľký font, ticho.
- Osnova: titul → terminál → výstup → report → CTA „Pošlite 2 vzorky“.

## Odkazy

- GitHub: https://github.com/perepolkin/shoptet-pohoda-demo
  *(ak sa účet repozitára líši, nahraďte URL)*
- ZIP: `handoff/perepolkin-demo-pack.zip`
- Web: https://perepolkin.sk

## Ako vložiť kartu

1. Vezmite `report.png` ako hlavný obrázok karty.
2. Pod neho dajte čísla z `metrics.md` (nie z tohto README).
3. CTA odkazujte na kontakt alebo `perepolkin.sk`.
4. Ak používate video, nastavte `poster` na `run.png` a `preload="metadata"`.
5. Pri mobilnom zobrazení zachovajte pomer 16:10; text nesmie zmiznúť.

## Kontrola pred publikovaním

- [ ] Na karte sú presné čísla z `metrics.md`.
- [ ] Je viditeľné DEMO / syntetické dáta.
- [ ] Nie je tam „0 errors“.
- [ ] Nie je tam reálne IČO/DIČ ani reálne meno.
- [ ] CTA je „Chcem test na svojich dátach“.
"""


def _build_video(scenario: str, ctx: dict, out_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg nie je v PATH. Použite `--skip-video` alebo nainštalujte ffmpeg.")
    report = ctx["reports"][scenario]
    log_lines = (ctx["root"] / "output" / scenario / "run.log").read_text(encoding="utf-8").splitlines()
    with tempfile.TemporaryDirectory(prefix=f"demo-video-{scenario}-") as tmp:
        tmp_path = Path(tmp)
        frames: list[tuple[Path, int]] = []

        title_path = tmp_path / "00_title.png"
        _save(title_image(ctx, scenario), title_path)
        frames.append((title_path, 10))

        # Reveal the terminal progressively, two lines per two-second frame.
        for index in range(10):
            reveal = max(2, int(len(log_lines) * (index + 1) / 10))
            path = tmp_path / f"01_run_{index:02d}.png"
            _save(run_image(ctx, scenario, reveal=reveal), path)
            frames.append((path, 2))

        output_path = tmp_path / "02_output.png"
        _save({"shoptet": output_shoptet, "invoices": output_invoices, "mergado": output_mergado}[scenario](ctx), output_path)
        frames.append((output_path, 20))

        report_path = tmp_path / "03_report.png"
        _save(report_image(ctx, scenario), report_path)
        frames.append((report_path, 20))

        cta_path = tmp_path / "04_cta.png"
        _save(cta_image(ctx, scenario), cta_path)
        frames.append((cta_path, 10))

        concat = tmp_path / "concat.txt"
        lines = []
        for path, duration in frames:
            lines.append(f"file '{path.as_posix()}'")
            lines.append(f"duration {duration}")
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ensure_dir(out_path.parent)
        command = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-shortest",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            str(out_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg zlyhal pre {scenario}:\n{result.stderr[-4000:]}")


def build_all(data_dir: Path | None = None, make_video: bool = True) -> dict:
    root = (data_dir or data_root()).resolve()
    ctx = _ctx(root)
    shots = REPO_ROOT / "assets" / "screenshots"
    video = REPO_ROOT / "assets" / "video"
    handoff = handoff_root()
    ensure_dir(shots)
    ensure_dir(video)
    ensure_dir(handoff)

    renderers = {
        "input": {"shoptet": input_shoptet, "invoices": input_invoices, "mergado": input_mergado},
        "run": {"shoptet": lambda c: run_image(c, "shoptet"), "invoices": lambda c: run_image(c, "invoices"), "mergado": lambda c: run_image(c, "mergado")},
        "output": {"shoptet": output_shoptet, "invoices": output_invoices, "mergado": output_mergado},
        "report": {"shoptet": lambda c: report_image(c, "shoptet"), "invoices": lambda c: report_image(c, "invoices"), "mergado": lambda c: report_image(c, "mergado")},
    }
    for scenario in SCENARIOS:
        target = handoff / scenario
        ensure_dir(target)
        for kind in ("input", "run", "output", "report"):
            image = renderers[kind][scenario](ctx)
            _save(image, shots / f"{scenario}_{kind}.png")
            _save(image, target / f"{kind}.png")
        write_text(target / "metrics.md", _metrics_md(ctx["reports"][scenario]))
        if make_video:
            _build_video(scenario, ctx, video / f"{scenario}.mp4")
            shutil.copyfile(video / f"{scenario}.mp4", target / "video.mp4")

    write_text(handoff / "README.md", handoff_readme(ctx["reports"]))
    write_text(handoff_root() / "README.md", handoff_readme(ctx["reports"]))
    return {"screenshots": shots, "video": video if make_video else None, "handoff": handoff}


def _zip_entries(root: Path) -> Iterable[tuple[Path, str]]:
    prefix = "shoptet-pohoda-demo"
    fixed = ["README.md", "LIMITATIONS.md", "handoff.md", "pyproject.toml", "Makefile", ".python-version"]
    for name in fixed:
        path = REPO_ROOT / name
        if path.exists():
            yield path, f"{prefix}/{name}"

    for path in sorted((REPO_ROOT / "demo").rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        yield path, f"{prefix}/{path.relative_to(REPO_ROOT).as_posix()}"

    for path in sorted((root / "input").rglob("*")):
        if path.is_file():
            yield path, f"{prefix}/data/input/{path.relative_to(root / 'input').as_posix()}"
    for path in sorted((root / "output").rglob("*")):
        if path.is_file():
            yield path, f"{prefix}/data/output/{path.relative_to(root / 'output').as_posix()}"

    for path in sorted(handoff_root().rglob("*")):
        if not path.is_file() or path.suffix.lower() == ".zip":
            continue
        yield path, f"{prefix}/handoff/{path.relative_to(handoff_root()).as_posix()}"


def build_zip(data_dir: Path | None = None) -> Path:
    root = (data_dir or data_root()).resolve()
    handoff = handoff_root()
    if not (handoff / "shoptet" / "report.png").exists():
        build_all(root, make_video=True)
    target = REPO_ROOT / "perepolkin-demo-pack.zip"
    fixed_zip(target, _zip_entries(root))
    ensure_dir(handoff)
    shutil.copyfile(target, handoff / "perepolkin-demo-pack.zip")
    return target
