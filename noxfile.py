from __future__ import annotations

import nox

_SRC = "src"
_REQUIREMENTS_LOCK = "requirements.lock"
_QUALITY_EXTRA = ".[quality]"


@nox.session(reuse_venv=True)
def quality(session: nox.Session) -> None:
    _install_quality_environment(session)
    session.run("ruff", "format", "--check", "src", "tools", "noxfile.py")
    session.run("ruff", "check", "src", "tools", "noxfile.py")
    session.run("basedpyright")
    session.run("semgrep", "--config", "semgrep", _SRC)
    session.run("lint-imports")
    session.run("python", "tools/source_audit.py", _SRC)
    session.run("complexipy", _SRC)
    session.run(
        "vulture",
        _SRC,
        "--min-confidence",
        "100",
        "--ignore-names",
        "compression,use_dictionary,write_statistics",
    )
    session.run("deptry", ".")
    session.run("pip-audit", "--timeout", "60")


@nox.session(reuse_venv=True)
def tests(session: nox.Session) -> None:
    _install_quality_environment(session)
    session.run("pytest", "--cov=trajcert", "--cov-branch")


@nox.session(reuse_venv=True)
def verify(session: nox.Session) -> None:
    _install_quality_environment(session)
    session.run("pytest", "tests/architecture")
    session.run("mutmut", "run", "--max-children", "1")


def _install_quality_environment(session: nox.Session) -> None:
    session.install("--require-hashes", "-r", _REQUIREMENTS_LOCK)
    session.install(_QUALITY_EXTRA)
