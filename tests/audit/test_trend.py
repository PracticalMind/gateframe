"""Tests for gateframe.audit.trend — ContractTrendAnalyzer."""

import json
from pathlib import Path

import pytest

from gateframe.audit.trend import (
    ContractTrend,
    ContractTrendAnalyzer,
    _direction,
    _ols_slope,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_audit(path: Path, entries: list[dict]) -> None:
    with path.open("w") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


def _entry(
    contract: str,
    passed: bool,
    workflow_id: str,
    ts: str = "2026-04-01T00:00:00+00:00",
) -> dict:
    return {
        "timestamp": ts,
        "contract_name": contract,
        "passed": passed,
        "rules_applied": 1,
        "rules_failed": 0 if passed else 1,
        "failures": [],
        "workflow_id": workflow_id,
        "confidence": 0.9,
    }


# ── OLS helpers ───────────────────────────────────────────────────────────────

class TestOlsSlope:
    def test_increasing(self):
        assert _ols_slope([0.5, 0.7, 0.9]) == pytest.approx(0.2)

    def test_decreasing(self):
        assert _ols_slope([0.9, 0.7, 0.5]) == pytest.approx(-0.2)

    def test_flat(self):
        assert _ols_slope([0.8, 0.8, 0.8]) == pytest.approx(0.0)

    def test_single_returns_zero(self):
        assert _ols_slope([0.7]) == 0.0

    def test_empty_returns_zero(self):
        assert _ols_slope([]) == 0.0


class TestDirection:
    def test_improving(self):
        assert _direction(0.05) == "improving"

    def test_worsening(self):
        assert _direction(-0.05) == "worsening"

    def test_stable_zero(self):
        assert _direction(0.0) == "stable"

    def test_stable_tiny(self):
        assert _direction(0.0001) == "stable"


# ── ContractTrendAnalyzer ─────────────────────────────────────────────────────

class TestContractTrendAnalyzer:
    def test_improving_contract(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        entries = [
            # run-a: 5/10 pass → 50%
            *[_entry("billing", True, "run-a", "2026-04-01T01:00:00+00:00")] * 5,
            *[_entry("billing", False, "run-a", "2026-04-01T01:00:00+00:00")] * 5,
            # run-b: 7/10 → 70%
            *[_entry("billing", True, "run-b", "2026-04-01T02:00:00+00:00")] * 7,
            *[_entry("billing", False, "run-b", "2026-04-01T02:00:00+00:00")] * 3,
            # run-c: 9/10 → 90%
            *[_entry("billing", True, "run-c", "2026-04-01T03:00:00+00:00")] * 9,
            *[_entry("billing", False, "run-c", "2026-04-01T03:00:00+00:00")] * 1,
        ]
        _write_audit(log, entries)
        report = ContractTrendAnalyzer(log).analyze()
        assert not report.any_regression
        ct = report.contract_trends[0]
        assert ct.direction == "improving"
        assert ct.slope > 0

    def test_regressing_contract(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        entries = [
            *[_entry("billing", True, "run-a", "2026-04-01T01:00:00+00:00")] * 9,
            *[_entry("billing", False, "run-a", "2026-04-01T01:00:00+00:00")] * 1,
            *[_entry("billing", True, "run-b", "2026-04-01T02:00:00+00:00")] * 6,
            *[_entry("billing", False, "run-b", "2026-04-01T02:00:00+00:00")] * 4,
            *[_entry("billing", True, "run-c", "2026-04-01T03:00:00+00:00")] * 3,
            *[_entry("billing", False, "run-c", "2026-04-01T03:00:00+00:00")] * 7,
        ]
        _write_audit(log, entries)
        report = ContractTrendAnalyzer(log).analyze()
        assert report.any_regression
        assert len(report.regressions) == 1
        assert report.regressions[0].contract_name == "billing"
        assert report.regressions[0].direction == "worsening"

    def test_entries_without_workflow_id_ignored(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        # Entries without workflow_id should be silently skipped
        entries = [
            {"timestamp": "2026-04-01T01:00:00+00:00", "contract_name": "c", "passed": True,
             "rules_applied": 1, "rules_failed": 0, "failures": []},
        ]
        _write_audit(log, entries)
        report = ContractTrendAnalyzer(log).analyze()
        assert report.contract_trends == []
        assert not report.any_regression

    def test_multiple_contracts(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        entries = [
            # contract A: stable 100% across two runs
            _entry("A", True, "run-1", "2026-04-01T01:00:00+00:00"),
            _entry("A", True, "run-2", "2026-04-01T02:00:00+00:00"),
            # contract B: degrading 100% → 50%
            _entry("B", True, "run-1", "2026-04-01T01:00:00+00:00"),
            *[_entry("B", True, "run-2", "2026-04-01T02:00:00+00:00")] * 1,
            *[_entry("B", False, "run-2", "2026-04-01T02:00:00+00:00")] * 1,
        ]
        _write_audit(log, entries)
        report = ContractTrendAnalyzer(log).analyze()
        names = {ct.contract_name for ct in report.contract_trends}
        assert "A" in names and "B" in names

    def test_window_limits_runs(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        entries = []
        for i in range(10):
            ts = f"2026-04-01T{i:02d}:00:00+00:00"
            entries.append(_entry("c", i < 8, f"run-{i}", ts))
        _write_audit(log, entries)
        report = ContractTrendAnalyzer(log, window=5).analyze()
        ct = report.contract_trends[0]
        # Only the last 5 runs: runs 5-9.  run-8 and run-9 failed → slope negative.
        assert len(ct.run_summaries) == 5

    def test_empty_file_returns_empty_report(self, tmp_path):
        log = tmp_path / "empty.jsonl"
        log.write_text("")
        report = ContractTrendAnalyzer(log).analyze()
        assert report.contract_trends == []
        assert not report.any_regression

    def test_missing_file_returns_empty_report(self, tmp_path):
        log = tmp_path / "missing.jsonl"
        report = ContractTrendAnalyzer(log).analyze()
        assert report.contract_trends == []

    def test_malformed_lines_skipped(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        with log.open("w") as f:
            f.write("not-json\n")
            f.write(json.dumps(_entry("billing", True, "run-1")) + "\n")
            entry = _entry("billing", True, "run-2", "2026-04-01T02:00:00+00:00")
            f.write(json.dumps(entry) + "\n")
        report = ContractTrendAnalyzer(log).analyze()
        assert len(report.contract_trends) == 1

    def test_temporal_ordering(self, tmp_path):
        """Runs must be ordered by first-seen timestamp, not insertion order."""
        log = tmp_path / "audit.jsonl"
        # Write run-b BEFORE run-a in file, but run-a has earlier timestamp
        entries = [
            _entry("c", False, "run-b", "2026-04-01T02:00:00+00:00"),
            _entry("c", True, "run-a", "2026-04-01T01:00:00+00:00"),
        ]
        _write_audit(log, entries)
        report = ContractTrendAnalyzer(log).analyze()
        ct = report.contract_trends[0]
        # run-a should be first (older ts), then run-b
        assert ct.run_summaries[0].workflow_id == "run-a"
        assert ct.run_summaries[1].workflow_id == "run-b"

    def test_report_attributes(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        _write_audit(log, [
            _entry("x", True, "r1"),
            _entry("x", True, "r2", "2026-04-01T02:00:00+00:00"),
        ])
        report = ContractTrendAnalyzer(log, window=15, regression_threshold=0.05).analyze()
        assert report.window == 15
        assert report.regression_threshold == 0.05
        assert isinstance(report.contract_trends[0], ContractTrend)
