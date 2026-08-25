from __future__ import annotations

import sys

import pytest

from trajcert.cli import main


def test_doctor_validates_the_authoritative_core_inputs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])

    main()

    assert capsys.readouterr().out == (
        "TrajCert doctor: configuration and core scientific inputs are valid\n"
    )
