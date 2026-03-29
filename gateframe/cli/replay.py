from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


def run_replay(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        print(f"Error: file not found: {path}")
        sys.exit(1)

    entries = _load_entries(path)
    if not entries:
        print("No entries found in audit log.")
        sys.exit(0)

    _print_summary(entries)
    for i, entry in enumerate(entries):
        _print_entry(i, entry)


def _load_entries(path: Path) -> list[dict[str, Any]]:
    text = path.read_text()

    # Try JSON array first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return [data]
    except json.JSONDecodeError:
        pass

    # Try JSON Lines
    entries: list[dict[str, Any]] = []
    for line_num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("skipping_invalid_line", line_number=line_num)
    return entries


def _print_summary(entries: list[dict[str, Any]]) -> None:
    total = len(entries)
    passed = sum(1 for e in entries if e.get("passed"))
    failed = total - passed
    print(f"\nAudit Log: {total} entries ({passed} passed, {failed} failed)")
    print("=" * 60)


def _print_entry(index: int, entry: dict[str, Any]) -> None:
    status = "PASS" if entry.get("passed") else "FAIL"
    contract = entry.get("contract_name", "?")
    print(f"\n  [{index}] {contract} -- {status}")
    print(f"      timestamp: {entry.get('timestamp', '?')}")
    print(
        f"      rules: {entry.get('rules_applied', '?')} applied, "
        f"{entry.get('rules_failed', '?')} failed"
    )
    if entry.get("workflow_id"):
        print(f"      workflow: {entry['workflow_id']}, confidence: {entry.get('confidence', '?')}")
    for failure in entry.get("failures", []):
        mode = failure.get("failure_mode", "?")
        name = failure.get("rule_name", "?")
        msg = failure.get("message", "?")
        print(f"      FAILURE: [{mode}] {name}: {msg}")
