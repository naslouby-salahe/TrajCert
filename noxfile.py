import nox


@nox.session(python=["3.12"])
def tests(session: nox.Session) -> None:
    session.install(".[quality]")
    session.run("coverage", "run", "-m", "pytest", "-q")
    session.run("coverage", "report")
    session.run("ruff", "format", "--check", ".")
    session.run("ruff", "check", ".")
    session.run("pyright")
    session.run("lint-imports")
    session.run("semgrep", "--config", "semgrep.yml", "src", "tests")
    session.run(
        "vulture",
        "src/trajcert",
        "--min-confidence",
        "100",
        "--ignore-names",
        "table,where,compression,use_dictionary,write_statistics,field_type,nullable,value_type,fields,tz,unit",
    )
    session.run("deptry", ".")
