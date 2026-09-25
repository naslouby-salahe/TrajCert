from __future__ import annotations

import nox

_SRC_TRAJCERT = "src/trajcert"
_REQUIREMENTS_LOCK = "requirements.lock"
_QUALITY_EXTRA = ".[quality]"


@nox.session(reuse_venv=True)
def quality(session: nox.Session) -> None:
    _install_quality_environment(session)
    session.run("ruff", "format", "--check", "src", "tools", "noxfile.py")
    session.run("ruff", "check", "src", "tools", "noxfile.py")
    session.run("basedpyright")
    session.run("semgrep", "--config", "semgrep", _SRC_TRAJCERT)
    session.run("lint-imports")
    session.run("python", "tools/source_audit.py", _SRC_TRAJCERT)
    session.run("complexipy", _SRC_TRAJCERT)
    session.run(
        "vulture",
        _SRC_TRAJCERT,
        "--min-confidence",
        "100",
        "--ignore-names",
        "compression,use_dictionary,write_statistics",
    )
    session.run("deptry", ".")
    session.run("pip-audit")


@nox.session(reuse_venv=True)
def tests(session: nox.Session) -> None:
    _install_quality_environment(session)
    session.run("pytest", "--cov=trajcert", "--cov-branch")


@nox.session(reuse_venv=True)
def verify(session: nox.Session) -> None:
    _install_quality_environment(session)
    session.run("pytest", "tests/architecture")
    session.run("crosshair", "check", "src/trajcert/math/safety.py")
    session.run("mutmut", "run", "--max-children", "1")


def _install_quality_environment(session: nox.Session) -> None:
    session.install("--require-hashes", "-r", _REQUIREMENTS_LOCK)
    session.install(_QUALITY_EXTRA)
