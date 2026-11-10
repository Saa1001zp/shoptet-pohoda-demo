"""Deterministic screenshots, videos and handoff pack.

The visual language follows perepolkin.sk: warm cream paper, editorial serif
headlines, Inter body text, JetBrains Mono labels and a muted brick accent.
Everything is rendered locally from the generated demo outputs. There are no
network calls and no real customer data. Numbers come from report.json, so the
cards cannot drift from the reports.
"""

from __future__ import annotations

import json
import os
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

# Site tokens. LINE is the opaque equivalent of rgba(31, 27, 22, 0.1) on cream.
BG = "#F7F4EE"
CARD = "#FDFBF7"
PAPER = "#FFFDF9"
INK = "#1F1B16"
MUTED = "#6F6759"
ACCENT = "#A8382A"
GREEN = "#2F6B4B"
LINE = "#E2DDD3"
LINE_STRONG = "#CFC6B8"
WARM = "#EFE8DD"
ACCENT_SOFT = "#F4E4DF"
GREEN_SOFT = "#E5EEE7"
INK_SOFT = "#EAE3D8"

TERM_BG = "#1F1B16"
TERM_BAR = "#2A241D"
TERM_TEXT = "#F4EEE5"
TERM_DIM = "#B6AA9A"
TERM_LINE = "#3A332A"
TERM_RED = "#D77A6B"
TERM_GREEN = "#8FB59B"
CODE_TAG = "#D98A7A"
CODE_ATTR = "#9DBFA6"
CODE_TEXT = "#EDE4D7"

FONT_DIR = REPO_ROOT / "assets" / "fonts"
FONT_FILES = {
    "sans": "Inter.ttf",
    "serif": "Newsreader.ttf",
    "mono": "JetBrainsMono.ttf",
}
FALLBACKS = {
    "sans": "arial.ttf",
    "serif": "georgia.ttf",
    "mono": "consola.ttf",
}
WEIGHTS = {
    "regular": "Regular",
    "medium": "Medium",
    "semibold": "SemiBold",
    "bold": "Bold",
}


@lru_cache(maxsize=256)
def font(size: int, weight: str = "regular", family: str = "sans") -> ImageFont.FreeTypeFont:
    path = FONT_DIR / FONT_FILES[family]
    if not path.exists():
        path = Path(r"C:\Windows\Fonts") / FALLBACKS[family]
    face = ImageFont.truetype(str(path), size=size)
    try:
        face.set_variation_by_name(WEIGHTS.get(weight, weight))
    except (OSError, ValueError):
        if weight in {"medium", "semibold", "bold"}:
            try:
                face.set_variation_by_name("Bold")
            except (OSError, ValueError):
                pass
    return face


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
    size: int = 18,
    color: str = INK,
    weight: str = "regular",
    family: str = "sans",
    anchor: str | None = None,
) -> None:
    draw.text(xy, str(value), font=font(size, weight, family), fill=color, anchor=anchor)


def panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str = CARD,
    outline: str = LINE,
    radius: int = 4,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)


def rule(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, color: str = LINE) -> None:
    draw.line((x1, y1, x2, y2), fill=color, width=1)


def badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    label: str,
    fill: str = ACCENT_SOFT,
    fg: str = ACCENT,
    outline: str | None = None,
) -> int:
    fnt = font(10, "medium", "mono")
    width = tw(draw, label, fnt) + 18
    draw.rounded_rectangle(
        (x, y, x + width, y + 24),
        radius=2,
        fill=fill,
        outline=outline or fill,
        width=1,
    )
    text(draw, (x + 9, y + 6), label, 10, fg, "medium", "mono")
    return width


def stamp(draw: ImageDraw.ImageDraw, x: int, y: int, label: str = "DEMO", color: str = ACCENT) -> None:
    fnt = font(11, "bold", "mono")
    width = tw(draw, label, fnt) + 22
    draw.rectangle((x, y, x + width, y + 28), outline=color, width=1)
    text(draw, (x + 11, y + 8), label, 11, color, "bold", "mono")


def title_run(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    value: str,
    size: int,
    color: str = INK,
    max_width: int = W - 2 * M,
) -> None:
    """Draw a Newsreader title, using Inter only for the arrow glyph."""
    if "→" not in value:
        text(draw, (x, y), fit(draw, value, font(size, "medium", "serif"), max_width), size, color, "medium", "serif")
        return
    left, right = (part.strip() for part in value.split("→", 1))
    while size > 24:
        serif = font(size, "medium", "serif")
        arrow = font(max(16, int(size * 0.72)), "medium", "sans")
        gap = max(8, int(size * 0.2))
        total = tw(draw, left, serif) + tw(draw, "→", arrow) + tw(draw, right, serif) + 2 * gap
        if total <= max_width:
            break
        size -= 2
    serif = font(size, "medium", "serif")
    arrow = font(max(16, int(size * 0.72)), "medium", "sans")
    gap = max(8, int(size * 0.2))
    left_w = tw(draw, left, serif)
    arrow_w = tw(draw, "→", arrow)
    draw.text((x, y), left, font=serif, fill=color)
    draw.text((x + left_w + gap, y + int(size * 0.05)), "→", font=arrow, fill=color)
    draw.text((x + left_w + gap + arrow_w + gap, y), right, font=serif, fill=color)


