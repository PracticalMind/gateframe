import json
from pathlib import Path

import pytest

from gateframe.audit.exporters import AuditExporter, JsonFileExporter
from gateframe.audit.log import AuditEntry
from gateframe.core.contract import ValidationResult
from gateframe.core.failure import FailureMode, FailureResult


def _make_entry(passed: bool = True) -> AuditEntry:
    failures = (
        []
        if passed
        else [
            FailureResult(
                rule_name="rule_a",
                failure_mode=FailureMode.HARD_FAIL,
                message="rule_a: rejected.",
            )
        ]
    )
    result = ValidationResult(
        passed=passed,
        contract_name="test_contract",
        failures=failures,
        rules_applied=1,
        rules_failed=0 if passed else 1,
    )
    return AuditEntry(result)


class TestAuditExporterABC:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            AuditExporter()  # type: ignore[abstract]


class TestJsonFileExporter:
    def test_export_writes_json_line(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        exporter = JsonFileExporter(path)
        exporter.export(_make_entry())
        exporter.flush()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["contract_name"] == "test_contract"
        exporter.shutdown()

    def test_multiple_exports(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        exporter = JsonFileExporter(path)
        exporter.export(_make_entry(passed=True))
        exporter.export(_make_entry(passed=False))
        exporter.flush()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        exporter.shutdown()

    def test_flush_writes_to_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        exporter = JsonFileExporter(path)
        exporter.export(_make_entry())
        exporter.flush()
        assert path.exists()
        assert len(path.read_text().strip()) > 0
        exporter.shutdown()

    def test_shutdown_closes_handle(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        exporter = JsonFileExporter(path)
        exporter.export(_make_entry())
        exporter.shutdown()
        assert exporter._handle.closed

    def test_entry_with_failures(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        exporter = JsonFileExporter(path)
        exporter.export(_make_entry(passed=False))
        exporter.flush()
        data = json.loads(path.read_text().strip())
        assert data["passed"] is False
        assert len(data["failures"]) == 1
        assert data["failures"][0]["rule_name"] == "rule_a"
        exporter.shutdown()


class TestOtlpExporter:
    def test_import_error_without_opentelemetry(self) -> None:
        # OtlpExporter should raise ImportError if opentelemetry is not installed
        # We can't reliably test this without uninstalling the package,
        # so we test the _require_opentelemetry function directly
        from gateframe.audit.exporters import _require_opentelemetry

        # This will either pass (if otel is installed) or raise ImportError
        # In CI without otel, this validates the error message
        try:
            _require_opentelemetry()
        except ImportError as exc:
            assert "pip install gateframe[otlp]" in str(exc)
