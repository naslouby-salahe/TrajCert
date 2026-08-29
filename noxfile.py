from __future__ import annotations

import nox

nox.options.default_venv_backend = "uv"


@nox.session(reuse_venv=True)
def quality(session: nox.Session) -> None:
    session.run("uv", "sync", "--extra", "quality", external=True)
    session.run(
        "uv", "run", "ruff", "format", "--check", "src", "tools", "noxfile.py", external=True
    )
    session.run("uv", "run", "ruff", "check", "src", "tools", "noxfile.py", external=True)
    session.run("uv", "run", "basedpyright", external=True)
    session.run("uv", "run", "semgrep", "--config", "semgrep", "src/trajcert", external=True)
    session.run("uv", "run", "lint-imports", external=True)
    session.run("uv", "run", "python", "tools/source_audit.py", "src/trajcert", external=True)
    session.run("uv", "run", "complexipy", "src/trajcert", external=True)
    session.run(
        "uv",
        "run",
        "vulture",
        "src/trajcert",
        "--min-confidence",
        "100",
        "--ignore-names",
        "compression,use_dictionary,write_statistics",
        external=True,
    )
    session.run("uv", "run", "deptry", ".", external=True)
    session.run("uv", "run", "pip-audit", external=True)


@nox.session(reuse_venv=True)
def tests(session: nox.Session) -> None:
    session.run("uv", "sync", "--extra", "quality", external=True)
    session.run("uv", "run", "pytest", "--cov=trajcert", "--cov-branch", external=True)


@nox.session(reuse_venv=True)
def verify(session: nox.Session) -> None:
    session.run("uv", "sync", "--extra", "quality", external=True)
    session.run("uv", "run", "pytest", "tests/architecture", external=True)
    session.run("uv", "run", "crosshair", "check", "src/trajcert/math/safety.py", external=True)
    session.run("uv", "run", "mutmut", "run", "--max-children", "1", external=True)
