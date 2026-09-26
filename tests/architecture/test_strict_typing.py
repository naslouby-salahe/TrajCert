from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
_DISABLED_DIAGNOSTIC = re.compile(
    r'^\s*report(?:Any|UnknownArgumentType|UnknownMemberType)\s*=\s*(?:false|"none"|"off")\s*$'
)


def _type_checker_violations(configuration: str) -> tuple[str, ...]:
    marker = "[tool.basedpyright]"
    if marker not in configuration:
        return ("[tool.basedpyright] section is missing",)
    section = configuration.split(marker, maxsplit=1)[1].split("\n[", maxsplit=1)[0]
    lines = tuple(line.strip() for line in section.splitlines())
    violations = [line for line in lines if _DISABLED_DIAGNOSTIC.fullmatch(line)]
    if 'typeCheckingMode = "all"' not in lines:
        violations.append('typeCheckingMode must be "all"')
    if "failOnWarnings = true" not in lines:
        violations.append("failOnWarnings must be true")
    if 'include = ["src", "tests"]' not in lines:
        violations.append('include must cover both "src" and "tests"')
    return tuple(violations)


def test_pyright_configuration_enables_strict_source_and_test_checks() -> None:
    configuration = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert not _type_checker_violations(configuration)


def test_mutation_of_any_or_unknown_type_diagnostics_is_rejected() -> None:
    valid = (
        '[tool.basedpyright]\ntypeCheckingMode = "all"\nfailOnWarnings = true\n'
        'include = ["src", "tests"]\n'
    )
    mutated = valid + "reportAny = false\nreportUnknownArgumentType = false\n"
    assert not _type_checker_violations(valid)
    assert _type_checker_violations(mutated) == (
        "reportAny = false",
        "reportUnknownArgumentType = false",
    )