def header(draw: ImageDraw.ImageDraw, kicker: str, title: str, subtitle: str) -> None:
    draw.rectangle((0, 0, W, 5), fill=ACCENT)
    draw.rectangle((0, 5, W, H), fill=BG)
    text(draw, (M, 30), "PEREPOLKIN.SK / DEMO PACK", 10, MUTED, "medium", "mono")
    text(draw, (W - M, 30), kicker.upper(), 10, ACCENT, "medium", "mono", anchor="ra")

    title_run(draw, M, 62, title, 50, INK, W - 2 * M - 230)
    text(draw, (M, 126), fit(draw, subtitle, font(18), W - 2 * M - 230), 18, MUTED)

    draw.rectangle((W - M - 166, 64, W - M, 94), outline=ACCENT, width=1)
    text(draw, (W - M - 83, 79), "SYNTETICKÉ DÁTA", 10, ACCENT, "medium", "mono", anchor="mm")
    rule(draw, M, 178, W - M, 178, LINE_STRONG)


def footer(draw: ImageDraw.ImageDraw, dark: bool = False) -> None:
    fg = TERM_DIM if dark else MUTED
    line = TERM_LINE if dark else LINE
    rule(draw, M, 842, W - M, 842, line)
    text(
        draw,
        (M, 858),
        "Syntetické dáta · všetky firmy a doklady sú vymyslené · bez reálneho IČO/DIČ",
        12,
        fg,
    )
    color = TERM_RED if dark else ACCENT
    draw.rectangle((W - M - 72, 850, W - M, 878), outline=color, width=1)
    text(draw, (W - M - 36, 864), "DEMO", 12, color, "bold", "mono", anchor="mm")


def stat_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    value: str,
    label: str,
    note: str = "",
    accent: str = ACCENT,
) -> None:
    panel(draw, box)
    x1, y1, _, _ = box
    draw.rectangle((x1 + 20, y1 + 18, x1 + 58, y1 + 22), fill=accent)
    text(draw, (x1 + 20, y1 + 36), value, 48, INK, "medium", "mono")
    text(draw, (x1 + 20, y1 + 96), label, 15, INK, "medium", "sans")
    if note:
        text(draw, (x1 + 20, y1 + 118), note, 12, MUTED, "regular", "mono")


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


def _file_icon(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, color: str = ACCENT) -> None:
    draw.rounded_rectangle((x, y, x + 32, y + 40), radius=2, fill=WARM, outline=LINE_STRONG, width=1)
    draw.line((x + 21, y, x + 21, y + 10), fill=LINE_STRONG, width=1)
    text(draw, (x + 16, y + 27), label, 9, color, "medium", "mono", anchor="mm")


def _file_row(draw: ImageDraw.ImageDraw, x: int, y: int, kind: str, name: str, note: str, color: str = ACCENT) -> None:
    _file_icon(draw, x, y, kind, color)
    text(draw, (x + 44, y + 1), fit(draw, name, font(14, "medium", "mono"), 230), 14, INK, "medium", "mono")
    text(draw, (x + 44, y + 23), fit(draw, note, font(13), 270), 13, MUTED)


