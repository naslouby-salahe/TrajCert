import hashlib
import math
from datetime import UTC, datetime
from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.data.synthetic.generator import SyntheticEvent, generate_synthetic_stream
from trajcert.data.synthetic.laws import (
    SYNTHETIC_LAW_CATALOG_MANIFEST_RELATIVE_PATH,
    SYNTHETIC_LAW_CATALOG_RELATIVE_PATH,
    SYNTHETIC_SCALING_CATALOG_MANIFEST_RELATIVE_PATH,
    SYNTHETIC_SCALING_CATALOG_RELATIVE_PATH,
    SyntheticTrajectoryLaw,
    canonical_synthetic_law_catalog,
    synthetic_law_catalog,
    synthetic_law_roles,
    synthetic_scaling_laws,
    write_synthetic_law_catalog,
    write_synthetic_scaling_catalog,
)
from trajcert.data.synthetic.ledger import (
    SYNTHETIC_LEDGER_RELATIVE_PATH,
    prepare_synthetic_ledger,
    synthetic_ledger_records,
    write_prepared_synthetic_ledger,
)
from trajcert.math.information_profile import InformationProfile


def test_synthetic_trajectory_law_preserves_conditional_probability_and_horizon_contract() -> None:
    law = SyntheticTrajectoryLaw("timing", 0.05, 0.3, 0.1, 0.5, -0.5, 4, 8.0)

    harmful = law.conditional_resolution_masses(True)
    correct = law.conditional_resolution_masses(False)

    assert math.isclose(sum(harmful) + law.conditional_terminal_mass(True), 1.0)
    assert math.isclose(sum(correct) + law.conditional_terminal_mass(False), 1.0)
    assert harmful[-1] > harmful[0]
    assert correct[-1] < correct[0]
    assert law.band_horizons() == (2.0, 4.0, 6.0, 8.0)
    assert law.with_resolved_band_count(8).terminal_horizon == law.terminal_horizon
    assert math.isclose(
        law.observable_law().harmful_total
        + law.observable_law().correct_total
        + law.observable_law().c,
        1.0,
    )


def test_synthetic_law_catalog_uses_authoritative_configuration() -> None:
    configuration = load_configuration()
    catalog = synthetic_law_catalog(configuration.synthetic_data, configuration.method)

    assert tuple(law.name for law in catalog) == (
        *(law.name for law in configuration.synthetic_data.laws),
        "Minimum-information completion of Timing and terminal: harmful outcomes resolve late",
    )
    assert all(
        law.resolved_band_count == configuration.method.primary_finest_resolved_bands
        for law in catalog
    )
    assert synthetic_law_roles(configuration.synthetic_data).utility_and_coherence == (
        configuration.synthetic_data.utility_and_coherence_laws
    )


def test_primary_synthetic_law_roles_have_declared_parameter_patterns() -> None:
    configuration = load_configuration()
    laws = {law.name: law for law in configuration.synthetic_data.laws}

    assert laws["No outcome-path dependence"].q1 == laws["No outcome-path dependence"].q0
    assert laws["No outcome-path dependence"].lambda1 == laws["No outcome-path dependence"].lambda0
    assert (
        laws["Timing only: harmful outcomes resolve late"].q1
        == laws["Timing only: harmful outcomes resolve late"].q0
    )
    assert (
        laws["Timing only: harmful outcomes resolve late"].lambda1
        > laws["Timing only: harmful outcomes resolve late"].lambda0
    )
    assert (
        laws["Terminal only: harmful outcomes remain unresolved"].q1
        > laws["Terminal only: harmful outcomes remain unresolved"].q0
    )
    assert (
        laws["Terminal only: harmful outcomes remain unresolved"].lambda1
        == laws["Terminal only: harmful outcomes remain unresolved"].lambda0
    )
    assert (
        laws["Timing and terminal: harmful outcomes resolve late"].q1
        > laws["Timing and terminal: harmful outcomes resolve late"].q0
    )
    assert (
        laws["Timing and terminal: harmful outcomes resolve early"].lambda1
        < laws["Timing and terminal: harmful outcomes resolve early"].lambda0
    )
    assert laws["Low error prevalence"].theta < laws["High error prevalence"].theta
    assert laws["High terminal unresolvedness"].q1 > 0.5
    assert laws["Near numerical degeneracy"].q1 > 0.5
    assert (
        laws["Same endpoint without timing information"].q1
        == laws["Same endpoint with timing information"].q1
    )
    assert (
        laws["Same endpoint without timing information"].q0
        == laws["Same endpoint with timing information"].q0
    )


def test_synthetic_streams_are_seed_deterministic_and_hide_terminal_labels() -> None:
    law = SyntheticTrajectoryLaw("terminal", 0.5, 1.0, 1.0, 0.0, 0.0, 2, 8.0)
    stream = generate_synthetic_stream(law, 7, 3)

    assert stream == generate_synthetic_stream(law, 7, 3)
    assert all(event.admitted for event in stream)
    assert all(event.resolution_band is None and event.observed_label is None for event in stream)


