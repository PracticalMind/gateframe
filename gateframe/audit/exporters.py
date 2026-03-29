from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from gateframe.audit.log import AuditEntry

logger = structlog.get_logger()


class AuditExporter(ABC):
    @abstractmethod
    def export(self, entry: AuditEntry) -> None: ...

    @abstractmethod
    def flush(self) -> None: ...

    def shutdown(self) -> None:  # noqa: B027
        pass


class JsonFileExporter(AuditExporter):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._handle = open(self._path, "a")  # noqa: SIM115

    def export(self, entry: AuditEntry) -> None:
        line = json.dumps(entry.to_dict(), default=str)
        self._handle.write(line + "\n")

    def flush(self) -> None:
        self._handle.flush()

    def shutdown(self) -> None:
        self._handle.close()


def _require_opentelemetry() -> None:
    try:
        import opentelemetry  # noqa: F401
    except ImportError:
        raise ImportError(
            "opentelemetry is required for OtlpExporter. "
            "Install it with: pip install gateframe[otlp]"
        ) from None


class OtlpExporter(AuditExporter):
    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        *,
        insecure: bool = True,
        service_name: str = "gateframe",
    ) -> None:
        _require_opentelemetry()

        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        self._provider = LoggerProvider(resource=resource)
        exporter = OTLPLogExporter(endpoint=endpoint, insecure=insecure)
        self._provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        self._logger = self._provider.get_logger("gateframe.audit")

    def export(self, entry: AuditEntry) -> None:
        from opentelemetry.sdk._logs import LogRecord

        severity = self._resolve_severity(entry)
        attributes: dict[str, Any] = {
            "contract_name": entry.contract_name,
            "passed": entry.passed,
            "rules_applied": entry.rules_applied,
            "rules_failed": entry.rules_failed,
        }
        if entry.workflow_id is not None:
            attributes["workflow_id"] = entry.workflow_id
        if entry.confidence is not None:
            attributes["confidence"] = entry.confidence

        record = LogRecord(
            body=json.dumps(entry.to_dict(), default=str),
            severity_number=severity,
            attributes=attributes,
        )
        self._logger.emit(record)

    def flush(self) -> None:
        self._provider.force_flush()

    def shutdown(self) -> None:
        self._provider.shutdown()

    @staticmethod
    def _resolve_severity(entry: AuditEntry) -> int:
        import logging

        has_hard = any(f.get("failure_mode") == "hard_fail" for f in entry.failures)
        has_soft = any(f.get("failure_mode") == "soft_fail" for f in entry.failures)
        if has_hard:
            return logging.ERROR
        if has_soft:
            return logging.WARNING
        return logging.INFO
