from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from gateframe.core.contract import ValidationContract


def run_inspect(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        print(f"Error: file not found: {path}")
        sys.exit(1)
    if path.suffix != ".py":
        print(f"Error: not a Python file: {path}")
        sys.exit(1)

    module = _import_file(path)
    contracts = _find_contracts(module)

    if not contracts:
        print(f"No ValidationContract instances found in {path}")
        sys.exit(0)

    print(f"\nFound {len(contracts)} contract(s) in {path.name}")
    for var_name, contract in contracts:
        _print_contract(var_name, contract)


def _import_file(path: Path) -> Any:  # noqa: ANN401 -- returns module
    parent = str(path.parent.resolve())
    if parent not in sys.path:
        sys.path.insert(0, parent)

    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_contracts(module: Any) -> list[tuple[str, ValidationContract]]:  # noqa: ANN401
    results = []
    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        obj = getattr(module, attr_name)
        if isinstance(obj, ValidationContract):
            results.append((attr_name, obj))
    return results


def _print_contract(var_name: str, contract: ValidationContract) -> None:
    print(f"\n{'=' * 60}")
    print(f"Contract: {contract.name}  (variable: {var_name})")
    print(f"{'=' * 60}")
    print(f"  Rules ({len(contract.rules)}):")
    for i, rule in enumerate(contract.rules):
        rule_type = type(rule).__name__
        print(f"    [{i}] {rule_type}: {rule.name}")
        if rule.description:
            print(f"        {rule.description}")
        if hasattr(rule, "schema"):
            print(f"        schema: {rule.schema.__name__}")
        if hasattr(rule, "failure_mode"):
            print(f"        failure_mode: {rule.failure_mode.value}")
    if contract.on_hard_fail:
        print(f"  on_hard_fail: {contract.on_hard_fail.value}")
    if contract.on_soft_fail:
        print(f"  on_soft_fail: {contract.on_soft_fail.value}")