def test_synthetic_ledger_records_have_canonical_identity_and_terminal_semantics() -> None:
    law = SyntheticTrajectoryLaw("Test law", 0.5, 0.0, 1.0, 0.0, 0.0, 2, 8.0)
    events = (
        SyntheticEvent(0, True, 1, True),
        SyntheticEvent(1, False, None, True),
    )

    records = synthetic_ledger_records(law, 3, events, datetime(2026, 1, 1, tzinfo=UTC))

    assert records[0].identity.client_id == "synthetic-client"
    assert records[0].identity.action_channel_id == "automatic-action"
    assert records[0].identity.epoch_id == "test-law::static-epoch"
    assert records[0].event_id == "test-law::S000003::E000000"
    assert records[1].event_id == "test-law::S000003::E000001"
    assert records[0].maturity_timestamp == datetime(2026, 1, 9, tzinfo=UTC)
    assert records[0].adjudication is not None
    assert records[0].adjudication.timestamp == datetime(2026, 1, 5, tzinfo=UTC)
    assert records[1].adjudication is None


def test_synthetic_preparation_returns_canonical_checksum_and_manifest(tmp_path: Path) -> None:
    law = SyntheticTrajectoryLaw("Test law", 0.5, 0.0, 1.0, 0.0, 0.0, 2, 8.0)
    events = (SyntheticEvent(0, True, 1, True), SyntheticEvent(1, False, None, True))

    prepared = prepare_synthetic_ledger(
        law,
        3,
        events,
        datetime(2026, 1, 1, tzinfo=UTC),
        1e-12,
    )

    assert prepared.ledger_checksum == prepared.dataset_manifest.preprocessing_digest
    assert prepared.dataset_manifest.known_full_law
    assert prepared.dataset_manifest.number_of_categories == 5
    assert tuple(record.event_id for record in prepared.records) == (
        "test-law::S000003::E000000",
        "test-law::S000003::E000001",
    )
    assert write_prepared_synthetic_ledger(tmp_path, prepared) == prepared.ledger_checksum
    assert (tmp_path / SYNTHETIC_LEDGER_RELATIVE_PATH).is_file()


def test_minimum_information_completion_preserves_observable_law_and_hits_floor() -> None:
    law = SyntheticTrajectoryLaw("timing", 0.05, 0.3, 0.05, 0.45, -0.15, 8, 8.0)

    derived = law.minimum_information_completion()
    profile = InformationProfile(law.observable_law())
    floor = profile.compatibility_floor().minimum_information_budget

    assert derived.name == "Minimum-information completion of timing"
    assert all(
        math.isclose(actual, expected, abs_tol=1e-12)
        for actual, expected in zip(
            derived.observable_law().harmful_masses,
            law.observable_law().harmful_masses,
            strict=True,
        )
    )
    assert all(
        math.isclose(actual, expected, abs_tol=1e-12)
        for actual, expected in zip(
            derived.observable_law().correct_masses,
            law.observable_law().correct_masses,
            strict=True,
        )
    )
    assert math.isclose(derived.observable_law().c, law.observable_law().c, abs_tol=1e-12)
    assert floor is not None
    assert math.isclose(
        InformationProfile(derived.observable_law()).value(derived.theta * derived.q1),
        floor,
        abs_tol=1e-12,
    )


def test_synthetic_scaling_laws_change_only_resolution() -> None:
    law = SyntheticTrajectoryLaw("timing", 0.05, 0.3, 0.05, 0.45, -0.15, 8, 8.0)

    scaled = synthetic_scaling_laws(law, (1, 2, 4, 8, 16))

    assert tuple(candidate.resolved_band_count for candidate in scaled) == (1, 2, 4, 8, 16)
    assert all(
        (
            candidate.name,
            candidate.theta,
            candidate.q1,
            candidate.q0,
            candidate.lambda1,
            candidate.lambda0,
            candidate.terminal_horizon,
        )
        == (
            law.name,
            law.theta,
            law.q1,
            law.q0,
            law.lambda1,
            law.lambda0,
            law.terminal_horizon,
        )
        for candidate in scaled
    )


def test_synthetic_law_catalog_is_canonical_and_atomically_materialized(tmp_path: Path) -> None:
    law = SyntheticTrajectoryLaw("timing", 0.05, 0.3, 0.05, 0.45, -0.15, 8, 8.0)

    digest = write_synthetic_law_catalog(tmp_path, (law,))
    payload = (tmp_path / SYNTHETIC_LAW_CATALOG_RELATIVE_PATH).read_bytes()

    assert digest == hashlib.sha256(payload).hexdigest()
    assert payload == canonical_synthetic_law_catalog((law,))
    assert (tmp_path / SYNTHETIC_LAW_CATALOG_MANIFEST_RELATIVE_PATH).is_file()


def test_synthetic_scaling_catalog_is_canonical_and_materialized(tmp_path: Path) -> None:
    law = SyntheticTrajectoryLaw("timing", 0.05, 0.3, 0.05, 0.45, -0.15, 8, 8.0)

    digest = write_synthetic_scaling_catalog(tmp_path, law, (2, 8, 16))
    payload = (tmp_path / SYNTHETIC_SCALING_CATALOG_RELATIVE_PATH).read_bytes()

    assert digest == hashlib.sha256(payload).hexdigest()
    assert payload == canonical_synthetic_law_catalog(synthetic_scaling_laws(law, (2, 8, 16)))
    assert (tmp_path / SYNTHETIC_SCALING_CATALOG_MANIFEST_RELATIVE_PATH).is_file()
