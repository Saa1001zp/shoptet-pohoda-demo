"""Fixed demo constants and paths.

The demo clock is deliberately frozen so two runs produce byte-identical
reports. See LIMITATIONS.md.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SEED = 20261110
DEMO_NOW = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
DEMO_DATE = date(2026, 11, 10)
VAT_RATE = Decimal("23")
CURRENCY = "CZK"
WAREHOUSE = "SKLAD-DEMO"

# Deterministic, simulated durations used in report.json. Real wall-clock
# time is printed to the terminal but never written to reports, otherwise
# reports would differ between runs.
SIMULATED_DURATION_MS = {
    "shoptet": 12_000,
    "invoices": 9_000,
    "mergado": 7_000,
}

SCENARIO_TITLES = {
    "shoptet": "Shoptet → Pohoda",
    "invoices": "Dodávateľské faktúry → Pohoda",
    "mergado": "Mergado / XML feed",
}

# Synthetic companies. No IČO, DIČ or VAT ID anywhere on purpose.
DEMO_SHOP = "DemoShop s.r.o."
DEMO_SUPPLIERS = [
    "Demo Dodávateľ Alfa s.r.o.",
    "Demo Dodávateľ Beta s.r.o.",
    "Demo Dodávateľ Gama s.r.o.",
]


def data_root() -> Path:
    """Return the data directory, allowing tests to isolate it."""
    override = os.environ.get("DEMO_DATA_DIR")
    return Path(override).resolve() if override else REPO_ROOT / "data"


def input_root() -> Path:
    return data_root() / "input"


def output_root() -> Path:
    return data_root() / "output"


def assets_root() -> Path:
    return REPO_ROOT / "assets"


def handoff_root() -> Path:
    return REPO_ROOT / "handoff"


def scenario_output(name: str) -> Path:
    return output_root() / name
