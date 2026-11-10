"""End-to-end checks for the three demo scenarios."""

from __future__ import annotations

import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from demo.exporters.pohoda_xml import count_elements, validate_xml
from demo.parsers.mergado_xml import load_feed

NS = {
    "inv": "http://www.stormware.cz/schema/version_2/invoice.xsd",
    "typ": "http://www.stormware.cz/schema/version_2/type.xsd",
    "stk": "http://www.stormware.cz/schema/version_2/stock.xsd",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_shoptet_expected_counts(shoptet_run: dict, data_root: Path) -> None:
    report = shoptet_run["report"]
    assert report["input_count"] == 50
    assert report["processed"] == 46
    assert report["flagged"] == 4
    assert report["silent_errors"] == 0
    assert report["invoices_total"] == 46
    assert report["stock_movements"] == 46
    assert report["rounding_lines"] == 1

    out = data_root / "output" / "shoptet"
    assert len(list((out / "invoices").glob("*.xml"))) == 46
    assert count_elements(out / "pohoda_invoices.xml", "inv", "invoice") == 46
    assert count_elements(out / "stock_issues.xml", "stk", "stock") == 46

    flagged = {(item["id"], item["reason"]) for item in report["flagged_items"]}
    assert flagged == {
        ("DEMO-2026-0007", "duplicate_order"),
        ("DEMO-2026-0033", "storno_requires_manual"),
        ("DEMO-2026-0041", "missing_ean_unresolved"),
        ("DEMO-2026-0044", "closed_period"),
    }
    warning_reasons = Counter(item["reason"] for item in report["warnings"])
    assert warning_reasons == {"missing_ean_enriched": 2, "vat_rounding": 1}
    assert all(check["passed"] for check in report["checks"])
    assert report["audit"]["issues_total"] == report["audit"]["issues_reported"] == 7


def test_shoptet_edge_cases(shoptet_run: dict, data_root: Path) -> None:
    out = data_root / "output" / "shoptet"
    processed = read_json(out / "processed.json")
    flagged = read_json(out / "flagged.json")
    by_number = {item["number"]: item for item in processed}
    by_order = {item["order_id"]: item for item in processed}

    assert "DEMO-2026-0033" not in by_order
    assert "DEMO-2026-0044" not in by_order
    assert "DEMO-2026-0041" not in by_order
    assert "DEMO-2026-0007" in by_order
    assert {item["reason"] for item in flagged} == {
        "duplicate_order",
        "storno_requires_manual",
        "missing_ean_unresolved",
        "closed_period",
    }

    # Missing EANs on orders 12 and 27 are repaired by SKU and reported.
    for number in ("2026-0012", "2026-0027"):
        invoice = by_number[number]
        assert all(line.get("ean") for line in invoice["lines"] if line["sku"] != "SHIPPING")

    # The 0.01 mismatch becomes an explicit rounding line, not a silent edit.
    invoice = by_number["2026-0031"]
    assert Decimal(invoice["totals"]["gross"]) == Decimal("859.41")
    assert Decimal(invoice["totals"]["rounding"]) == Decimal("0.01")
    assert [line for line in invoice["lines"] if line["is_rounding"]][0]["description"] == "Zaokrúhlenie DPH"

    # Every processed invoice reconciles and every line uses a supported rate.
    for invoice in processed:
        line_net = sum((Decimal(line["net"]) for line in invoice["lines"]), Decimal("0.00"))
        line_gross = sum((Decimal(line["gross"]) for line in invoice["lines"]), Decimal("0.00"))
        assert line_net == Decimal(invoice["totals"]["net"])
        assert line_gross == Decimal(invoice["totals"]["gross"])
        assert all(Decimal(line["vat_rate"]) in (Decimal("0"), Decimal("23")) for line in invoice["lines"])


def test_invoices_expected_counts(invoices_run: dict, data_root: Path) -> None:
    report = invoices_run["report"]
    assert report["input_count"] == 10
    assert report["processed"] == 8
    assert report["flagged"] == 2
    assert report["silent_errors"] == 0
    assert report["lines_total"] == 48
    assert report["lines_posted"] == 48
    assert report["lines_extracted"] == 54
    assert report["lines_matched"] == 48
    assert report["lines_unmatched"] == 0
    assert report["matching"] == {"by_sku": 47, "by_ean": 1, "unmatched": 0}

    out = data_root / "output" / "invoices"
    assert len(list((out / "invoices").glob("*.xml"))) == 8
    assert len(list((out / "parsed").glob("*.json"))) == 10
    assert count_elements(out / "pohoda_received_invoices.xml", "inv", "invoice") == 8
    assert count_elements(out / "stock_receipts.xml", "stk", "stock") == 8

    flagged = {(item["id"], item["reason"]) for item in report["flagged_items"]}
    assert flagged == {
        ("invoice_09_scan.pdf", "scan_requires_ocr"),
        ("invoice_10.pdf", "duplicate_invoice"),
    }
    warning_reasons = Counter(item["reason"] for item in report["warnings"])
    assert warning_reasons == {
        "sku_matched_by_ean": 1,
        "price_differs_from_catalog": 1,
        "mixed_vat_rates": 1,
    }
    assert all(check["passed"] for check in report["checks"])


def test_invoices_manual_review_and_matching(data_root: Path) -> None:
    parsed = read_json(data_root / "output" / "invoices" / "parsed.json")
    by_file = {item["source_file"]: item for item in parsed}
    assert len(parsed) == 10

    scan = by_file["invoice_09_scan.pdf"]
    assert scan["status"] == "manual_review"
    assert scan["reason"] == "scan_requires_ocr"
    assert scan["lines"] == []

    duplicate = by_file["invoice_10.pdf"]
    assert duplicate["status"] == "manual_review"
    assert duplicate["reason"] == "duplicate_invoice"
    assert duplicate["duplicate_of"] == "invoice_03.pdf"

    # The unknown supplier SKU was matched by EAN, not silently accepted.
    invoice_05 = by_file["invoice_05.pdf"]
    assert any(line["note"] == "sku_matched_by_ean" for line in invoice_05["lines"])
    assert any(line["sku"] == "SUP-999" and line["catalog_sku"] == "SUP-002" for line in invoice_05["lines"])

    # The supplier price is kept and reported; it is not replaced by catalog price.
    invoice_06 = by_file["invoice_06.pdf"]
    assert invoice_06["status"] == "parsed"
    assert any(Decimal(str(line["unit_price"])) == Decimal("134.90") for line in invoice_06["lines"])


def test_mergado_expected_counts(mergado_run: dict, data_root: Path) -> None:
    report = mergado_run["report"]
    assert report["input_count"] == 1000
    assert report["processed"] == 987
    assert report["flagged"] == 13
    assert report["silent_errors"] == 0
    assert report["zero_stock_products"] == 5
    assert report["category_inferred"] == 1

    out = data_root / "output" / "mergado"
    mapping = read_json(out / "mapping.json")
    assert mapping["input_count"] == 1000
    assert mapping["processed"] == 987
    assert mapping["flagged"] == 13
    assert len(mapping["items"]) == 1000
    assert len({item["master_id"] for item in mapping["items"] if item["master_id"]}) == 987

    reasons = Counter(item["reason"] for item in report["flagged_items"])
    assert reasons == {
        "missing_category": 9,
        "duplicate_ean": 1,
        "unsupported_currency": 2,
        "invalid_price": 1,
    }
    warning_reasons = Counter(item["reason"] for item in report["warnings"])
    assert warning_reasons == {"category_inferred": 1, "zero_stock": 5}
    assert all(check["passed"] for check in report["checks"])

    root = validate_xml(out / "master_feed.xml")
    assert len(root.findall("PRODUCT")) == 987
    with (out / "master_feed.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        assert sum(1 for _ in csv.DictReader(handle)) == 987

    # Flagged source products never leak into the master feed. A duplicate
    # EAN is expected to survive once (the first, valid occurrence).
    master_sources = {node.findtext("SOURCE_ID") for node in root.findall("PRODUCT")}
    flagged_sources = {item["source_id"] for item in mapping["items"] if item["status"] == "flagged"}
    assert master_sources.isdisjoint(flagged_sources)


def test_mergado_inputs_and_master_fields(data_root: Path) -> None:
    input_dir = data_root / "input" / "mergado"
    feeds = [input_dir / "supplier_a.xml", input_dir / "supplier_b.xml", input_dir / "supplier_c.csv"]
    loaded = [item for feed in feeds for item in load_feed(feed)]
    assert len(loaded) == 1000
    assert len({item["source"] for item in loaded}) == 3

    root = validate_xml(data_root / "output" / "mergado" / "master_feed.xml")
    first = root.find("PRODUCT")
    assert first is not None
    for field in ("MASTER_ID", "SKU", "EAN", "NAME", "CATEGORY", "PRICE", "CURRENCY", "STOCK", "VAT"):
        assert first.findtext(field), f"missing {field} in master feed"


def test_invoice_xml_totals_are_consistent(data_root: Path) -> None:
    paths = list((data_root / "output" / "shoptet" / "invoices").glob("*.xml"))
    paths += list((data_root / "output" / "invoices" / "invoices").glob("*.xml"))
    assert len(paths) == 54

    for path in paths:
        root = validate_xml(path)
        summary = root.find(".//inv:invoiceSummary/inv:homeCurrency", NS)
        assert summary is not None
        none_net = Decimal(summary.findtext("typ:priceNone", namespaces=NS))
        high_net = Decimal(summary.findtext("typ:priceHigh", namespaces=NS))
        high_gross = Decimal(summary.findtext("typ:priceHighVAT", namespaces=NS))
        rounding = Decimal(summary.findtext("typ:round/typ:priceRound", namespaces=NS))

        items = root.findall(".//inv:invoiceDetail/inv:invoiceItem", NS)
        assert items, f"no items in {path.name}"
        line_net = sum(
            (Decimal(item.findtext("inv:homeCurrency/typ:price", namespaces=NS)) for item in items),
            Decimal("0.00"),
        )
        line_gross = sum(
            (Decimal(item.findtext("inv:homeCurrency/typ:priceVAT", namespaces=NS)) for item in items),
            Decimal("0.00"),
        )
        assert none_net + high_net == line_net, path.name
        assert none_net + high_gross == line_gross, path.name
        assert high_gross - high_net >= Decimal("0.00")
        assert rounding >= Decimal("0.00")

        for item in items:
            assert item.findtext("inv:homeCurrency/typ:percentVAT", namespaces=NS) in {"0", "23"}
            assert item.findtext("inv:text", namespaces=NS)
            assert item.findtext("inv:code", namespaces=NS)
