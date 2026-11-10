"""Decimal VAT arithmetic. No float ever touches a monetary value."""

from __future__ import annotations

from decimal import Decimal

from ..util import money, vat_amount

ALLOWED_RATES = {Decimal("0"), Decimal("23")}


def line_vat(net: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    vat = vat_amount(net, rate)
    return vat, money(net + vat)


def rate_is_supported(rate: Decimal) -> bool:
    return rate in ALLOWED_RATES


def rate_label(rate: Decimal) -> str:
    if rate == Decimal("23"):
        return "high"
    if rate == Decimal("0"):
        return "none"
    return "unknown"


def split_by_rate(lines: list[dict]) -> dict[str, dict[str, Decimal]]:
    buckets: dict[str, dict[str, Decimal]] = {}
    for line in lines:
        key = f"{line['vat_rate']:g}"
        bucket = buckets.setdefault(key, {"net": Decimal("0.00"), "vat": Decimal("0.00"), "gross": Decimal("0.00")})
        bucket["net"] += line["net"]
        bucket["vat"] += line["vat"]
        bucket["gross"] += line["gross"]
    for bucket in buckets.values():
        for key in bucket:
            bucket[key] = money(bucket[key])
    return buckets
