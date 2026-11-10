"""Totals checks: sum(lines) == total, rounding is explicit."""

from __future__ import annotations

from decimal import Decimal

from ..util import money


def sum_totals(lines: list[dict]) -> dict[str, Decimal]:
    net = money(sum((line["net"] for line in lines), Decimal("0.00")))
    vat = money(sum((line["vat"] for line in lines), Decimal("0.00")))
    gross = money(sum((line["gross"] for line in lines), Decimal("0.00")))
    return {"net": net, "vat": vat, "gross": gross}


def difference(computed: Decimal, declared: Decimal) -> Decimal:
    return money(declared - computed)


def totals_match(lines: list[dict], declared: Decimal) -> bool:
    return sum_totals(lines)["gross"] == money(declared)
