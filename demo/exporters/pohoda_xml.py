"""Write a documented subset of Pohoda XML.

The demo never talks to Pohoda. The subset is intentionally small, uses only
public element names and is checked for well-formedness, required fields and
internal totals by the tests. It is not claimed to be XSD-valid against a
particular Pohoda release; see LIMITATIONS.md.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from lxml import etree

from ..util import ensure_dir, fmt, write_text

NS = {
    "dat": "http://www.stormware.cz/schema/version_2/data.xsd",
    "inv": "http://www.stormware.cz/schema/version_2/invoice.xsd",
    "typ": "http://www.stormware.cz/schema/version_2/type.xsd",
    "stk": "http://www.stormware.cz/schema/version_2/stock.xsd",
}


def _q(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def _el(parent: etree._Element, prefix: str, tag: str, text: str | None = None, **attrs: str) -> etree._Element:
    node = etree.SubElement(parent, _q(prefix, tag), **attrs)
    if text is not None:
        node.text = text
    return node


def _address(parent: etree._Element, data: dict) -> None:
    address = _el(parent, "typ", "address")
    _el(address, "typ", "name", data.get("name", ""))
    _el(address, "typ", "street", data.get("street", ""))
    _el(address, "typ", "city", data.get("city", ""))
    _el(address, "typ", "zip", data.get("zip", ""))
    country = _el(address, "typ", "country")
    _el(country, "typ", "ids", data.get("country", "CZ"))
    if data.get("email"):
        _el(address, "typ", "email", data["email"])


def _data_pack(pack_id: str) -> etree._Element:
    root = etree.Element(
        _q("dat", "dataPack"),
        nsmap=NS,
        version="2.0",
        id=pack_id,
        application="shoptet-pohoda-demo",
        note="Syntetické dáta – DEMO. Nie je reálne pripojenie k Pohode.",
    )
    return root


def _invoice_element(parent: etree._Element, invoice: dict) -> etree._Element:
    item = _el(parent, "dat", "dataPackItem", id=invoice["number"], version="2.0")
    inv = _el(item, "inv", "invoice", version="2.0")
    header = _el(inv, "inv", "invoiceHeader")
    _el(header, "inv", "invoiceType", invoice.get("invoice_type", "issuedInvoice"))
    number = _el(header, "inv", "number")
    _el(number, "typ", "numberRequested", invoice["number"])
    _el(header, "inv", "symVar", invoice["sym_var"])
    _el(header, "inv", "date", invoice["date"].isoformat())
    _el(header, "inv", "dateDue", invoice["due_date"].isoformat())
    _el(header, "inv", "text", invoice["text"])
    partner = _el(header, "inv", "partnerIdentity")
    _address(partner, invoice["partner"])
    payment = _el(header, "inv", "paymentType")
    _el(payment, "typ", "ids", invoice.get("payment", "card"))
    _el(header, "inv", "note", "DEMO · syntetické dáta")

    detail = _el(inv, "inv", "invoiceDetail")
    for line in invoice["lines"]:
        row = _el(detail, "inv", "invoiceItem")
        _el(row, "inv", "quantity", str(line["qty"]))
        _el(row, "inv", "unit", line.get("unit", "ks"))
        _el(row, "inv", "text", line["description"])
        _el(row, "inv", "code", line["sku"])
        home = _el(row, "inv", "homeCurrency")
        _el(home, "typ", "unitPrice", fmt(line["unit_price"]))
        _el(home, "typ", "price", fmt(line["net"]))
        _el(home, "typ", "priceVAT", fmt(line["gross"]))
        _el(home, "typ", "rateVAT", line.get("rate_label", "high"))
        _el(home, "typ", "percentVAT", f"{line['vat_rate']:g}")
        if not line.get("is_rounding"):
            stock = _el(row, "inv", "stockItem")
            stock_item = _el(stock, "typ", "stockItem")
            _el(stock_item, "typ", "ids", line["sku"])

    summary = _el(inv, "inv", "invoiceSummary")
    home = _el(summary, "inv", "homeCurrency")
    _el(home, "typ", "priceNone", fmt(invoice["totals"]["none_net"]))
    _el(home, "typ", "priceHigh", fmt(invoice["totals"]["high_net"]))
    _el(home, "typ", "priceHighVAT", fmt(invoice["totals"]["high_gross"]))
    round_node = _el(home, "typ", "round")
    _el(round_node, "typ", "priceRound", fmt(invoice["totals"]["rounding"]))
    return item


def write_invoice_xml(path: Path, invoice: dict, pack_id: str) -> None:
    ensure_dir(path.parent)
    root = _data_pack(pack_id)
    _invoice_element(root, invoice)
    path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def write_invoice_pack(path: Path, invoices: list[dict], pack_id: str) -> None:
    ensure_dir(path.parent)
    root = _data_pack(pack_id)
    for invoice in invoices:
        _invoice_element(root, invoice)
    path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def _stock_element(parent: etree._Element, movement: dict) -> etree._Element:
    item = _el(parent, "dat", "dataPackItem", id=movement["number"], version="2.0")
    stock = _el(item, "stk", "stock", version="2.0")
    header = _el(stock, "stk", "stockHeader")
    _el(header, "stk", "stockType", movement["type"])
    number = _el(header, "stk", "number")
    _el(number, "typ", "numberRequested", movement["number"])
    _el(header, "stk", "date", movement["date"].isoformat())
    _el(header, "stk", "text", movement["text"])
    store = _el(header, "stk", "store")
    _el(store, "typ", "ids", movement["warehouse"])
    _el(header, "stk", "note", "DEMO · syntetické dáta")

    detail = _el(stock, "stk", "stockDetail")
    for line in movement["lines"]:
        row = _el(detail, "stk", "stockItem")
        _el(row, "stk", "quantity", str(line["qty"]))
        stock_item = _el(row, "stk", "stockItem")
        _el(stock_item, "typ", "ids", line["sku"])
    return item


def write_stock_pack(path: Path, movements: list[dict], pack_id: str) -> None:
    ensure_dir(path.parent)
    root = _data_pack(pack_id)
    for movement in movements:
        _stock_element(root, movement)
    path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def validate_xml(path: Path) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)
    return etree.parse(str(path), parser).getroot()


def count_elements(path: Path, prefix: str, tag: str) -> int:
    root = validate_xml(path)
    return len(root.findall(f".//{_q(prefix, tag)}"))


def required_texts(path: Path, prefix: str, tag: str) -> list[str]:
    root = validate_xml(path)
    return [(node.text or "") for node in root.findall(f".//{_q(prefix, tag)}")]
