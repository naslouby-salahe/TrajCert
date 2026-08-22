from trajcert.cli.main import SUCCESS_OR_SCIENTIFIC_NOOP, USAGE_OR_UNKNOWN_NAME, main


def test_public_cli_accepts_only_declared_command_forms() -> None:
    assert main(("doctor",)) == SUCCESS_OR_SCIENTIFIC_NOOP
    assert (
        main(("preprocess", "Timing and terminal: harmful outcomes resolve late", "--overwrite"))
        == 0
    )
    assert main(("plan",)) == SUCCESS_OR_SCIENTIFIC_NOOP
    assert main(("smoke", "--overwrite")) == SUCCESS_OR_SCIENTIFIC_NOOP
    assert main(("run", "population-sensitivity-utility", "--overwrite")) == 0
    assert main(("status",)) == SUCCESS_OR_SCIENTIFIC_NOOP
    assert main(("report", "population-sensitivity-utility", "--overwrite")) == 0
    assert main(("run", "population-sensitivity-utility", "--rho", "0.05")) == USAGE_OR_UNKNOWN_NAME
