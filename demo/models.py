"""Pydantic models for all demo inputs and intermediate documents."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Customer(StrictModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    zip: str = Field(min_length=1)
    country: str = "CZ"


class OrderItem(StrictModel):
    sku: str = Field(min_length=1)
    ean: str | None = None
    name: str = Field(min_length=1)
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0)


class Order(StrictModel):
    order_id: str = Field(min_length=1)
    created_at: datetime
    currency: Literal["CZK"] = "CZK"
    customer: Customer
    items: list[OrderItem] = Field(min_length=1)
    shipping: Decimal = Field(ge=0)
    payment: str = "card"
    status: str = "open"
    note: str | None = None
    declared_total: Decimal | None = None


class CatalogItem(StrictModel):
    sku: str = Field(min_length=1)
    ean: str
    name: str = Field(min_length=1)
    unit: str = "ks"
    price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0)
    stock: int = Field(ge=0)


class InvoiceLine(StrictModel):
    line_no: int = Field(gt=0)
    sku: str = Field(min_length=1)
    ean: str | None = None
    description: str = Field(min_length=1)
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0)


class SupplierInvoice(StrictModel):
    invoice_number: str = Field(min_length=1)
    supplier: str = Field(min_length=1)
    issue_date: date
    due_date: date
    currency: Literal["CZK"] = "CZK"
    lines: list[InvoiceLine] = Field(min_length=1)
    total: Decimal = Field(ge=0)


class ParsedInvoiceLine(StrictModel):
    line_no: int
    sku: str
    ean: str | None = None
    description: str
    qty: int
    unit_price: Decimal
    vat_rate: Decimal
    net: Decimal
    vat: Decimal
    gross: Decimal
    catalog_sku: str | None = None
    matched: bool = False
    match_method: str | None = None
    note: str | None = None


class ParsedInvoice(StrictModel):
    source_file: str
    invoice_number: str | None = None
    supplier: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    declared_total: Decimal | None = None
    lines: list[ParsedInvoiceLine] = Field(default_factory=list)
    computed_total: Decimal | None = None
    status: Literal["parsed", "manual_review"] = "parsed"
    reason: str | None = None
    duplicate_of: str | None = None


class FeedProduct(StrictModel):
    source: str
    source_id: str
    sku: str
    ean: str | None = None
    name: str
    category: str | None = None
    price: Decimal | None = None
    currency: str = "CZK"
    stock: int = 0
    vat_rate: Decimal = Decimal("23")
    raw_price: str | None = None


class MasterProduct(StrictModel):
    master_id: str
    sku: str
    ean: str
    name: str
    category: str
    price: Decimal
    currency: str = "CZK"
    stock: int
    vat_rate: Decimal = Decimal("23")
    source: str
    source_id: str


class Flag(StrictModel):
    id: str
    reason: str
    detail: str = ""
    severity: Literal["flagged", "warning"] = "flagged"


class CheckResult(StrictModel):
    name: str
    passed: bool
    detail: str = ""
