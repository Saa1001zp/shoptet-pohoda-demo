"""Load Shoptet orders from JSON or CSV, plus the catalog."""

from __future__ import annotations

import csv
import json
from collections import OrderedDict
from pathlib import Path

from ..models import CatalogItem, Order


def load_catalog(path: Path) -> tuple[dict[str, CatalogItem], dict[str, CatalogItem]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = [CatalogItem.model_validate(item) for item in raw]
    by_sku = {item.sku: item for item in items}
    by_ean = {item.ean: item for item in items if item.ean}
    return by_sku, by_ean


def _order_from_dict(raw: dict) -> Order:
    if isinstance(raw.get("items"), list):
        return Order.model_validate(raw)
    raise ValueError("order JSON must contain an items list")


def _load_csv(path: Path) -> list[Order]:
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            grouped.setdefault(row["order_id"], []).append(row)

    orders: list[Order] = []
    for order_id, rows in grouped.items():
        first = rows[0]
        items = [
            {
                "sku": row["sku"],
                "ean": row["ean"] or None,
                "name": row["name"],
                "qty": int(row["qty"]),
                "unit_price": row["unit_price"],
                "vat_rate": row["vat_rate"],
            }
            for row in rows
        ]
        payload = {
            "order_id": order_id,
            "created_at": first["created_at"],
            "currency": first["currency"] or "CZK",
            "customer": {
                "name": first["customer_name"],
                "email": first["customer_email"],
                "street": first["customer_street"],
                "city": first["customer_city"],
                "zip": first["customer_zip"],
                "country": first["customer_country"] or "CZ",
            },
            "items": items,
            "shipping": first["shipping"],
            "payment": first["payment"] or "card",
            "status": first["status"] or "open",
            "note": first["note"] or None,
            "declared_total": first["declared_total"] or None,
        }
        orders.append(Order.model_validate(payload))
    return orders


def load_orders(path: Path) -> list[Order]:
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("orders JSON must be a list")
    return [_order_from_dict(item) for item in raw]
