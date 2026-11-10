"""Report builder and report.json writer."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..config import SIMULATED_DURATION_MS, SCENARIO_TITLES
from ..models import CheckResult, Flag
from ..util import ensure_dir, now_iso, write_json


class ReportBuilder:
    def __init__(self, scenario: str, input_count: int) -> None:
        self.scenario = scenario
        self.title = SCENARIO_TITLES[scenario]
        self.input_count = input_count
        self.warnings: list[Flag] = []
        self.flagged: list[Flag] = []
        self.checks: list[CheckResult] = []
        self.extra: dict[str, Any] = {}

    def warning(self, item_id: str, reason: str, detail: str = "") -> None:
        self.warnings.append(Flag(id=item_id, reason=reason, detail=detail, severity="warning"))

    def flag(self, item_id: str, reason: str, detail: str = "") -> None:
        self.flagged.append(Flag(id=item_id, reason=reason, detail=detail, severity="flagged"))

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, passed=passed, detail=detail))

    def set(self, key: str, value: Any) -> None:
        self.extra[key] = value

    def _counts(self, items: list[Flag]) -> dict[str, int]:
        return dict(sorted(Counter(item.reason for item in items).items()))

    def build(self, processed: int, outputs: list[str] | None = None) -> dict:
        silent_errors = sum(1 for item in self.warnings + self.flagged if not item.reason)
        report = {
            "scenario": self.scenario,
            "title": self.title,
            "started_at": now_iso(),
            "duration_ms": SIMULATED_DURATION_MS[self.scenario],
            "input_count": self.input_count,
            "processed": processed,
            "flagged": len(self.flagged),
            "silent_errors": silent_errors,
            "warnings": [item.model_dump() for item in self.warnings],
            "flagged_items": [item.model_dump() for item in self.flagged],
            "counts_by_reason": self._counts(self.flagged),
            "warning_counts_by_reason": self._counts(self.warnings),
            "checks": [item.model_dump() for item in self.checks],
            "audit": {
                "issues_total": len(self.warnings) + len(self.flagged),
                "issues_reported": len(self.warnings) + len(self.flagged),
                "silent_errors": silent_errors,
            },
            "outputs": outputs or [],
        }
        report.update(self.extra)
        return report

    def write(self, output_dir: Path, processed: int, outputs: list[str] | None = None) -> dict:
        ensure_dir(output_dir)
        report = self.build(processed, outputs)
        write_json(output_dir / "report.json", report)
        return report