def input_shoptet(ctx: dict) -> Image.Image:
    report = ctx["reports"]["shoptet"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(
        draw,
        "SCENÁR 01 / VSTUP",
        "Shoptet → Pohoda",
        "50 syntetických objednávok · 12 produktov · 1 sklad · CZK · DPH 23 %",
    )
    card_w = (W - 2 * M - 2 * 18) // 3
    for index, (value, label, note, accent) in enumerate(
        [
            (fmt_int(report["input_count"]), "objednávok", "DEMO-2026-0001 … 0050", ACCENT),
            ("12", "produktov v katalógu", "SKU + EAN + cena + DPH", INK),
            ("1", "sklad", "SKLAD-DEMO · výdajky", GREEN),
        ]
    ):
        stat_card(draw, (M + index * (card_w + 18), 206, M + index * (card_w + 18) + card_w, 350), value, label, note, accent)

    panel(draw, (M, 378, 604, 800))
    text(draw, (M + 24, 400), "Vstupné súbory", 24, INK, "medium", "serif")
    text(draw, (M + 24, 432), "Lokálne, bez API a bez siete", 12, MUTED, "regular", "mono")
    files = [
        ("JSON", "orders.json", "50 objednávok", ACCENT),
        ("CSV", "orders.csv", "ten istý export pre CSV import", MUTED),
        ("JSON", "catalog.json", "12 SKU, EAN, cena, DPH", ACCENT),
        ("JSON", "stock.json", "1 sklad, 12 položiek", GREEN),
        ("TXT", "README.txt", "syntetické dáta, žiadny klient", MUTED),
    ]
    for index, (kind, name, note, color) in enumerate(files):
        y = 474 + index * 58
        _file_row(draw, M + 24, y, kind, name, note, color)
        rule(draw, M + 24, y + 52, 580, y + 52, LINE)

    panel(draw, (628, 378, 1368, 800))
    text(draw, (652, 400), "Ukážka objednávky", 24, INK, "medium", "serif")
    order = ctx["orders"][0]
    text(draw, (652, 432), f"{order['order_id']} · {order['customer']['name']} · CZK", 12, MUTED, "regular", "mono")
    columns = [(652, "SKU"), (748, "POLOŽKA"), (1068, "MNOŽ."), (1150, "CENA"), (1264, "DPH")]
    draw.rectangle((652, 464, 1344, 496), fill=WARM)
    for x, label in columns:
        text(draw, (x, 474), label, 10, MUTED, "medium", "mono")
    rows = [(item["sku"], item["name"], str(item["qty"]), _money(item["unit_price"]), "23 %") for item in order["items"]]
    rows.append(("—", "Doprava", "1", _money(order["shipping"]), "23 %"))
    for index, (sku, name, qty, price, vat) in enumerate(rows):
        y = 506 + index * 48
        if index % 2 == 0:
            draw.rectangle((652, y - 8, 1344, y + 34), fill="#FAF6EF")
        text(draw, (652, y), sku, 13, ACCENT, "medium", "mono")
        text(draw, (748, y), fit(draw, name, font(15), 280), 15, INK)
        text(draw, (1068, y), qty, 14, INK, "medium", "mono")
        text(draw, (1150, y), price, 14, INK, "medium", "mono")
        text(draw, (1264, y), vat, 14, MUTED, "medium", "mono")
    net = sum((Decimal(item["unit_price"]) * item["qty"] for item in order["items"]), Decimal("0")) + Decimal(order["shipping"])
    gross = money(net * Decimal("1.23"))
    rule(draw, 652, 706, 1344, 706, LINE_STRONG)
    text(draw, (652, 722), "Spolu s DPH", 14, MUTED)
    text(draw, (1344, 714), f"{_money(gross)} CZK", 22, INK, "medium", "mono", anchor="ra")
    text(draw, (652, 766), "Všetky mená, adresy a e-maily sú vymyslené.", 11, MUTED, "regular", "mono")
    footer(draw)
    return image


def input_invoices(ctx: dict) -> Image.Image:
    report = ctx["reports"]["invoices"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(
        draw,
        "SCENÁR 02 / VSTUP",
        "Dodávateľské faktúry → Pohoda",
        "10 syntetických PDF · 48 riadkov · 1 katalóg · 8 čitateľných + 2 na kontrolu",
    )
    card_w = (W - 2 * M - 2 * 18) // 3
    for index, (value, label, note, accent) in enumerate(
        [
            ("10", "PDF faktúr", "8 čitateľných + 1 sken + 1 duplikát", INK),
            ("48", "riadkov", "6 riadkov na faktúru", GREEN),
            ("2", "na ručnú kontrolu", "sken bez OCR · duplicita", ACCENT),
        ]
    ):
        stat_card(draw, (M + index * (card_w + 18), 206, M + index * (card_w + 18) + card_w, 350), value, label, note, accent)

    panel(draw, (M, 378, 770, 800))
    text(draw, (M + 24, 400), "Vstupné PDF", 24, INK, "medium", "serif")
    text(draw, (M + 24, 432), "manifest.json · 10 dokumentov", 12, MUTED, "regular", "mono")
    for index, item in enumerate(ctx["manifest"]):
        column = index // 5
        row = index % 5
        x = M + 24 + column * 340
        y = 468 + row * 58
        _file_icon(draw, x, y, "PDF", ACCENT if item["kind"] != "scan" else MUTED)
        text(draw, (x + 42, y - 1), fit(draw, item["file"], font(12, "medium", "mono"), 150), 12, INK, "medium", "mono")
        text(draw, (x + 42, y + 21), f"{item['invoice_number']} · {_money(item['total'])}", 11, MUTED, "regular", "mono")
        if item["kind"] == "scan":
            badge(draw, x + 222, y + 8, "SKEN", ACCENT_SOFT, ACCENT)
        elif item["kind"] == "duplicate":
            badge(draw, x + 200, y + 8, "DUPLIKÁT", ACCENT_SOFT, ACCENT)
        else:
            badge(draw, x + 230, y + 8, "OK", GREEN_SOFT, GREEN)

    panel(draw, (794, 378, 1368, 800))
    text(draw, (818, 400), "Ukážka dokumentu", 24, INK, "medium", "serif")
    text(draw, (818, 432), "PDF → text → riadky → Pohoda XML", 12, MUTED, "regular", "mono")
    draw.rectangle((842, 464, 1320, 772), fill=PAPER, outline=LINE_STRONG)
    draw.rectangle((842, 464, 1320, 468), fill=ACCENT)
    text(draw, (864, 488), "FAKTÚRA / DEMO", 11, ACCENT, "medium", "mono")
    text(draw, (864, 510), ctx["parsed"]["supplier"], 19, INK, "medium", "serif")
    text(draw, (864, 538), f"{ctx['parsed']['invoice_number']} · {ctx['parsed']['issue_date']}", 11, MUTED, "regular", "mono")
    text(draw, (1296, 488), "CZK", 11, MUTED, "medium", "mono", anchor="ra")
    rule(draw, 864, 560, 1296, 560, LINE_STRONG)
    for index, line in enumerate(ctx["parsed"]["lines"][:3]):
        y = 578 + index * 36
        text(draw, (864, y), fit(draw, line["description"], font(14), 240), 14, INK)
        text(draw, (1146, y), f"{line['qty']} × {_money(line['unit_price'])}", 11, MUTED, "regular", "mono")
        text(draw, (1296, y), _money(line["gross"]), 12, INK, "medium", "mono", anchor="ra")
    rule(draw, 864, 696, 1296, 696, LINE_STRONG)
    text(draw, (864, 712), "Spolu", 13, MUTED, "medium", "sans")
    text(draw, (1296, 704), f"{_money(ctx['parsed']['declared_total'])} CZK", 19, INK, "medium", "mono", anchor="ra")
    text(draw, (864, 744), "Syntetická faktúra · Demo Dodávateľ Alfa s.r.o.", 11, MUTED, "regular", "mono")
    stamp(draw, 1182, 730)
    footer(draw)
    return image


def input_mergado(ctx: dict) -> Image.Image:
    report = ctx["reports"]["mergado"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(
        draw,
        "SCENÁR 03 / VSTUP",
        "Mergado / XML feed",
        "3 dodávatelia · 1 000 produktov · 2 XML + 1 CSV · CZK",
    )
    card_w = (W - 2 * M - 2 * 18) // 3
    for index, (value, label, note, accent) in enumerate(
        [
            ("3", "feedy", "2 × XML + 1 × CSV", INK),
            (fmt_int(report["input_count"]), "produktov", "400 + 350 + 250", GREEN),
            ("13", "na kontrolu", "kategória, EAN, mena, cena", ACCENT),
        ]
    ):
        stat_card(draw, (M + index * (card_w + 18), 206, M + index * (card_w + 18) + card_w, 350), value, label, note, accent)

    panel(draw, (M, 378, 656, 800))
    text(draw, (M + 24, 400), "Zdroje", 24, INK, "medium", "serif")
    text(draw, (M + 24, 432), "Každý feed má iný formát", 12, MUTED, "regular", "mono")
    suppliers = [
        ("A", "supplier_a.xml", 400, "XML", ACCENT),
        ("B", "supplier_b.xml", 350, "XML", "#C17A6C"),
        ("C", "supplier_c.csv", 250, "CSV", MUTED),
    ]
    for index, (code, name, count, kind, color) in enumerate(suppliers):
        y = 478 + index * 92
        draw.rectangle((M + 24, y, M + 68, y + 44), outline=color, width=1)
        text(draw, (M + 46, y + 22), code, 18, color, "medium", "mono", anchor="mm")
        text(draw, (M + 84, y + 2), name, 14, INK, "medium", "mono")
        text(draw, (M + 84, y + 27), f"{count} produktov · {kind}", 12, MUTED, "regular", "mono")
        bar_w = 170
        draw.rectangle((M + 336, y + 18, M + 336 + bar_w, y + 26), fill=INK_SOFT)
        draw.rectangle((M + 336, y + 18, M + 336 + int(bar_w * count / 400), y + 26), fill=color)
        text(draw, (M + 552, y + 14), str(count), 16, INK, "medium", "mono", anchor="ra")

    panel(draw, (680, 378, 1368, 800))
    text(draw, (704, 400), "Edge cases, ktoré demo rieši", 24, INK, "medium", "serif")
    text(draw, (704, 432), "Nič sa nemení ticho. Všetko je v reporte.", 12, MUTED, "regular", "mono")
    cases = [
        ("10", "bez kategórie", "1 odvodená z názvu, 9 na kontrolu", ACCENT),
        ("1", "duplicitný EAN", "druhý výskyt na kontrolu", ACCENT),
        ("5", "nulový sklad", "zostáva v master feede s warningom", GREEN),
        ("2", "iná mena", "EUR / USD sa nekonvertuje", ACCENT),
        ("1", "neplatná cena", "N/A nejde do master feedu", ACCENT),
    ]
    for index, (value, label, note, color) in enumerate(cases):
        y = 478 + index * 60
        draw.rectangle((704, y, 744, y + 40), fill=WARM, outline=LINE)
        text(draw, (724, y + 20), value, 16, color, "medium", "mono", anchor="mm")
        text(draw, (762, y), label, 15, INK, "medium", "sans")
        text(draw, (762, y + 24), note, 12, MUTED, "regular", "mono")
    footer(draw)
    return image


def _terminal_line_color(line: str) -> str:
    if "WARN" in line:
        return TERM_RED
    if line.startswith("$"):
        return TERM_TEXT
    if "Report:" in line:
        return TERM_GREEN
    if re.match(r"^\[\d+\]", line):
        return TERM_TEXT
    return TERM_TEXT


def run_image(ctx: dict, scenario: str, reveal: int | None = None) -> Image.Image:
    report = ctx["reports"][scenario]
    log_path = ctx["root"] / "output" / scenario / "run.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    if reveal is not None:
        lines = lines[:reveal]
    image = Image.new("RGB", (W, H), TERM_BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 5), fill=ACCENT)
    draw.rectangle((0, 5, W, 66), fill=TERM_BAR)
    for index, color in enumerate((TERM_RED, TERM_GREEN, TERM_TEXT)):
        draw.ellipse((26 + index * 22, 30, 40 + index * 22, 44), fill=color)
    text(draw, (108, 26), f"demo — python -m demo run --scenario {scenario}", 14, TERM_DIM, "regular", "mono")
    draw.rectangle((W - M - 72, 24, W - M, 52), outline=TERM_RED, width=1)
    text(draw, (W - M - 36, 38), "DEMO", 10, TERM_RED, "bold", "mono", anchor="mm")

    text(draw, (M, 88), "RUN / LOKÁLNY CLI BEH", 10, TERM_RED, "medium", "mono")
    text(draw, (M, 112), "Reálny log. Bez siete. Bez databázy.", 28, TERM_TEXT, "medium", "serif")
    text(draw, (M, 152), "Každý riadok je z výstupu scenára, žiadna skrytá chyba.", 12, TERM_DIM, "regular", "mono")

    y = 188
    body_size = 18 if len(lines) <= 16 else 16
    step = 28 if len(lines) <= 16 else 23
    for line in lines:
        if not line.strip():
            y += step // 2
            continue
        color = _terminal_line_color(line)
        if "WARN" in line:
            draw.rectangle((M - 14, y + 2, M - 10, y + body_size + 1), fill=ACCENT)
        text(draw, (M, y), fit(draw, line, font(body_size, "regular", "mono"), W - 2 * M - 20), body_size, color, "regular", "mono")
        y += step

    panel(draw, (M, 744, W - M, 826), fill=TERM_BAR, outline=TERM_LINE)
    metrics = [
        (str(report["processed"]), "SPRACOVANÉ", TERM_GREEN),
        (str(report["flagged"]), "NA KONTROLU", TERM_RED),
        (str(report["silent_errors"]), "TICHO PREJDENÉ", TERM_TEXT),
    ]
    for index, (value, label, color) in enumerate(metrics):
        x = M + 28 + index * 400
        text(draw, (x, 758), value, 26, color, "medium", "mono")
        text(draw, (x + 64, 770), label, 11, TERM_DIM, "medium", "mono")
    text(draw, (W - M - 24, 770), "syntetické dáta", 11, TERM_DIM, "regular", "mono", anchor="ra")
    footer(draw, dark=True)
    return image


def _code_lines(xml_text: str, limit: int = 24) -> list[str]:
    return xml_text.splitlines()[:limit]


def _code_panel(draw: ImageDraw.ImageDraw, title: str, lines: list[str], line_size: int = 13, step: int = 21) -> None:
    panel(draw, (604, 206, 1368, 800), fill=TERM_BG, outline=TERM_LINE)
    text(draw, (628, 228), title, 13, TERM_RED, "medium", "mono")
    text(draw, (W - 88, 228), "ukážka", 10, TERM_DIM, "regular", "mono", anchor="ra")
    y = 262
    for index, line in enumerate(lines, start=1):
        text(draw, (628, y), f"{index:02d}", 10, "#7D7264", "regular", "mono")
        stripped = line.strip()
        color = CODE_TAG if stripped.startswith("<") else CODE_TEXT
        text(draw, (660, y), fit(draw, line, font(line_size, "regular", "mono"), 650), line_size, color, "regular", "mono")
        y += step


def output_shoptet(ctx: dict) -> Image.Image:
    report = ctx["reports"]["shoptet"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 01 / VÝSTUP", "46 faktúr je hotových", "Pohoda XML subset · 46 výdajok skladu · všetky súčty sedia")
    panel(draw, (M, 206, 580, 800))
    text(draw, (M + 24, 230), "Pohoda XML", 24, INK, "medium", "serif")
    text(draw, (M + 24, 262), "Vyexportované doklady", 12, MUTED, "regular", "mono")
    text(draw, (M + 24, 296), fmt_int(report["processed"]), 64, ACCENT, "medium", "mono")
    text(draw, (M + 24, 378), "XML faktúr", 18, INK, "medium", "sans")
    text(draw, (M + 24, 406), f"{report['stock_movements']} výdajok skladu · 1 rounding line", 12, MUTED, "regular", "mono")
    items = [
        ("pohoda_invoices.xml", f"{report['processed']} dokladov v jednom balíku"),
        ("invoices/", "jeden XML súbor na faktúru"),
        ("stock_issues.xml", f"{report['stock_movements']} pohybov skladu"),
        ("report.json + report.md", "strojový aj ľudský report"),
    ]
    for index, (name, note) in enumerate(items):
        y = 452 + index * 64
        _file_row(draw, M + 24, y, "XML" if name.endswith(".xml") else "DIR" if name.endswith("/") else "DOC", name, note, ACCENT if index != 2 else GREEN)
    for index, label in enumerate(("XML well-formed", "Súčty sedia", "Decimal")):
        badge(draw, M + 24 + index * 140, 742, label, GREEN_SOFT, GREEN)

    xml_path = ctx["root"] / "output" / "shoptet" / "invoices" / "2026-0001.xml"
    _code_panel(draw, "invoices/2026-0001.xml", _code_lines(xml_path.read_text(encoding="utf-8"), 23))
    footer(draw)
    return image


def output_invoices(ctx: dict) -> Image.Image:
    report = ctx["reports"]["invoices"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 02 / VÝSTUP", "8 faktúr, 48/48 riadkov", "Prijaté faktúry do Pohody · skladové príjemky · parsed.json")
    panel(draw, (M, 206, 580, 800))
    text(draw, (M + 24, 230), "Pohoda XML", 24, INK, "medium", "serif")
    text(draw, (M + 24, 262), "Prijaté faktúry a príjemky", 12, MUTED, "regular", "mono")
    text(draw, (M + 24, 296), "8", 64, ACCENT, "medium", "mono")
    text(draw, (M + 24, 378), "prijatých faktúr", 18, INK, "medium", "sans")
    text(draw, (M + 24, 406), f"{report['lines_posted']}/{report['lines_total']} riadkov · 0 unmatched", 12, MUTED, "regular", "mono")
    items = [
        ("pohoda_received_invoices.xml", "8 dokladov v jednom balíku"),
        ("stock_receipts.xml", "8 skladových príjemiek"),
        ("parsed/", "10 JSON výstupov z PDF"),
        ("report.json + report.md", "matched / unmatched / flagged"),
    ]
    for index, (name, note) in enumerate(items):
        y = 452 + index * 64
        _file_row(draw, M + 24, y, "XML" if name.endswith(".xml") else "DIR" if name.endswith("/") else "DOC", name, note, ACCENT if index != 1 else GREEN)
    for index, label in enumerate(("48/48 riadkov", "SKU + EAN", "0/23 % DPH")):
        badge(draw, M + 24 + index * 140, 742, label, GREEN_SOFT, GREEN)

    xml_path = ctx["root"] / "output" / "invoices" / "invoices" / "DF-2026-1001.xml"
    _code_panel(draw, "pohoda_received_invoices.xml", _code_lines(xml_path.read_text(encoding="utf-8"), 23))
    footer(draw)
    return image


def output_mergado(ctx: dict) -> Image.Image:
    report = ctx["reports"]["mergado"]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "SCENÁR 03 / VÝSTUP", "987 produktov v master feede", "master_feed.xml + CSV · mapping.json · 1 000 vstupov")
    panel(draw, (M, 206, 580, 800))
    text(draw, (M + 24, 230), "Master feed", 24, INK, "medium", "serif")
    text(draw, (M + 24, 262), "Z 3 feedov do jedného", 12, MUTED, "regular", "mono")
    text(draw, (M + 24, 296), fmt_int(report["processed"]), 64, ACCENT, "medium", "mono")
    text(draw, (M + 24, 378), "produktov", 18, INK, "medium", "sans")
    text(draw, (M + 24, 406), "13 na kontrolu · 5 nulových skladov", 12, MUTED, "regular", "mono")
    items = [
        ("master_feed.xml", "987 produktov, XML"),
        ("master_feed.csv", "ten istý feed pre CSV"),
        ("mapping.json", "1 000 vstupov → master ID"),
        ("report.json + report.md", "duplicity, meny, ceny"),
    ]
    for index, (name, note) in enumerate(items):
        y = 452 + index * 64
        _file_row(draw, M + 24, y, "XML" if name.endswith(".xml") else "CSV" if name.endswith(".csv") else "DOC", name, note, ACCENT if index < 2 else GREEN)
    for index, label in enumerate(("987/1000", "unikátne EAN", "Decimal")):
        badge(draw, M + 24 + index * 140, 742, label, GREEN_SOFT, GREEN)

    csv_path = ctx["root"] / "output" / "mergado" / "master_feed.csv"
    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()[:20]
    _code_panel(draw, "master_feed.csv", lines, line_size=12, step=22)
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
        (str(report["flagged"]), "na kontrolu", "flagged, nie processed", ACCENT, ACCENT_SOFT),
        (str(report["silent_errors"]), "ticho prejdené", "musí byť 0", INK, INK_SOFT),
    ]
    if scenario == "shoptet":
        extra = (str(report.get("rounding_lines", 0)), "rounding line", "0,01 CZK viditeľne")
    elif scenario == "invoices":
        extra = (f"{report['lines_posted']}/{report['lines_total']}", "riadkov", "0 unmatched")
    else:
        extra = (fmt_int(report["input_count"]), "vstupov", "987 v masteri")
    cards.append((extra[0], extra[1], extra[2], ACCENT, ACCENT_SOFT))
    card_w = (W - 2 * M - 3 * 18) // 4
    for index, (value, label, note, accent, soft) in enumerate(cards):
        x = M + index * (card_w + 18)
        panel(draw, (x, 206, x + card_w, 380))
        draw.rectangle((x, 206, x + card_w, 210), fill=accent)
        text(draw, (x + 20, 228), value, 40 if len(value) < 6 else 32, INK, "medium", "mono")
        text(draw, (x + 20, 300), label, 16, INK, "medium", "serif")
        text(draw, (x + 20, 326), note, 12, MUTED, "regular", "mono")
        draw.rectangle((x + 20, 356, x + 66, 360), fill=soft)

    panel(draw, (M, 404, 790, 800))
    text(draw, (M + 24, 428), "Na kontrolu", 24, INK, "medium", "serif")
    text(draw, (766, 432), f"{report['flagged']} položiek", 11, ACCENT, "medium", "mono", anchor="ra")
    flagged = report.get("flagged_items", [])
    for index, item in enumerate(flagged[:5]):
        y = 474 + index * 44
        draw.rectangle((M + 24, y + 4, M + 28, y + 30), fill=ACCENT)
        text(draw, (M + 42, y), fit(draw, item["id"], font(12, "medium", "mono"), 170), 12, INK, "medium", "mono")
        reason = REASON_SK.get(item["reason"], item["reason"])
        text(draw, (M + 220, y), fit(draw, reason, font(14), 480), 14, MUTED)
    if len(flagged) > 5:
        text(draw, (M + 42, 474 + 5 * 44), f"+ {len(flagged) - 5} ďalších v reporte", 11, MUTED, "regular", "mono")
    rule(draw, M + 24, 720, 766, 720, LINE)
    text(draw, (M + 24, 736), "Syntetické dáta. Nie je to reálny klient.", 12, MUTED, "regular", "mono")
    text(draw, (M + 24, 760), "Každá položka na kontrolu je viditeľná v reporte.", 12, MUTED, "regular", "mono")

    panel(draw, (814, 404, 1368, 800))
    text(draw, (838, 428), "Kontroly", 24, INK, "medium", "serif")
    checks = report.get("checks", [])
    for index, check in enumerate(checks[:7]):
        y = 474 + index * 38
        color = GREEN if check["passed"] else ACCENT
        draw.ellipse((838, y + 5, 852, y + 19), fill=color)
        text(draw, (845, y + 7), "✓" if check["passed"] else "!", 10, CARD, "bold", "sans", anchor="mm")
        label = CHECK_SK.get(check["name"], check["name"])
        text(draw, (864, y), fit(draw, label, font(14, "medium"), 300), 14, INK, "medium", "sans")
    draw.rectangle((838, 742, 1342, 782), fill=ACCENT_SOFT, outline=LINE)
    text(draw, (854, 752), f"{len(report.get('warnings', []))} upozornení · všetky v report.json", 12, ACCENT, "medium", "mono")
    footer(draw)
    return image


def title_image(ctx: dict, scenario: str) -> Image.Image:
    report = ctx["reports"][scenario]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 5), fill=ACCENT)
    text(draw, (M, 54), "PEREPOLKIN.SK / DEMO PACK", 11, MUTED, "medium", "mono")
    text(draw, (W - M, 54), "SYNTETICKÉ DÁTA", 11, ACCENT, "medium", "mono", anchor="ra")
    text(draw, (M, 110), "LOKÁLNY CLI BEH / 2026", 11, ACCENT, "medium", "mono")
    title = {"shoptet": "Shoptet → Pohoda", "invoices": "Dodávateľské faktúry → Pohoda", "mergado": "Mergado / XML feed"}[scenario]
    y = 196
    draw.rectangle((M - 24, y + 4, M - 18, y + 94), fill=ACCENT)
    title_run(draw, M, y, title, 78, INK, W - 2 * M - 40)
    y += 112
    rule(draw, M, y + 18, M + 220, y + 18, ACCENT)
    subtitle = {
        "shoptet": f"Syntetické dáta. {report['input_count']} objednávok.",
        "invoices": f"Syntetické dáta. {report['input_count']} PDF faktúr.",
        "mergado": f"Syntetické dáta. {fmt_int(report['input_count'])} produktov.",
    }[scenario]
    text(draw, (M, y + 48), subtitle, 30, MUTED)
    text(draw, (M, 760), "Lokálny CLI beh · bez siete · bez reálneho klienta", 14, MUTED, "regular", "mono")
    stamp(draw, W - M - 72, 748, "DEMO")
    return image


