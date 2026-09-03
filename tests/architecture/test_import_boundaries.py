from __future__ import annotations

from importlinter.cli import EXIT_STATUS_SUCCESS, lint_imports


def test_import_linter_contracts_are_kept() -> None:
    status = lint_imports(no_cache=True)
    assert status == EXIT_STATUS_SUCCESS
