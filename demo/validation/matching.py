"""Catalog matching by SKU first, then EAN. Returns an explicit reason."""

from __future__ import annotations

from ..models import CatalogItem


def match_catalog(
    sku: str,
    ean: str | None,
    by_sku: dict[str, CatalogItem],
    by_ean: dict[str, CatalogItem],
) -> tuple[CatalogItem | None, str | None, str | None]:
    item = by_sku.get(sku)
    if item is not None:
        if ean and item.ean != ean:
            return item, "sku", "ean_differs_from_catalog"
        return item, "sku", None

    if ean:
        item = by_ean.get(ean)
        if item is not None:
            return item, "ean", "sku_matched_by_ean"
    return None, None, "catalog_item_not_found"
