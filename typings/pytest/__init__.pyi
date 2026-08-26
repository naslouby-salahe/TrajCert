from _pytest._code import ExceptionInfo
from _pytest.capture import CaptureFixture
from _pytest.fixtures import FixtureFunction, FixtureFunctionMarker, fixture
from _pytest.mark import MARK_GEN as mark
from _pytest.mark.structures import MarkDecorator, MarkGenerator, ParameterSet
from _pytest.monkeypatch import MonkeyPatch
from _pytest.python_api import ApproxBase, RaisesContext, raises

__all__ = [
    "ApproxBase",
    "CaptureFixture",
    "ExceptionInfo",
    "FixtureFunction",
    "FixtureFunctionMarker",
    "MarkDecorator",
    "MarkGenerator",
    "MonkeyPatch",
    "ParameterSet",
    "RaisesContext",
    "approx",
    "fixture",
    "mark",
    "raises",
]

def approx(
    expected: object,
    rel: float | None = None,
    abs: float | None = None,
    nan_ok: bool = False,
) -> ApproxBase: ...
