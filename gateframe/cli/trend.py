from __future__ import annotations

import sys
from pathlib import Path


def run_trend(file_path: str, window: int = 20) -> None:
    path = Path(file_path)
    if not path.exists():
        print(f"Error: file not found: {path}")
        sys.exit(1)

    from gateframe.audit.trend import ContractTrendAnalyzer

    analyzer = ContractTrendAnalyzer(path, window=window)
    report = analyzer.analyze()

    if not report.contract_trends:
        print("No workflow entries found in audit log. Ensure entries contain a workflow_id.")
        sys.exit(0)

    _print_report(report)

    if report.any_regression:
        sys.exit(2)


def _print_report(report) -> None:  # noqa: ANN001
    from gateframe.audit.trend import TrendReport

    report: TrendReport
    print(
        f"\nTrend Report  (window={report.window} runs, "
        f"regression_threshold={report.regression_threshold})"
    )
    print("=" * 60)

    for ct in report.contract_trends:
        runs = len(ct.run_summaries)
        avg_pass = sum(s.pass_rate for s in ct.run_summaries) / runs if runs else 0.0
        flag = " [REGRESSION]" if ct.regressed else ""
        print(f"\n  {ct.contract_name}{flag}")
        print(f"    direction : {ct.direction}")
        print(f"    slope     : {ct.slope:+.4f} per run")
        print(f"    avg pass  : {avg_pass:.1%}  over {runs} run(s)")

    print(f"\n{'=' * 60}")
    if report.any_regression:
        names = ", ".join(r.contract_name for r in report.regressions)
        print(f"REGRESSIONS DETECTED: {names}")
        print("Exit code 2 — integrate into CI to catch reliability drops.")
    else:
        print("No regressions detected.")
