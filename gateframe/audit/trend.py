"""Cross-session contract reliability trend analysis for gateframe.

Provides :class:`ContractTrendAnalyzer` which reads an existing JSONL audit
log produced by :class:`~gateframe.audit.exporters.JsonFileExporter`, groups
entries by ``workflow_id``, and computes per-contract OLS pass-rate slopes to
detect reliability regressions across workflow runs.

Usage::

    from pathlib import Path
    from gateframe.audit.trend import ContractTrendAnalyzer

    analyzer = ContractTrendAnalyzer(Path("audit.jsonl"), window=20)
    report = analyzer.analyze()
    if report.any_regression:
        print("Contracts degrading:", [r.contract_name for r in report.regressions])

CLI equivalent::

    gateframe trend audit.jsonl --window 20

The *window* parameter specifies the number of most-recent **workflow runs**
(i.e. distinct ``workflow_id`` groups) to include in the trend calculation.
Entries without a ``workflow_id`` are ignored.

Reference: PDR in Production v2.5 — DOI 10.5281/zenodo.19362461
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Data models


@dataclass
class WorkflowRunSummary:
    """Pass-rate statistics for a single workflow run.

    A "workflow run" is the set of all audit entries that share the same
    ``workflow_id``.

    Attributes:
        workflow_id: The workflow identifier.
        contract_name: Name of the :class:`~gateframe.core.contract.ValidationContract`.
        total: Total number of validation events in this run.
        passed: Number of events where ``passed == True``.
        pass_rate: ``passed / total`` (``NaN`` when ``total == 0``).
    """

    workflow_id: str
    contract_name: str
    total: int
    passed: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else float("nan")


@dataclass
class ContractTrend:
    """OLS trend for a single contract across ordered workflow runs.

    Attributes:
        contract_name: Name of the contract.
        run_summaries: Ordered (oldest first) per-run statistics.
        slope: OLS slope of ``pass_rate`` over run index (positive = improving).
        direction: ``"improving"``, ``"worsening"``, or ``"stable"``.
        regressed: ``True`` when the slope is below ``-regression_threshold``.
    """

    contract_name: str
    run_summaries: list[WorkflowRunSummary]
    slope: float
    direction: str
    regressed: bool


@dataclass
class TrendReport:
    """Aggregated trend report across all contracts in the audit log.

    Attributes:
        contract_trends: Per-contract trend results, sorted by ``contract_name``.
        any_regression: ``True`` if at least one contract is degrading.
        regressions: Subset of *contract_trends* where ``regressed == True``.
        window: Number of workflow runs included in the analysis.
        regression_threshold: Threshold used to classify a slope as a regression.
    """

    contract_trends: list[ContractTrend]
    any_regression: bool
    regressions: list[ContractTrend] = field(default_factory=list)
    window: int = 20
    regression_threshold: float = 0.02


# Internal helpers


def _ols_slope(values: list[float]) -> float:
    """OLS slope of *values* over index 0 … n-1.  Returns 0.0 for < 2 points."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    slope, _ = statistics.linear_regression(xs, values)
    return slope


def _direction(slope: float, threshold: float = 0.001) -> str:
    if slope > threshold:
        return "improving"
    if slope < -threshold:
        return "worsening"
    return "stable"


def _is_valid_float(v: float) -> bool:
    import math

    return not (math.isnan(v) or math.isinf(v))


# Public API


