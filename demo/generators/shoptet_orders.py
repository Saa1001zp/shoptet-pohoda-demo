"""Generate 50 synthetic Shoptet orders, a catalog and one warehouse."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from faker import Faker

from ..config import CURRENCY, DEMO_SHOP, SEED, WAREHOUSE, input_root
from ..models import CatalogItem, Customer, Order, OrderItem
from ..util import ean13, ensure_dir, write_json, write_text

CATALOG: list[CatalogItem] = [
    CatalogItem(sku="SKU-001", ean=ean13(1001), name="Demo kancelársky papier A4", unit="bal", price=Decimal("199.90"), vat_rate=Decimal("23"), stock=240),
    CatalogItem(sku="SKU-002", ean=ean13(1002), name="Demo USB-C kábel 2 m", unit="ks", price=Decimal("349.00"), vat_rate=Decimal("23"), stock=180),
    CatalogItem(sku="SKU-003", ean=ean13(1003), name="Demo bezdrôtová myš", unit="ks", price=Decimal("89.50"), vat_rate=Decimal("23"), stock=320),
    CatalogItem(sku="SKU-004", ean=ean13(1004), name="Demo monitor 27\"", unit="ks", price=Decimal("1290.00"), vat_rate=Decimal("23"), stock=75),
    CatalogItem(sku="SKU-005", ean=ean13(1005), name="Demo zápisník A5", unit="ks", price=Decimal("45.00"), vat_rate=Decimal("23"), stock=500),
    CatalogItem(sku="SKU-006", ean=ean13(1006), name="Demo klávesnica SK", unit="ks", price=Decimal("599.00"), vat_rate=Decimal("23"), stock=120),
    CatalogItem(sku="SKU-007", ean=ean13(1007), name="Demo reproduktor", unit="ks", price=Decimal("249.90"), vat_rate=Decimal("23"), stock=95),
    CatalogItem(sku="SKU-008", ean=ean13(1008), name="Demo podložka na stôl", unit="ks", price=Decimal("79.90"), vat_rate=Decimal("23"), stock=210),
    CatalogItem(sku="SKU-009", ean=ean13(1009), name="Demo webkamera Full HD", unit="ks", price=Decimal("1890.00"), vat_rate=Decimal("23"), stock=60),
    CatalogItem(sku="SKU-010", ean=ean13(1010), name="Demo kancelárske pero", unit="ks", price=Decimal("12.50"), vat_rate=Decimal("23"), stock=900),
    CatalogItem(sku="SKU-011", ean=ean13(1011), name="Demo stojan na monitor", unit="ks", price=Decimal("320.00"), vat_rate=Decimal("23"), stock=140),
    CatalogItem(sku="SKU-012", ean=ean13(1012), name="Demo čistič obrazovky", unit="ks", price=Decimal("149.00"), vat_rate=Decimal("23"), stock=260),
]


def _customer(fake: Faker, number: int) -> Customer:
    return Customer(
        name=f"Demo Zákazník {number:02d}",
        email=f"demo{number:02d}@example.com",
        street=f"Demo ulica {number}",
        city=fake.city(),
        zip=f"1{number:04d}"[:5],
        country="CZ",
    )


def _items_for(order_no: int, rng: random.Random) -> list[OrderItem]:
    count = 1 + (order_no % 3)
    picked: list[CatalogItem] = []
    cursor = order_no % len(CATALOG)
    for offset in range(count):
        picked.append(CATALOG[(cursor + offset * 3) % len(CATALOG)])
    return [
        OrderItem(
            sku=item.sku,
            ean=item.ean,
            name=item.name,
            qty=1 + rng.randint(0, 2),
            unit_price=item.price,
            vat_rate=item.vat_rate,
        )
        for item in picked
    ]


def build_orders() -> list[Order]:
    fake = Faker("cs_CZ")
    Faker.seed(SEED)
    rng = random.Random(SEED)
    orders: list[Order] = []
    base = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)

    for number in range(1, 50):
        created = base + timedelta(hours=(number - 1) * 3)
        items = _items_for(number, rng)
        order = Order(
            order_id=f"DEMO-2026-{number:04d}",
            created_at=created,
            currency=CURRENCY,
            customer=_customer(fake, number),
            items=items,
            shipping=Decimal("99.00"),
            payment="card" if number % 2 else "transfer",
            status="open",
        )

        # 3 orders without EAN. Two are repaired from the catalog by SKU,
        # one references an unknown SKU and must go to manual review.
        if number in (12, 27):
            order.items = [item.model_copy(update={"ean": None}) for item in order.items]
        if number == 41:
            order.items = [
                OrderItem(
                    sku="SKU-999",
                    ean=None,
                    name="Demo neznámy produkt",
                    qty=1,
                    unit_price=Decimal("99.00"),
                    vat_rate=Decimal("23"),
                )
            ]

        # 0.01 CZK declared-total mismatch. The scenario adds a visible
        # rounding line; it never changes input values silently.
        if number == 31:
            order.items = [
                OrderItem(
                    sku="SKU-001",
                    ean=CATALOG[0].ean,
                    name=CATALOG[0].name,
                    qty=3,
                    unit_price=Decimal("199.90"),
                    vat_rate=Decimal("23"),
                )
            ]
            order.shipping = Decimal("99.00")
            order.declared_total = Decimal("859.41")

        if number == 33:
            order.status = "storno"
            order.note = "Storno objednávky – vyžaduje ručné spracovanie."
        if number == 44:
            order.status = "blocked"
            order.note = "Doklad patrí do uzavretého účtovného obdobia."

        orders.append(order)

    # 1 duplicate order: the last row repeats order DEMO-2026-0007.
    duplicate = orders[6].model_copy(deep=True)
    orders.append(duplicate)
    assert len(orders) == 50
    return orders


def _write_orders_csv(path: Path, orders: list[Order]) -> None:
    fields = [
        "order_id",
        "created_at",
        "currency",
        "customer_name",
        "customer_email",
        "customer_street",
        "customer_city",
        "customer_zip",
        "customer_country",
        "sku",
        "ean",
        "name",
        "qty",
        "unit_price",
        "vat_rate",
        "shipping",
        "payment",
        "status",
        "note",
        "declared_total",
    ]
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for order in orders:
            for item in order.items:
                writer.writerow(
                    {
                        "order_id": order.order_id,
                        "created_at": order.created_at.isoformat().replace("+00:00", "Z"),
                        "currency": order.currency,
                        "customer_name": order.customer.name,
                        "customer_email": order.customer.email,
                        "customer_street": order.customer.street,
                        "customer_city": order.customer.city,
                        "customer_zip": order.customer.zip,
                        "customer_country": order.customer.country,
                        "sku": item.sku,
                        "ean": item.ean or "",
                        "name": item.name,
                        "qty": item.qty,
                        "unit_price": f"{item.unit_price:.2f}",
                        "vat_rate": f"{item.vat_rate:g}",
                        "shipping": f"{order.shipping:.2f}",
                        "payment": order.payment,
                        "status": order.status,
                        "note": order.note or "",
                        "declared_total": f"{order.declared_total:.2f}" if order.declared_total is not None else "",
                    }
                )


def generate(root: Path | None = None) -> dict:
    root = root or input_root() / "shoptet"
    ensure_dir(root)
    orders = build_orders()

    write_json(root / "orders.json", [order.model_dump(mode="json") for order in orders])
    _write_orders_csv(root / "orders.csv", orders)
    write_json(root / "catalog.json", [item.model_dump(mode="json") for item in CATALOG])

    stock = {
        "warehouse": WAREHOUSE,
        "company": DEMO_SHOP,
        "currency": CURRENCY,
        "items": [
            {"sku": item.sku, "ean": item.ean, "stock": item.stock, "unit": item.unit}
            for item in CATALOG
        ],
    }
    write_json(root / "stock.json", stock)
    write_text(
        root / "README.txt",
        "Syntetické vstupné dáta pre demo Shoptet → Pohoda.\n"
        "Firma DemoShop s.r.o. je vymyslená. Žiadne reálne IČO, DIČ ani klienti.\n"
        "50 objednávok, 12 katalógových položiek, 1 sklad.\n",
    )
    return {
        "orders": len(orders),
        "catalog": len(CATALOG),
        "path": str(root),
    }
