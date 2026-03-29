import json
from pathlib import Path

import pytest

from gateframe.cli.replay import _load_entries, _print_entry, _print_summary, run_replay

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadEntries:
    def test_json_lines_format(self) -> None:
        entries = _load_entries(FIXTURES / "sample_audit.jsonl")
        assert len(entries) == 3
        assert entries[0]["contract_name"] == "classification"

    def test_json_array_format(self, tmp_path: Path) -> None:
        data = [{"contract_name": "test", "passed": True}]
        path = tmp_path / "audit.json"
        path.write_text(json.dumps(data))
        entries = _load_entries(path)
        assert len(entries) == 1

    def test_single_json_object(self, tmp_path: Path) -> None:
        data = {"contract_name": "test", "passed": True}
        path = tmp_path / "audit.json"
        path.write_text(json.dumps(data))
        entries = _load_entries(path)
        assert len(entries) == 1

    def test_skips_invalid_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        path.write_text('{"valid": true}\nnot json\n{"also_valid": true}\n')
        entries = _load_entries(path)
        assert len(entries) == 2


class TestRunReplay:
    def test_valid_audit_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        run_replay(str(FIXTURES / "sample_audit.jsonl"))
        output = capsys.readouterr().out
        assert "3 entries" in output
        assert "classification" in output
        assert "action_plan" in output
        assert "FAIL" in output

    def test_nonexistent_file_exits(self) -> None:
        with pytest.raises(SystemExit):
            run_replay("nonexistent.jsonl")


class TestPrintSummary:
    def test_summary_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        entries = [{"passed": True}, {"passed": False}, {"passed": True}]
        _print_summary(entries)
        output = capsys.readouterr().out
        assert "3 entries" in output
        assert "2 passed" in output
        assert "1 failed" in output


class TestPrintEntry:
    def test_passed_entry(self, capsys: pytest.CaptureFixture[str]) -> None:
        entry = {
            "contract_name": "test",
            "passed": True,
            "timestamp": "2026-01-01T00:00:00",
            "rules_applied": 2,
            "rules_failed": 0,
            "failures": [],
        }
        _print_entry(0, entry)
        output = capsys.readouterr().out
        assert "PASS" in output

    def test_failed_entry_with_workflow(self, capsys: pytest.CaptureFixture[str]) -> None:
        entry = {
            "contract_name": "test",
            "passed": False,
            "timestamp": "2026-01-01T00:00:00",
            "rules_applied": 2,
            "rules_failed": 1,
            "failures": [
                {"rule_name": "rule_a", "failure_mode": "hard_fail", "message": "rejected"}
            ],
            "workflow_id": "wf1",
            "confidence": 0.85,
        }
        _print_entry(0, entry)
        output = capsys.readouterr().out
        assert "FAIL" in output
        assert "wf1" in output
        assert "0.85" in output
        assert "rejected" in output