class ContractTrendAnalyzer:
    """Reads a gateframe JSONL audit log and computes per-contract trend slopes.

    Only audit entries that carry a ``workflow_id`` are considered.  Entries are
    grouped by ``workflow_id``; the groups are ordered by the **earliest
    timestamp** seen within each group (oldest-first), so the trend slope
    represents change over time.

    Args:
        audit_log_path: Path to the JSONL file written by
            :class:`~gateframe.audit.exporters.JsonFileExporter`.
        window: How many most-recent workflow-ID groups to include.
        regression_threshold: Minimum downward slope that constitutes a
            regression.  Defaults to 0.02 (2 percentage-point drop per run).

    Example::

        analyzer = ContractTrendAnalyzer(Path("audit.jsonl"), window=20)
        report = analyzer.analyze()
        for ct in report.contract_trends:
            print(f"{ct.contract_name}: {ct.direction} (slope={ct.slope:.4f})")
    """

    def __init__(
        self,
        audit_log_path: Path | str,
        *,
        window: int = 20,
        regression_threshold: float = 0.02,
    ) -> None:
        self._path = Path(audit_log_path)
        self._window = window
        self._regression_threshold = regression_threshold

    # private

    def _read_entries(self) -> list[dict]:
        """Parse the JSONL file; skip malformed lines."""
        entries: list[dict] = []
        try:
            with self._path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return entries

    def _build_run_summaries(self, entries: list[dict]) -> dict[str, list[WorkflowRunSummary]]:
        """Group entries by workflow_id, compute pass rates per contract.

        Returns a dict mapping contract_name → list of WorkflowRunSummary,
        ordered oldest-first by first-seen timestamp within each workflow run.
        """
        # workflow_id → contract_name → {total, passed}
        # Also track earliest timestamp per workflow_id for ordering.
        wf_contract: dict[str, dict[str, dict]] = defaultdict(
            lambda: defaultdict(lambda: {"total": 0, "passed": 0})
        )
        wf_first_ts: dict[str, str] = {}

        for entry in entries:
            wf_id = entry.get("workflow_id")
            if not wf_id:
                continue
            contract = entry.get("contract_name", "unknown")
            passed = bool(entry.get("passed", False))
            ts = entry.get("timestamp", "")

            if wf_id not in wf_first_ts or ts < wf_first_ts[wf_id]:
                wf_first_ts[wf_id] = ts

            bucket = wf_contract[wf_id][contract]
            bucket["total"] += 1
            if passed:
                bucket["passed"] += 1

        # Sort workflow runs by first-seen timestamp → oldest first
        ordered_wf_ids = sorted(wf_first_ts, key=lambda w: wf_first_ts[w])

        # Apply window: keep only the most-recent *window* runs
        if len(ordered_wf_ids) > self._window:
            ordered_wf_ids = ordered_wf_ids[-self._window :]

        # Invert: contract_name → list[WorkflowRunSummary] (time-ordered)
        contract_runs: dict[str, list[WorkflowRunSummary]] = defaultdict(list)
        for wf_id in ordered_wf_ids:
            for contract, counts in wf_contract[wf_id].items():
                contract_runs[contract].append(
                    WorkflowRunSummary(
                        workflow_id=wf_id,
                        contract_name=contract,
                        total=counts["total"],
                        passed=counts["passed"],
                    )
                )

        return dict(contract_runs)

    # public

    def analyze(self) -> TrendReport:
        """Run the trend analysis and return a :class:`TrendReport`.

        Returns:
            A :class:`TrendReport` summarising per-contract slopes and
            regression flags.  If the audit log is empty or contains no
            entries with ``workflow_id``, the report will have no
            ``contract_trends``.
        """
        entries = self._read_entries()
        contract_runs = self._build_run_summaries(entries)

        contract_trends: list[ContractTrend] = []
        for contract_name, run_summaries in sorted(contract_runs.items()):
            pass_rates = [s.pass_rate for s in run_summaries if _is_valid_float(s.pass_rate)]
            slope = _ols_slope(pass_rates)
            direction = _direction(slope)
            regressed = slope < -self._regression_threshold

            contract_trends.append(
                ContractTrend(
                    contract_name=contract_name,
                    run_summaries=run_summaries,
                    slope=slope,
                    direction=direction,
                    regressed=regressed,
                )
            )

        regressions = [ct for ct in contract_trends if ct.regressed]
        return TrendReport(
            contract_trends=contract_trends,
            any_regression=bool(regressions),
            regressions=regressions,
            window=self._window,
            regression_threshold=self._regression_threshold,
        )
