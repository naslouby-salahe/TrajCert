from __future__ import annotations

import sys

from pytest import CaptureFixture, MonkeyPatch

from trajcert.cli import main


def test_doctor_validates_the_authoritative_core_inputs(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])

    main()

    assert capsys.readouterr().out == (
        "TrajCert doctor: configuration and core scientific inputs are valid\n"
    )
