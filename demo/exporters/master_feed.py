"""Write the master feed in XML and CSV, plus a mapping file."""

from __future__ import annotations

import csv
from pathlib import Path

from lxml import etree

from ..models import MasterProduct
from ..util import ensure_dir, fmt, write_json


def write_master_xml(path: Path, products: list[MasterProduct]) -> None:
    ensure_dir(path.parent)
    root = etree.Element(
        "PRODUCTS",
        count=str(len(products)),
        generated_at="2026-11-10T10:00:00Z",
        note="Syntetické dáta – DEMO",
    )
    for product in products:
        node = etree.SubElement(root, "PRODUCT")
        for tag, value in [
            ("MASTER_ID", product.master_id),
            ("SKU", product.sku),
            ("EAN", product.ean),
            ("NAME", product.name),
            ("CATEGORY", product.category),
            ("PRICE", fmt(product.price)),
            ("CURRENCY", product.currency),
            ("STOCK", str(product.stock)),
            ("VAT", f"{product.vat_rate:g}"),
            ("SOURCE", product.source),
            ("SOURCE_ID", product.source_id),
        ]:
            child = etree.SubElement(node, tag)
            child.text = value
    path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def write_master_csv(path: Path, products: list[MasterProduct]) -> None:
    fields = [
        "MASTER_ID",
        "SKU",
        "EAN",
        "NAME",
        "CATEGORY",
        "PRICE",
        "CURRENCY",
        "STOCK",
        "VAT",
        "SOURCE",
        "SOURCE_ID",
    ]
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "MASTER_ID": product.master_id,
                    "SKU": product.sku,
                    "EAN": product.ean,
                    "NAME": product.name,
                    "CATEGORY": product.category,
                    "PRICE": fmt(product.price),
                    "CURRENCY": product.currency,
                    "STOCK": str(product.stock),
                    "VAT": f"{product.vat_rate:g}",
                    "SOURCE": product.source,
                    "SOURCE_ID": product.source_id,
                }
            )


def write_mapping(path: Path, payload: dict) -> None:
    write_json(path, payload)
