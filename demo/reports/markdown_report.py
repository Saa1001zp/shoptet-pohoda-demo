"""Human-readable report.md in Slovak."""

from __future__ import annotations

from pathlib import Path

from ..util import ensure_dir, fmt_int, write_text

REASON_SK = {
    "missing_ean_enriched": "EAN chýbal, doplnené z katalógu podľa SKU",
    "missing_ean_unresolved": "chýba EAN a SKU nie je v katalógu",
    "unknown_sku": "SKU nie je v katalógu",
    "duplicate_order": "duplicitná objednávka",
    "storno_requires_manual": "storno – vyžaduje ručné spracovanie",
    "closed_period": "doklad patrí do uzavretého obdobia",
    "vat_rounding": "zaokrúhlenie DPH 0,01 CZK – pridaný rounding line",
    "total_mismatch": "nesúlad celkovej sumy",
    "ean_mismatch": "EAN sa nezhoduje s katalógom",
    "scan_requires_ocr": "sken bez textovej vrstvy – potrebné OCR / ručné zadanie",
    "duplicate_invoice": "duplicitná faktúra",
    "sku_matched_by_ean": "SKU chýbalo, položka spárovaná cez EAN",
    "price_differs_from_catalog": "cena sa líši od katalógu – použité cena z faktúry",
    "mixed_vat_rates": "faktúra kombinuje 0 % a 23 % DPH",
    "missing_category": "chýba kategória",
    "category_inferred": "kategória odvodená z názvu",
    "duplicate_ean": "duplicitný EAN",
    "unsupported_currency": "iná mena ako CZK",
    "invalid_price": "neplatná cena",
    "zero_stock": "nulový sklad – produkt zostal v master feede",
}


def _label(reason: str) -> str:
    return REASON_SK.get(reason, reason)


def _section(title: str, items: list[dict], empty: str = "Žiadne.") -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.append(empty)
    else:
        for item in items:
            detail = f" — {item['detail']}" if item.get("detail") else ""
            lines.append(f"- `{item['id']}` — {_label(item['reason'])}{detail}")
    lines.append("")
    return lines


def render(report: dict) -> str:
    scenario = report["scenario"]
    lines = [f"# Demo: {report['title']}", ""]
    if scenario == "shoptet":
        lines.append(f"- Vstup: {fmt_int(report['input_count'])} objednávok")
    elif scenario == "invoices":
        lines.append(f"- Vstup: {fmt_int(report['input_count'])} faktúr")
    else:
        lines.append(f"- Vstup: {fmt_int(report['input_count'])} produktov")

    lines.append(f"- Spracované: {fmt_int(report['processed'])}")
    lines.append(f"- Na kontrolu: {fmt_int(report['flagged'])}")
    if "lines_total" in report:
        lines.append(f"- Riadky: {fmt_int(report['lines_posted'])}/{fmt_int(report['lines_total'])}")
    lines.append(f"- Ticho prejdené chyby: {report['silent_errors']}")
    lines.append(f"- Čas: {report['duration_ms'] / 1000:.0f} s (simulovaný demo čas)")
    lines.append("")

    lines.extend(_section("Na kontrolu", report.get("flagged_items", [])))
    lines.extend(_section("Upozornenia", report.get("warnings", [])))

    lines.extend(["## Kontroly", ""])
    for check in report.get("checks", []):
        mark = "OK" if check["passed"] else "FAIL"
        detail = f" — {check['detail']}" if check.get("detail") else ""
        lines.append(f"- {mark} `{check['name']}`{detail}")
    lines.append("")

    if report.get("outputs"):
        lines.extend(["## Výstupy", ""])
        for output in report["outputs"]:
            lines.append(f"- `{output}`")
        lines.append("")

    lines.extend(
        [
            "## Limity",
            "",
            "- Syntetické dáta, všetky firmy a osoby sú vymyslené.",
            "- Nie je to reálny klient ani klientsky prípad.",
            "- Žiadne reálne pripojenie k Shoptetu, Pohode alebo Mergadu.",
            "- Demo beží lokálne, bez siete, databázy a Dockeru.",
            "",
        ]
    )
    return "\n".join(lines)


def write(output_dir: Path, report: dict) -> None:
    ensure_dir(output_dir)
    write_text(output_dir / "report.md", render(report))
