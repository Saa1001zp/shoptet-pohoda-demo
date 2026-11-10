"""Generate three synthetic supplier feeds with 1,000 products in total.

Supplier A: 400 products, XML
Supplier B: 350 products, XML
Supplier C: 250 products, CSV
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from ..config import SEED, input_root
from ..util import ean13, ensure_dir, money, write_json, write_text

CATEGORIES = ["Kancelária", "Elektronika", "Príslušenstvo", "Domácnosť", "Šport"]
SUPPLIER_SIZES = {"A": 400, "B": 350, "C": 250}


def _product(source: str, index: int) -> dict:
    source_id = f"{source}-{index:04d}"
    category = CATEGORIES[(index - 1) % len(CATEGORIES)]
    name = f"Demo produkt {source_id}"
    stock = 5 + (index * 7) % 180
    price = money(Decimal("19.90") + Decimal((index * 13) % 900) / Decimal("10"))
    currency = "CZK"

    # 10 products without a category. Nine stay without one; A-0010 is
    # repaired by the keyword rule in the scenario (and reported as such).
    if source == "A" and index <= 10:
        category = ""
    if source == "A" and index == 10:
        name = "USB-C kábel 2 m (DEMO)"

    # 5 products with zero stock are still valid master-feed products.
    if source == "C" and index <= 5:
        stock = 0

    # 2 products in another currency cannot be converted without a rate.
    if source == "B" and index == 200:
        currency = "EUR"
    if source == "C" and index == 200:
        currency = "USD"

    # 1 broken price must never be repaired silently.
    raw_price = f"{price:.2f}"
    if source == "C" and index == 250:
        raw_price = "N/A"

    ean = ean13(3000 + ({"A": 0, "B": 500, "C": 900}[source]) + index)
    if source == "B" and index == 100:
        # Duplicate of A-0050's EAN. The later occurrence is flagged.
        ean = ean13(3000 + 50)

    return {
        "source": source,
        "source_id": source_id,
        "sku": f"SKU-{source}-{index:04d}",
        "ean": ean,
        "name": name,
        "category": category,
        "price": raw_price,
        "currency": currency,
        "stock": stock,
        "vat_rate": "23",
    }


def build_products() -> list[dict]:
    products: list[dict] = []
    for source, size in SUPPLIER_SIZES.items():
        products.extend(_product(source, index) for index in range(1, size + 1))
    assert len(products) == 1000
    return products


def _write_xml_feed(path: Path, source: str, products: list[dict]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<SHOP supplier="{source}" note="Syntetické dáta – DEMO">',
    ]
    for product in products:
        lines.append("  <SHOPITEM>")
        for tag, key in [
            ("PRODUCT_ID", "source_id"),
            ("SKU", "sku"),
            ("EAN", "ean"),
            ("NAME", "name"),
            ("CATEGORY", "category"),
            ("PRICE", "price"),
            ("CURRENCY", "currency"),
            ("STOCK", "stock"),
            ("VAT", "vat_rate"),
        ]:
            value = product[key]
            lines.append(f"    <{tag}>{escape(str(value))}</{tag}>")
        lines.append("  </SHOPITEM>")
    lines.append("</SHOP>")
    write_text(path, "\n".join(lines) + "\n")


def _write_csv_feed(path: Path, products: list[dict]) -> None:
    fields = ["PRODUCT_ID", "SKU", "EAN", "NAME", "CATEGORY", "PRICE", "CURRENCY", "STOCK", "VAT"]
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "PRODUCT_ID": product["source_id"],
                    "SKU": product["sku"],
                    "EAN": product["ean"],
                    "NAME": product["name"],
                    "CATEGORY": product["category"],
                    "PRICE": product["price"],
                    "CURRENCY": product["currency"],
                    "STOCK": product["stock"],
                    "VAT": product["vat_rate"],
                }
            )


def generate(root: Path | None = None) -> dict:
    root = root or input_root() / "mergado"
    ensure_dir(root)
    products = build_products()
    by_source = {source: [p for p in products if p["source"] == source] for source in SUPPLIER_SIZES}

    _write_xml_feed(root / "supplier_a.xml", "A", by_source["A"])
    _write_xml_feed(root / "supplier_b.xml", "B", by_source["B"])
    _write_csv_feed(root / "supplier_c.csv", by_source["C"])
    write_json(
        root / "manifest.json",
        {
            "seed": SEED,
            "total": len(products),
            "feeds": [
                {"file": "supplier_a.xml", "supplier": "A", "products": len(by_source["A"])},
                {"file": "supplier_b.xml", "supplier": "B", "products": len(by_source["B"])},
                {"file": "supplier_c.csv", "supplier": "C", "products": len(by_source["C"])},
            ],
        },
    )
    write_text(
        root / "README.txt",
        "Syntetické Mergado/XML feedy pre demo. 3 dodávatelia, 1 000 produktov.\n"
        "A a B sú XML, C je CSV. Všetky názvy a firmy sú vymyslené.\n",
    )
    return {"products": len(products), "feeds": 3, "path": str(root)}
