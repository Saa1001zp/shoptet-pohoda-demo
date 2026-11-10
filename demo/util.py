"""Small shared helpers: money, JSON, deterministic files and logging."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from .config import DEMO_NOW

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str | float) -> Decimal:
    """Quantize to haléře with commercial rounding. Floats never enter the core."""
    if isinstance(value, float):
        value = str(value)
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def dec(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def parse_decimal(raw: str | None) -> Decimal | None:
    """Parse CZK/EUR price strings from feeds; returns None when unusable."""
    if raw is None:
        return None
    text = str(raw).strip().replace("\u00a0", "").replace(" ", "")
    text = text.replace("Kč", "").replace("CZK", "").replace("EUR", "").replace("€", "")
    if "," in text and "." in text:
        # 1.234,56 -> 1234.56
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite():
        return None
    return value


def vat_amount(net: Decimal, rate: Decimal) -> Decimal:
    return money(net * rate / Decimal("100"))


def gross_amount(net: Decimal, rate: Decimal) -> Decimal:
    return money(net + vat_amount(net, rate))


def fmt(value: Decimal | int | str, places: int = 2) -> str:
    if isinstance(value, Decimal):
        return f"{value:.{places}f}"
    return f"{Decimal(str(value)):.{places}f}"


def fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def fmt_date(value: date | datetime) -> str:
    return value.strftime("%Y-%m-%d")


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False, default=_json_default)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def safe_filename(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return cleaned or "file"


def ean13(seed_number: int) -> str:
    """Build a valid-looking EAN-13 with a real check digit."""
    body = f"200{seed_number:09d}"[:12]
    digits = [int(ch) for ch in body]
    checksum = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    return body + str(checksum)


def ean_valid(ean: str | None) -> bool:
    if not ean or not ean.isdigit() or len(ean) != 13:
        return False
    digits = [int(ch) for ch in ean]
    return (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12])) % 10) % 10 == digits[-1]


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8", newline="\n")


def fixed_zip(path: Path, entries: Iterable[tuple[Path, str]]) -> None:
    """Create a reproducible ZIP with fixed member timestamps."""
    ensure_dir(path.parent)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, arcname in sorted(entries, key=lambda item: item[1]):
            info = zipfile.ZipInfo(arcname.replace("\\", "/"), date_time=(2026, 11, 10, 10, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())


class RunLog:
    """Deterministic step log. No wall-clock timestamps on purpose."""

    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.lines: list[str] = [f"$ python -m demo run --scenario {scenario}"]

    def step(self, message: str) -> None:
        self.lines.append(f"[{len(self.lines):02d}] {message}")

    def info(self, message: str) -> None:
        self.lines.append(f"     {message}")

    def warn(self, message: str) -> None:
        self.lines.append(f"WARN {message}")

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"

    def write(self, path: Path) -> None:
        write_text(path, self.render())


def now_iso() -> str:
    return iso_z(DEMO_NOW)
