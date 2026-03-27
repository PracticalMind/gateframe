from gateframe.audit.log import AuditEntry, AuditLog
from gateframe.core.contract import ValidationResult
from gateframe.core.failure import FailureMode, FailureResult


def _make_result(passed: bool = True, **overrides: object) -> ValidationResult:
    defaults: dict = {
        "passed": passed,
        "contract_name": "test_contract",
        "rules_applied": 1,
        "rules_failed": 0 if passed else 1,
        "failures": [] if passed else [
            FailureResult(
                rule_name="rule_a",
                failure_mode=FailureMode.HARD_FAIL,
                message="rule_a: output rejected.",
            )
        ],
    }
    defaults.update(overrides)
    return ValidationResult(**defaults)


class TestAuditLog:

    def test_record_adds_entry(self) -> None:
        log = AuditLog()
        log.record(_make_result())
        assert len(log.entries) == 1

    def test_multiple_records(self) -> None:
        log = AuditLog()
        log.record(_make_result())
        log.record(_make_result(passed=False))
        assert len(log.entries) == 2

    def test_clear_removes_entries(self) -> None:
        log = AuditLog()
        log.record(_make_result())
        log.clear()
        assert len(log.entries) == 0

    def test_entries_returns_copy(self) -> None:
        log = AuditLog()
        log.record(_make_result())
        entries = log.entries
        entries.clear()
        assert len(log.entries) == 1


class TestAuditEntry:

    def test_entry_structure(self) -> None:
        result = _make_result(passed=False)
        entry = AuditEntry(result)
        assert entry.contract_name == "test_contract"
        assert entry.passed is False
        assert entry.rules_applied == 1
        assert entry.rules_failed == 1

    def test_entry_has_timestamp(self) -> None:
        entry = AuditEntry(_make_result())
        assert entry.timestamp is not None
        assert entry.timestamp.tzinfo is not None

    def test_entry_failures_serialized(self) -> None:
        entry = AuditEntry(_make_result(passed=False))
        assert len(entry.failures) == 1
        assert entry.failures[0]["rule_name"] == "rule_a"
        assert entry.failures[0]["failure_mode"] == "hard_fail"

    def test_to_dict(self) -> None:
        entry = AuditEntry(_make_result())
        data = entry.to_dict()
        assert "timestamp" in data
        assert "contract_name" in data
        assert "passed" in data
        assert "rules_applied" in data
        assert "rules_failed" in data
        assert "failures" in data
