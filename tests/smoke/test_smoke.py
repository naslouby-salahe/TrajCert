from trajcert.cli.commands.smoke import (
    SMOKE_FIXTURES,
    OverwriteRequested,
    SmokeCommandInput,
    execute,
)


def test_exact_deterministic_smoke_fixture_contract() -> None:
    fixtures = {fixture.name: fixture for fixture in SMOKE_FIXTURES}
    assert len(fixtures) == 6
    assert fixtures["compatible_population"].expected == "compatible nonempty risk set"
    assert fixtures["incompatible_population"].expected == "MODEL_INCOMPATIBLE"
    assert fixtures["deterministic_cs"].partition == "2-band partition"
    assert fixtures["low_dimensional_outer_optimizer"].law == (
        "Timing and terminal: harmful outcomes resolve late"
    )


def test_smoke_command_exercises_population_validation_path() -> None:
    assert execute(SmokeCommandInput(OverwriteRequested(False))) == 0
