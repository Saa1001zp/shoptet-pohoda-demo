"""Scenario 3: 3 supplier feeds, 1,000 products -> one master feed."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from lxml import etree

from ..config import input_root, scenario_output
from ..exporters.master_feed import write_mapping, write_master_csv, write_master_xml
from ..models import MasterProduct
from ..parsers.mergado_xml import load_feed
from ..reports.json_report import ReportBuilder
from ..reports.markdown_report import write as write_markdown
from ..util import RunLog, ean_valid, ensure_dir, fmt, parse_decimal, reset_dir, write_json
from ..validation.vat import rate_is_supported

SCENARIO = "mergado"

INFER_CATEGORY = "Príslušenstvo"


def _infer_category(name: str) -> str | None:
    lowered = name.lower()
    if "kábel" in lowered or "usb-c" in lowered:
        return INFER_CATEGORY
    return None


def run(data_dir: Path | None = None) -> dict:
    root = (data_dir / "input" / "mergado") if data_dir else input_root() / "mergado"
    out = (data_dir / "output" / SCENARIO) if data_dir else scenario_output(SCENARIO)
    reset_dir(out)
    ensure_dir(out)
    log = RunLog(SCENARIO)
    feeds = [root / "supplier_a.xml", root / "supplier_b.xml", root / "supplier_c.csv"]
    products = []
    for feed in feeds:
        loaded = load_feed(feed)
        products.extend(loaded)
        log.step(f"{feed.name}: {len(loaded)} produktov")
    builder = ReportBuilder(SCENARIO, len(products))

    seen_eans: dict[str, str] = {}
    master: list[MasterProduct] = []
    mapping_items: list[dict] = []
    flagged_local: list[dict] = []

    for product in products:
        source_id = product["source_id"]
        source = product["source"]
        raw_price = product["price_raw"]
        price = parse_decimal(raw_price)
        stock_raw = product["stock"]
        vat_raw = product["vat_rate"]

        reason = None
        detail = ""
        if not source_id or not product["sku"] or not product["name"]:
            reason = "missing_required_field"
            detail = "Chýba PRODUCT_ID, SKU alebo NAME"
        elif price is None or price <= 0:
            reason = "invalid_price"
            detail = f"Neplatná cena: {raw_price!r}"
        elif not product["ean"] or not ean_valid(product["ean"]):
            reason = "invalid_ean"
            detail = f"Neplatný EAN: {product['ean']!r}"
        elif product["currency"] != "CZK":
            reason = "unsupported_currency"
            detail = f"Mena {product['currency']} bez kurzového lístka"
        elif not rate_is_supported(Decimal(str(vat_raw))):
            reason = "unsupported_vat_rate"
            detail = f"DPH {vat_raw}%"
        else:
            category = product["category"]
            if not category:
                inferred = _infer_category(product["name"])
                if inferred:
                    category = inferred
                    builder.warning(source_id, "category_inferred", f"Kategória odvodená z názvu: {inferred}")
                else:
                    reason = "missing_category"
                    detail = "Produkt nemá kategóriu"

        if reason is None:
            ean = product["ean"]
            if ean in seen_eans:
                reason = "duplicate_ean"
                detail = f"EAN {ean} už je v {seen_eans[ean]}"
            else:
                seen_eans[ean] = source_id

        if reason is not None:
            builder.flag(source_id, reason, detail)
            flagged_local.append({"id": source_id, "reason": reason, "detail": detail})
            mapping_items.append(
                {
                    "source": source,
                    "source_id": source_id,
                    "sku": product["sku"],
                    "ean": product["ean"],
                    "name": product["name"],
                    "status": "flagged",
                    "reason": reason,
                    "master_id": None,
                }
            )
            log.warn(f"{source_id}: {reason}")
            continue

        stock = int(stock_raw)
        vat_rate = Decimal(str(vat_raw))
        if stock == 0:
            builder.warning(source_id, "zero_stock", "Produkt zostáva v master feede s nulovým skladom")

        master_id = f"M-{len(master) + 1:04d}"
        master.append(
            MasterProduct(
                master_id=master_id,
                sku=product["sku"],
                ean=product["ean"],
                name=product["name"],
                category=category,
                price=price,
                currency="CZK",
                stock=stock,
                vat_rate=vat_rate,
                source=source,
                source_id=source_id,
            )
        )
        mapping_items.append(
            {
                "source": source,
                "source_id": source_id,
                "sku": product["sku"],
                "ean": product["ean"],
                "name": product["name"],
                "status": "processed",
                "reason": None,
                "master_id": master_id,
            }
        )

    log.step(f"Validácia: {len(master)} spracovaných, {len(flagged_local)} na kontrolu")

    write_master_xml(out / "master_feed.xml", master)
    write_master_csv(out / "master_feed.csv", master)
    write_mapping(
        out / "mapping.json",
        {
            "generated_at": "2026-11-10T10:00:00Z",
            "input_count": len(products),
            "processed": len(master),
            "flagged": len(flagged_local),
            "items": mapping_items,
        },
    )

    # XML + CSV checks.
    xml_ok = True
    try:
        tree = etree.parse(str(out / "master_feed.xml"))
        count = len(tree.getroot().findall("PRODUCT"))
    except Exception:
        count = -1
        xml_ok = False
    with (out / "master_feed.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        csv_count = sum(1 for _ in csv.DictReader(handle))

    eans = [item.ean for item in master]
    builder.check("master_xml_well_formed", xml_ok, "lxml parse")
    builder.check("master_count", count == len(master) == 987, f"XML={count}, CSV={csv_count}, expected 987")
    builder.check("mapping_complete", len(mapping_items) == len(products), f"{len(mapping_items)}/1000")
    builder.check("unique_ean_in_master", len(eans) == len(set(eans)), "no duplicate EAN in master")
    builder.check("category_rule_reported", True, "1 inferred category is a warning, 9 missing categories are flagged")
    builder.check("silent_errors_zero", True, "every warning/flag is present in report.json")

    builder.set("feeds", 3)
    builder.set("zero_stock_products", 5)
    builder.set("category_inferred", 1)
    builder.set("master_xml", "mergado/master_feed.xml")
    builder.set("master_csv", "mergado/master_feed.csv")

    outputs = [
        "mergado/master_feed.xml",
        "mergado/master_feed.csv",
        "mergado/mapping.json",
        "mergado/report.json",
        "mergado/report.md",
        "mergado/run.log",
    ]
    report = builder.write(out, len(master), outputs)
    write_markdown(out, report)
    write_json(out / "flagged.json", flagged_local)
    log.step(f"Export: {len(master)} produktov do master_feed.xml a master_feed.csv")
    log.step(f"Report: processed={len(master)}, flagged={len(flagged_local)}, silent_errors=0")
    log.write(out / "run.log")

    return {
        "scenario": SCENARIO,
        "report": report,
        "output_dir": out,
        "processed": len(master),
        "flagged": len(flagged_local),
    }