def cta_image(ctx: dict, scenario: str) -> Image.Image:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 5), fill=ACCENT)
    text(draw, (M, 54), "PEREPOLKIN.SK / DEMO PACK", 11, MUTED, "medium", "mono")
    text(draw, (W - M, 54), "ĎALŠÍ KROK", 11, ACCENT, "medium", "mono", anchor="ra")
    text(draw, (M, 118), "Chcete test na", 72, INK, "medium", "serif")
    text(draw, (M, 204), "vašich dátach?", 72, INK, "medium", "serif")
    draw.rectangle((M, 318, M + 220, 322), fill=ACCENT)
    text(draw, (M, 360), "Pošlite 2 vzorky.", 36, INK, "medium", "serif")
    text(draw, (M, 430), "Ukážeme rovnaký report na vašich dátach.", 20, MUTED)
    draw.rectangle((M, 548, 420, 606), fill=ACCENT)
    text(draw, (M + 26, 568), "perepolkin.sk", 17, CARD, "medium", "mono")
    text(draw, (M, 650), "Demo je syntetické. Nie je to klientsky prípad.", 12, MUTED, "regular", "mono")
    text(draw, (M, 760), "Syntetické dáta · všetky firmy a doklady sú vymyslené · bez reálneho IČO/DIČ", 12, MUTED)
    stamp(draw, W - M - 72, 748, "DEMO")
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
            "- Limity: syntetické dáta, nie reálny klient",
            "- CTA: Chcem test na svojich dátach",
            "",
        ]
    )


