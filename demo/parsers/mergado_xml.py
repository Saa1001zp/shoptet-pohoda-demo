"""Read Mergado-style supplier XML and CSV feeds."""

from __future__ import annotations

import csv
from pathlib import Path

from lxml import etree


def _text(node: etree._Element, tag: str) -> str:
    value = node.findtext(tag)
    return value.strip() if value else ""


def _load_xml(path: Path) -> list[dict]:
    tree = etree.parse(str(path))
    root = tree.getroot()
    supplier = root.get("supplier") or path.stem[-1].upper()
    products: list[dict] = []
    for node in root.findall(".//SHOPITEM"):
        source_id = _text(node, "PRODUCT_ID")
        products.append(
            {
                "source": supplier,
                "source_id": source_id,
                "sku": _text(node, "SKU"),
                "ean": _text(node, "EAN") or None,
                "name": _text(node, "NAME"),
                "category": _text(node, "CATEGORY") or None,
                "price_raw": _text(node, "PRICE"),
                "currency": _text(node, "CURRENCY") or "CZK",
                "stock": _text(node, "STOCK"),
                "vat_rate": _text(node, "VAT"),
            }
        )
    return products


def _load_csv(path: Path) -> list[dict]:
    supplier = path.stem[-1].upper()
    products: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            products.append(
                {
                    "source": row.get("PRODUCT_ID", "")[:1] or supplier,
                    "source_id": row.get("PRODUCT_ID", "").strip(),
                    "sku": row.get("SKU", "").strip(),
                    "ean": (row.get("EAN") or "").strip() or None,
                    "name": row.get("NAME", "").strip(),
                    "category": (row.get("CATEGORY") or "").strip() or None,
                    "price_raw": (row.get("PRICE") or "").strip(),
                    "currency": (row.get("CURRENCY") or "CZK").strip(),
                    "stock": (row.get("STOCK") or "0").strip(),
                    "vat_rate": (row.get("VAT") or "23").strip(),
                }
            )
    return products


def load_feed(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    return _load_xml(path)
