from pathlib import Path

import pytest

from gateframe.cli.inspect import _find_contracts, _import_file, run_inspect

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestImportFile:
    def test_loads_module(self) -> None:
        module = _import_file(FIXTURES / "sample_contract.py")
        assert hasattr(module, "sample_contract")

    def test_nonexistent_file_raises(self) -> None:
        with pytest.raises((FileNotFoundError, ImportError, OSError)):
            _import_file(FIXTURES / "nonexistent.py")


class TestFindContracts:
    def test_finds_contracts(self) -> None:
        module = _import_file(FIXTURES / "sample_contract.py")
        contracts = _find_contracts(module)
        names = [name for name, _ in contracts]
        assert "sample_contract" in names

    def test_ignores_non_contracts(self) -> None:
        module = _import_file(FIXTURES / "sample_contract.py")
        contracts = _find_contracts(module)
        names = [name for name, _ in contracts]
        assert "NOT_A_CONTRACT" not in names


class TestRunInspect:
    def test_valid_contract_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        run_inspect(str(FIXTURES / "sample_contract.py"))
        output = capsys.readouterr().out
        assert "sample" in output
        assert "StructuralRule" in output
        assert "SemanticRule" in output

    def test_nonexistent_file_exits(self) -> None:
        with pytest.raises(SystemExit):
            run_inspect(str(FIXTURES / "nonexistent.py"))

    def test_not_python_file_exits(self, tmp_path: Path) -> None:
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        with pytest.raises(SystemExit):
            run_inspect(str(txt))