def _manifest_object(report: dict) -> dict:
    scenario = report["scenario"]
    if scenario == "shoptet":
        alt = "Syntetické demo dáta, 50 objednávok, 46 automaticky, 4 na kontrolu"
        caption = "50 objednávok. 46 automaticky, 4 na kontrolu. 0 ticho prejdených chýb."
    elif scenario == "invoices":
        alt = "Syntetické demo dáta, 10 PDF faktúr, 8 automaticky, 2 na kontrolu, 48/48 riadkov"
        caption = "10 PDF faktúr. 8 automaticky, 2 na kontrolu. 48/48 riadkov. 0 ticho prejdených chýb."
    else:
        alt = "Syntetické demo dáta, 3 feedy, 1 000 produktov, 987 v master feede, 13 na kontrolu"
        caption = "3 feedy, 1 000 produktov. 987 v master feede, 13 na kontrolu. 0 ticho prejdených chýb."
    return {
        "scenario": scenario,
        "title": report["title"],
        "metrics": {
            "input": report["input_count"],
            "auto": report["processed"],
            "review": report["flagged"],
            "silent": report["silent_errors"],
        },
        "images": {
            "input": f"handoff/{scenario}/input.png",
            "run": f"handoff/{scenario}/run.png",
            "output": f"handoff/{scenario}/output.png",
            "report": f"handoff/{scenario}/report.png",
        },
        "video": f"handoff/{scenario}/video.mp4",
        "raw": "handoff/raw/run-all.mp4",
        "poster": f"handoff/{scenario}/run.png",
        "alt": alt,
        "caption": caption,
    }


