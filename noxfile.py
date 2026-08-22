import nox


@nox.session(python=["3.12"])
def tests(session: nox.Session) -> None:
    session.install(".")
    session.run("pytest", "-q")
