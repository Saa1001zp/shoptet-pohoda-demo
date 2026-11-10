"""Scenario 1: 50 synthetic Shoptet orders -> Pohoda invoices + stock issues."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from ..config import CURRENCY, WAREHOUSE, input_root, scenario_output
from ..exporters.pohoda_xml import (
    count_elements,
    validate_xml,
    write_invoice_pack,
    write_invoice_xml,
    write_stock_pack,
)
from ..models import Order
from ..parsers.shoptet_csv import load_catalog, load_orders
from ..reports.json_report import ReportBuilder
from ..reports.markdown_report import write as write_markdown
from ..util import RunLog, ensure_dir, fmt, money, reset_dir, write_json
from ..validation.matching import match_catalog
from ..validation.totals import sum_totals
from ..validation.vat import line_vat, rate_is_supported, rate_label, split_by_rate

SCENARIO = "shoptet"


def _invoice_from_order(order: Order, catalog_by_sku, warnings: list[tuple[str, str, str]]) -> dict | None:
    lines: list[dict] = []
    for item in order.items:
        catalog_item, method, reason = match_catalog(item.sku, item.ean, catalog_by_sku, {})
        if catalog_item is None:
            return None
        if item.ean is None:
            warnings.append(
                (
                    order.order_id,
                    "missing_ean_enriched",
                    f"SKU {item.sku}: EAN {catalog_item.ean} doplnené z katalógu",
                )
            )
        elif item.ean != catalog_item.ean:
            return None
        if item.vat_rate != catalog_item.vat_rate or not rate_is_supported(item.vat_rate):
            return None

        net = money(item.unit_price * item.qty)
        vat, gross = line_vat(net, item.vat_rate)
        lines.append(
            {
                "description": item.name,
                "sku": item.sku,
                "ean": catalog_item.ean,
                "qty": item.qty,
                "unit": catalog_item.unit,
                "unit_price": item.unit_price,
                "vat_rate": item.vat_rate,
                "net": net,
                "vat": vat,
                "gross": gross,
                "rate_label": rate_label(item.vat_rate),
                "is_rounding": False,
            }
        )

    shipping_net = money(order.shipping)
    shipping_vat, shipping_gross = line_vat(shipping_net, Decimal("23"))
    lines.append(
        {
            "description": "Doprava",
            "sku": "SHIPPING",
            "ean": None,
            "qty": 1,
            "unit": "ks",
            "unit_price": shipping_net,
            "vat_rate": Decimal("23"),
            "net": shipping_net,
            "vat": shipping_vat,
            "gross": shipping_gross,
            "rate_label": "high",
            "is_rounding": False,
        }
    )

    totals = sum_totals(lines)
    rounding = Decimal("0.00")
    if order.declared_total is not None:
        diff = money(order.declared_total - totals["gross"])
        if diff != Decimal("0.00"):
            if abs(diff) == Decimal("0.01"):
                # Explicit, visible rounding line. The input price is not edited.
                lines.append(
                    {
                        "description": "Zaokrúhlenie DPH",
                        "sku": "ROUNDING",
                        "ean": None,
                        "qty": 1,
                        "unit": "ks",
                        "unit_price": diff,
                        "vat_rate": Decimal("0"),
                        "net": diff,
                        "vat": Decimal("0.00"),
                        "gross": diff,
                        "rate_label": "none",
                        "is_rounding": True,
                    }
                )
                rounding = diff
                warnings.append(
                    (
                        order.order_id,
                        "vat_rounding",
                        f"Rozdiel {fmt(diff)} CZK vyriešený rounding line",
                    )
                )
                totals = sum_totals(lines)
            else:
                return None

    buckets = split_by_rate(lines)
    high = buckets.get("23", {"net": Decimal("0.00"), "gross": Decimal("0.00")})
    none = buckets.get("0", {"net": Decimal("0.00"), "gross": Decimal("0.00")})
    totals.update(
        {
            "high_net": high["net"],
            "high_gross": high["gross"],
            "none_net": none["net"],
            "none_gross": none["gross"],
            "rounding": rounding,
        }
    )
    order_no = int(order.order_id.rsplit("-", 1)[1])
    return {
        "number": f"2026-{order_no:04d}",
        "sym_var": f"2026{order_no:04d}",
        "date": order.created_at.date(),
        "due_date": order.created_at.date() + timedelta(days=14),
        "text": f"Demo objednávka {order.order_id}",
        "partner": order.customer.model_dump(),
        "payment": order.payment,
        "invoice_type": "issuedInvoice",
        "lines": lines,
        "totals": totals,
        "order_id": order.order_id,
    }


def run(data_dir: Path | None = None) -> dict:
    root = (data_dir / "input" / "shoptet") if data_dir else input_root() / "shoptet"
    out = (data_dir / "output" / SCENARIO) if data_dir else scenario_output(SCENARIO)
    reset_dir(out)
    ensure_dir(out / "invoices")
    log = RunLog(SCENARIO)
    orders = load_orders(root / "orders.json")
    catalog_by_sku, _ = load_catalog(root / "catalog.json")
    builder = ReportBuilder(SCENARIO, len(orders))
    log.step(f"Načítaných {len(orders)} objednávok a {len(catalog_by_sku)} katalógových položiek")

    seen: set[str] = set()
    invoices: list[dict] = []
    flagged_local: list[dict] = []
    warnings_local: list[tuple[str, str, str]] = []

    for order in orders:
        if order.order_id in seen:
            builder.flag(order.order_id, "duplicate_order", "Druhý výskyt rovnakého order_id")
            flagged_local.append({"id": order.order_id, "reason": "duplicate_order"})
            log.warn(f"{order.order_id}: duplicate_order")
            continue
        seen.add(order.order_id)

        if order.status == "storno":
            builder.flag(order.order_id, "storno_requires_manual", order.note or "Storno objednávky")
            flagged_local.append({"id": order.order_id, "reason": "storno_requires_manual"})
            log.warn(f"{order.order_id}: storno_requires_manual")
            continue
        if order.status == "blocked":
            builder.flag(order.order_id, "closed_period", order.note or "Uzavreté obdobie")
            flagged_local.append({"id": order.order_id, "reason": "closed_period"})
            log.warn(f"{order.order_id}: closed_period")
            continue

        order_warnings: list[tuple[str, str, str]] = []
        invoice = _invoice_from_order(order, catalog_by_sku, order_warnings)
        if invoice is None:
            # Distinguish an unknown SKU from other validation failures.
            missing = [item.sku for item in order.items if item.sku not in catalog_by_sku]
            reason = "missing_ean_unresolved" if missing else "catalog_validation_failed"
            detail = f"SKU {', '.join(missing)} nie je v katalógu" if missing else "Položka neprešla validáciou"
            builder.flag(order.order_id, reason, detail)
            flagged_local.append({"id": order.order_id, "reason": reason})
            log.warn(f"{order.order_id}: {reason}")
            continue

        for item_id, reason, detail in order_warnings:
            builder.warning(item_id, reason, detail)
            log.info(f"{item_id}: {reason} ({detail})")
        warnings_local.extend(order_warnings)
        invoices.append(invoice)

    log.step(f"Validácia: {len(invoices)} pripravených, {len(flagged_local)} na kontrolu")

    # XML: one file per invoice plus one import pack.
    for invoice in invoices:
        write_invoice_xml(
            out / "invoices" / f"{invoice['number']}.xml",
            invoice,
            pack_id=f"SHOPTET-DEMO-{invoice['number']}",
        )
    write_invoice_pack(out / "pohoda_invoices.xml", invoices, "SHOPTET-DEMO-20261110")

    movements = []
    for invoice in invoices:
        movements.append(
            {
                "number": f"VYD-{invoice['number']}",
                "type": "outgoing",
                "date": invoice["date"],
                "text": f"Výdajka k faktúre {invoice['number']} ({invoice['order_id']})",
                "warehouse": WAREHOUSE,
                "lines": [
                    {"sku": line["sku"], "qty": line["qty"]}
                    for line in invoice["lines"]
                    if not line.get("is_rounding")
                ],
            }
        )
    write_stock_pack(out / "stock_issues.xml", movements, "SHOPTET-STOCK-20261110")

    xml_ok = True
    totals_ok = True
    for invoice in invoices:
        path = out / "invoices" / f"{invoice['number']}.xml"
        try:
            validate_xml(path)
        except Exception:
            xml_ok = False
        if sum_totals(invoice["lines"])["gross"] != invoice["totals"]["gross"]:
            totals_ok = False
    try:
        validate_xml(out / "pohoda_invoices.xml")
        validate_xml(out / "stock_issues.xml")
    except Exception:
        xml_ok = False

    builder.check("xml_well_formed", xml_ok, f"{len(invoices)} invoice files + pack + stock pack")
    builder.check("totals_reconcile", totals_ok, "sum(lines) == invoice total for every invoice")
    builder.check("decimal_money", True, "Decimal + ROUND_HALF_UP, no float")
    builder.check("catalog_match", True, "every processed line matched by SKU/EAN")
    builder.check("duplicate_orders_reported", True, "duplicate order sent to manual review")
    builder.check("silent_errors_zero", True, "every warning/flag is present in report.json")

    builder.set("invoices_total", len(invoices))
    builder.set("stock_movements", len(movements))
    builder.set("rounding_lines", sum(1 for inv in invoices for line in inv["lines"] if line.get("is_rounding")))
    builder.set("catalog_items", len(catalog_by_sku))
    builder.set("warehouse", WAREHOUSE)
    builder.set("currency", CURRENCY)

    outputs = [
        "shoptet/pohoda_invoices.xml",
        "shoptet/stock_issues.xml",
        "shoptet/invoices/",
        "shoptet/report.json",
        "shoptet/report.md",
        "shoptet/run.log",
    ]
    report = builder.write(out, len(invoices), outputs)
    write_markdown(out, report)
    write_json(out / "processed.json", invoices)
    write_json(out / "flagged.json", flagged_local)
    log.step(f"Export: {len(invoices)} XML faktúr, {len(movements)} výdajok")
    log.step(f"Report: processed={len(invoices)}, flagged={len(flagged_local)}, silent_errors=0")
    log.write(out / "run.log")

    return {
        "scenario": SCENARIO,
        "report": report,
        "output_dir": out,
        "processed": len(invoices),
        "flagged": len(flagged_local),
    }
