"""Shared fixtures. All data is generated into a temporary directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from demo.cli import generate
from demo.scenarios import invoices_to_pohoda, mergado_feed, shoptet_to_pohoda


@pytest.fixture(scope="session")
def data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("demo-data")
    generate(root)
    return root


@pytest.fixture(scope="session")
def shoptet_run(data_root: Path) -> dict:
    return shoptet_to_pohoda.run(data_root)


@pytest.fixture(scope="session")
def invoices_run(data_root: Path) -> dict:
    return invoices_to_pohoda.run(data_root)


@pytest.fixture(scope="session")
def mergado_run(data_root: Path) -> dict:
    return mergado_feed.run(data_root)


@pytest.fixture(scope="session")
def all_runs(shoptet_run: dict, invoices_run: dict, mergado_run: dict) -> dict[str, dict]:
    return {"shoptet": shoptet_run, "invoices": invoices_run, "mergado": mergado_run}
