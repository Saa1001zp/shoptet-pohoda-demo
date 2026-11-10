"""Repository-level checks: determinism, reports, safety and the CLI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from demo.cli import generate, main
from demo.scenarios import shoptet_to_pohoda

ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_readme_and_limitations_exist() -> None:
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "LIMITATIONS.md").is_file()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python -m demo run-all" in readme
    assert "46" in readme and "987" in readme


def test_input_generation_is_deterministic(data_root: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    generate(other)
    assert tree_hashes(data_root / "input") == tree_hashes(other / "input")


def test_shoptet_output_is_deterministic(tmp_path: Path) -> None:
    work = tmp_path / "work"
    generate(work)
    shoptet_to_pohoda.run(work)
    first = tree_hashes(work / "output" / "shoptet")
    shoptet_to_pohoda.run(work)
    second = tree_hashes(work / "output" / "shoptet")
    assert first == second
    assert "report.json" in first


@pytest.mark.parametrize(
    ("scenario", "input_line", "processed", "flagged"),
    [
        ("shoptet", "- Vstup: 50 objednávok", "46", "4"),
        ("invoices", "- Vstup: 10 faktúr", "8", "2"),
        ("mergado", "- Vstup: 1 000 produktov", "987", "13"),
    ],
)
def test_markdown_reports_use_actual_numbers(
    data_root: Path, all_runs: dict[str, dict], scenario: str, input_line: str, processed: str, flagged: str
) -> None:
    assert scenario in all_runs
    out = data_root / "output" / scenario
    text = (out / "report.md").read_text(encoding="utf-8")
    report = read_json(out / "report.json")
    assert input_line in text
    assert f"- Spracované: {processed}" in text
    assert f"- Na kontrolu: {flagged}" in text
    assert "- Ticho prejdené chyby: 0" in text
    assert "0 errors" not in text.lower()
    assert report["silent_errors"] == 0
    assert report["audit"]["issues_total"] == report["audit"]["issues_reported"]
    assert all(check["passed"] for check in report["checks"])


def test_run_all_cleans_output_and_returns_zero(tmp_path: Path) -> None:
    root = tmp_path / "cli"
    sentinel = root / "output" / "sentinel.txt"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("must be removed", encoding="utf-8")

    assert main(["run-all", "--data-dir", str(root)]) == 0
    assert not sentinel.exists()
    summary = read_json(root / "output" / "summary.json")
    assert [item["scenario"] for item in summary["scenarios"]] == ["shoptet", "invoices", "mergado"]
    assert all(item["silent_errors"] == 0 for item in summary["scenarios"])
    assert [(item["input_count"], item["processed"], item["flagged"]) for item in summary["scenarios"]] == [
        (50, 46, 4),
        (10, 8, 2),
        (1000, 987, 13),
    ]


def test_no_network_calls_in_source() -> None:
    forbidden = (
        "import requests",
        "import httpx",
        "import aiohttp",
        "import urllib",
        "from urllib",
        "urlopen(",
        "http.client",
        "socket.socket",
    )
    sources = [path for path in (ROOT / "demo").rglob("*.py") if "tests" not in path.parts]
    assert sources
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path} contains {marker}"

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for package in ("requests", "httpx", "aiohttp", "urllib3"):
        assert package not in pyproject


def test_no_real_company_identifiers_or_emails(data_root: Path) -> None:
    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key.lower()
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    for path in (data_root / "input").rglob("*.json"):
        payload = read_json(path)
        assert not ({"ico", "dic", "vat_id", "tax_id"} & set(keys(payload))), path

    orders = read_json(data_root / "input" / "shoptet" / "orders.json")
    assert len(orders) == 50
    for order in orders:
        assert order["customer"]["email"].endswith("@example.com")
        assert order["customer"]["name"].startswith("Demo ")

    manifest = read_json(data_root / "input" / "invoices" / "manifest.json")
    assert len(manifest) == 10
    assert all(item["supplier"].startswith("Demo ") for item in manifest)
    assert all(item["currency"] == "CZK" for item in manifest)


def test_generated_xml_has_no_real_identifiers(data_root: Path) -> None:
    for path in (data_root / "output").rglob("*.xml"):
        text = path.read_text(encoding="utf-8")
        assert "IČO" not in text
        assert "DIČ" not in text
        assert "ico=" not in text.lower()
        assert "dic=" not in text.lower()


def test_source_has_no_float_money_arithmetic() -> None:
    # Floats may only be stringified at the util boundary; monetary modules
    # must not construct Decimal from a float.
    offenders = []
    for path in (ROOT / "demo").rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "Decimal(float" in text or "Decimal(0." in text:
            offenders.append(path)
    assert not offenders
