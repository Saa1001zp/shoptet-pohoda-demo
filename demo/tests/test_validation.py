"""Unit tests for Decimal money, VAT, totals and catalog matching."""

from __future__ import annotations

from decimal import Decimal

from demo.models import CatalogItem
from demo.util import ean13, ean_valid, money, parse_decimal, vat_amount
from demo.validation.matching import match_catalog
from demo.validation.totals import difference, sum_totals, totals_match
from demo.validation.vat import line_vat, rate_is_supported, rate_label, split_by_rate


def test_money_is_decimal_and_rounds_half_up() -> None:
    assert money("0.005") == Decimal("0.01")
    assert money(Decimal("2.675")) == Decimal("2.68")
    assert money("199.90") == Decimal("199.90")
    assert isinstance(money("1.00"), Decimal)


def test_parse_decimal_accepts_demo_formats() -> None:
    assert parse_decimal("199.90") == Decimal("199.90")
    assert parse_decimal("199,90") == Decimal("199.90")
    assert parse_decimal("1 299,00") == Decimal("1299.00")
    assert parse_decimal("1299.00 CZK") == Decimal("1299.00")
    assert parse_decimal("N/A") is None


def test_vat_23_percent() -> None:
    vat, gross = line_vat(Decimal("100.00"), Decimal("23"))
    assert vat == Decimal("23.00")
    assert gross == Decimal("123.00")
    assert vat_amount(Decimal("99.00"), Decimal("23")) == Decimal("22.77")
    assert rate_is_supported(Decimal("0"))
    assert rate_is_supported(Decimal("23"))
    assert not rate_is_supported(Decimal("21"))
    assert rate_label(Decimal("23")) == "high"
    assert rate_label(Decimal("0")) == "none"


def test_vat_zero_and_mixed_split() -> None:
    vat, gross = line_vat(Decimal("399.00"), Decimal("0"))
    assert vat == Decimal("0.00")
    assert gross == Decimal("399.00")

    lines = [
        {"vat_rate": Decimal("23"), "net": Decimal("100.00"), "vat": Decimal("23.00"), "gross": Decimal("123.00")},
        {"vat_rate": Decimal("0"), "net": Decimal("50.00"), "vat": Decimal("0.00"), "gross": Decimal("50.00")},
    ]
    buckets = split_by_rate(lines)
    assert buckets["23"] == {"net": Decimal("100.00"), "vat": Decimal("23.00"), "gross": Decimal("123.00")}
    assert buckets["0"] == {"net": Decimal("50.00"), "vat": Decimal("0.00"), "gross": Decimal("50.00")}


def test_totals_and_rounding_difference() -> None:
    lines = [
        {"net": Decimal("599.70"), "vat": Decimal("137.93"), "gross": Decimal("737.63")},
        {"net": Decimal("99.00"), "vat": Decimal("22.77"), "gross": Decimal("121.77")},
    ]
    totals = sum_totals(lines)
    assert totals == {"net": Decimal("698.70"), "vat": Decimal("160.70"), "gross": Decimal("859.40")}
    assert abs(difference(Decimal("859.41"), totals["gross"])) == Decimal("0.01")
    assert not totals_match(lines, Decimal("859.41"))

    lines.append({"net": Decimal("0.01"), "vat": Decimal("0.00"), "gross": Decimal("0.01")})
    assert totals_match(lines, Decimal("859.41"))


def test_ean_checksum() -> None:
    ean = ean13(1001)
    assert len(ean) == 13
    assert ean_valid(ean)
    assert not ean_valid("1234567890123")
    assert not ean_valid(None)
    assert not ean_valid("123")


def test_catalog_matching_priority_and_reasons() -> None:
    item = CatalogItem(
        sku="SKU-001",
        ean=ean13(1001),
        name="Demo produkt",
        unit="ks",
        price=Decimal("199.90"),
        vat_rate=Decimal("23"),
        stock=10,
    )
    by_sku = {item.sku: item}
    by_ean = {item.ean: item}

    matched, method, reason = match_catalog("SKU-001", item.ean, by_sku, by_ean)
    assert (matched, method, reason) == (item, "sku", None)

    matched, method, reason = match_catalog("SKU-999", item.ean, by_sku, by_ean)
    assert (matched, method, reason) == (item, "ean", "sku_matched_by_ean")

    matched, method, reason = match_catalog("SKU-999", None, by_sku, by_ean)
    assert matched is None
    assert method is None
    assert reason == "catalog_item_not_found"

    matched, method, reason = match_catalog("SKU-001", ean13(9999), by_sku, by_ean)
    assert matched is item
    assert method == "sku"
    assert reason == "ean_differs_from_catalog"