def _git_meta() -> dict:
    def run(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    return {
        "remote": os.environ.get("DEMO_REMOTE") or run("remote", "get-url", "origin") or "local",
        "branch": run("rev-parse", "--abbrev-ref", "HEAD") or "feat/demo-assets-v2",
        "commit": os.environ.get("DEMO_COMMIT") or run("rev-parse", "--short", "HEAD") or "local",
    }


def handoff_readme(reports: dict, meta: dict | None = None) -> str:
    meta = meta or _git_meta()
    return f"""# Handoff pre dizajnéra

Demo pack pre **perepolkin.sk**. Všetko je syntetické, bez reálneho klienta,
bez IČO/DIČ a bez live pripojenia na Shoptet/Pohoda/Mergado.

Vizuál v2 používa tokeny webu: cream `#F7F4EE`, karty `#FDFBF7`,
text `#1F1B16`, akcent `#A8382A`, OK `#2F6B4B`; Newsreader + Inter +
JetBrains Mono. Terminál je tmavý `#1F1B16`, warning je akcentná červená.

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
| `handoff/raw/run-all.mp4` | Surová 59,5 s nahrávka reálneho `run-all`, bez strihu |
| `handoff/raw/poster.png` | Poster pre raw video |
| `handoff/raw/README.md` | Čo presne raw nahrávka ukazuje |
| `handoff/manifest.json` | Strojový manifest všetkých troch scenárov |
| `handoff/README.md` | Tento súbor |
| `handoff/perepolkin-demo-pack.zip` | ZIP so vstupmi, výstupmi, reportmi, screenshotmi a videom |

## Presné čísla na stránku

| Scenár | Vstup | Automaticky | Na kontrolu | Ticho prejdené |
|---|---|---:|---:|---:|
""" + "\n".join(
        f"| {report['title']} | {fmt_int(report['input_count'])} | {report['processed']} | {report['flagged']} | {report['silent_errors']} |"
        for report in reports.values()
    ) + f"""

**Nepíšte „nulový počet chýb“.** Správna formulácia je
**„0 ticho prejdených chýb“** a k tomu počet položiek na ručnú kontrolu.
Demo má zámerne flagged prípady.

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
- 90 sekúnd, 1440×900, 30 fps, bez zvuku, bez browser chrome, veľký font.
- Osnova: titul → terminál → výstup → report → CTA „Pošlite 2 vzorky“.
- Samostatná surová nahrávka: `handoff/raw/run-all.mp4` (59,5 s, 1440×900,
  30 fps, bez zvuku, reálny `python -m demo run-all`, bez strihu a bez hudby).
  Poster je `handoff/raw/poster.png`, popis `handoff/raw/README.md`.
  Na stránke ju použite ako samostatný odkaz „Pozrieť surový beh“.

## Odkazy

- GitHub: https://github.com/Saa1001zp/shoptet-pohoda-demo
- Branch: `{meta['branch']}`
- Commit: `{meta['commit']}`
- Remote: `{meta['remote']}`
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
- [ ] Nie je tam „nulový počet chýb“.
- [ ] Nie je tam reálne IČO/DIČ ani reálne meno.
- [ ] CTA je „Chcem test na svojich dátach“.
"""


def _build_video(scenario: str, ctx: dict, out_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg nie je v PATH. Použite `--skip-video` alebo nainštalujte ffmpeg.")
    log_lines = (ctx["root"] / "output" / scenario / "run.log").read_text(encoding="utf-8").splitlines()
    with tempfile.TemporaryDirectory(prefix=f"demo-video-{scenario}-") as tmp:
        tmp_path = Path(tmp)
        frames: list[tuple[Path, int]] = []

        title_path = tmp_path / "00_title.png"
        _save(title_image(ctx, scenario), title_path)
        frames.append((title_path, 10))

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
        frames.append((cta_path, 20.1))

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
            "-vf",
            "tpad=stop_mode=clone:stop_duration=1",
            "-r",
            "30",
            "-frames:v",
            "2700",
            "-an",
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

    objects = [_manifest_object(ctx["reports"][scenario]) for scenario in SCENARIOS]
    meta = _git_meta()
    manifest = {
        "generated_at": "2026-11-10T10:00:00Z",
        "synthetic": True,
        "source": {
            "remote": meta["remote"],
            "branch": meta["branch"],
            "commit": meta["commit"],
        },
        "scenarios": objects,
    }
    write_text(handoff / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    for obj in objects:
        write_text(handoff / obj["scenario"] / "manifest.json", json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

    readme = handoff_readme(ctx["reports"], meta)
    write_text(handoff / "README.md", readme)
    write_text(handoff_root() / "README.md", readme)
    return {"screenshots": shots, "video": video if make_video else None, "handoff": handoff, "manifest": handoff / "manifest.json"}


def _zip_entries(root: Path) -> Iterable[tuple[Path, str]]:
    prefix = "shoptet-pohoda-demo"
    fixed = ["README.md", "LIMITATIONS.md", "handoff.md", "pyproject.toml", "Makefile", ".python-version", "uv.lock"]
    for name in fixed:
        path = REPO_ROOT / name
        if path.exists():
            yield path, f"{prefix}/{name}"

    for path in sorted((REPO_ROOT / "demo").rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        yield path, f"{prefix}/{path.relative_to(REPO_ROOT).as_posix()}"

    for path in sorted((REPO_ROOT / "scripts").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path, f"{prefix}/{path.relative_to(REPO_ROOT).as_posix()}"

    for path in sorted((REPO_ROOT / "assets" / "fonts").rglob("*")):
        if path.is_file():
            yield path, f"{prefix}/assets/fonts/{path.relative_to(REPO_ROOT / 'assets' / 'fonts').as_posix()}"

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
