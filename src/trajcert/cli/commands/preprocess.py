from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NewType

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.synthetic.laws import (
    SyntheticScalingCatalogWriteInput,
    SyntheticTrajectoryLaw,
    synthetic_law_catalog,
    write_synthetic_law_catalog,
    write_synthetic_scaling_catalog,
)
from trajcert.data.synthetic.ledger import (
    PreparedSyntheticLedgerWriteInput,
    SyntheticLedgerPreparationInput,
    prepare_synthetic_ledger,
    write_prepared_synthetic_ledger,
)

DatasetName = NewType("DatasetName", str)
OverwriteRequested = NewType("OverwriteRequested", bool)
PreprocessExitCode = NewType("PreprocessExitCode", int)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True, slots=True)
class PreprocessCommandInput:
    dataset_name: DatasetName | None
    overwrite: OverwriteRequested


def execute(input_value: PreprocessCommandInput) -> PreprocessExitCode:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    laws = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    base_laws = laws[: len(configuration.synthetic_data.laws)]
    if input_value.dataset_name is not None and input_value.dataset_name not in {
        law.name for law in base_laws
    }:
        return PreprocessExitCode(configuration.cli.exit_codes.usage_or_unknown_name)
    selected_laws = (
        base_laws
        if input_value.dataset_name is None
        else tuple(law for law in base_laws if law.name == input_value.dataset_name)
    )
    write_synthetic_law_catalog(PROJECT_ROOT, laws)
    _write_scaling_catalog(configuration, base_laws)
    for stream_index, law in enumerate(selected_laws):
        prepared = prepare_synthetic_ledger(
            SyntheticLedgerPreparationInput(
                law,
                stream_index,
                (),
                datetime(1970, 1, 1, tzinfo=UTC),
                configuration.numerics.scientific_comparison_guard,
            )
        )
        write_prepared_synthetic_ledger(PreparedSyntheticLedgerWriteInput(PROJECT_ROOT, prepared))
    return PreprocessExitCode(configuration.cli.exit_codes.success_or_scientific_noop)


def _write_scaling_catalog(
    configuration: TrajCertConfiguration,
    laws: tuple[SyntheticTrajectoryLaw, ...],
) -> None:
    matching_laws = tuple(law for law in laws if law.name == configuration.runtime_benchmark.law)
    if len(matching_laws) != 1:
        raise ValueError("runtime benchmark law must resolve exactly once")
    write_synthetic_scaling_catalog(
        SyntheticScalingCatalogWriteInput(
            PROJECT_ROOT,
            matching_laws[0],
            configuration.partitions.computational_scaling_resolved_bands,
        )
    )
