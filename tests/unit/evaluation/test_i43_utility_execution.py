import json
from collections.abc import Mapping
from pathlib import Path

from pytest import MonkeyPatch

from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw
from trajcert.domain.serialization import JSONValue
from trajcert.evaluation import i43_utility_execution
from trajcert.experiments.definitions.sequential_analysis import (
    PopulationMaterialityCell,
    SequentialMetricEvidence,
)
from trajcert.infrastructure.completion import completion_records


def test_utility_completion_records_authoritative_grouped_cell_count(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    configuration = load_configuration()
    monkeypatch.setattr(i43_utility_execution, "_laws", _empty_laws)
    monkeypatch.setattr(i43_utility_execution, "_population_payload", _population_payload)
    monkeypatch.setattr(i43_utility_execution, "_sequential_payload", _sequential_payload)

    evidence = i43_utility_execution.execute_i43_utility_validation(
        i43_utility_execution.I43UtilityExecutionRequest(tmp_path, configuration)
    )

    completion_path = tmp_path / i43_utility_execution.I43_UTILITY_COMPLETION_RELATIVE_PATH
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    records = completion_records(tmp_path)
    assert evidence.population_cell_count == 360
    assert evidence.sequential_cell_count == 18
    assert completion["cell_count"] == 378
    assert len(records) == 1
    assert records[0].valid


def _empty_laws(_: TrajCertConfiguration) -> Mapping[str, SyntheticTrajectoryLaw]:
    return {}


def _population_payload(
    _: Mapping[str, SyntheticTrajectoryLaw], __: TrajCertConfiguration
) -> tuple[Mapping[str, JSONValue], tuple[PopulationMaterialityCell, ...]]:
    return {"cell_count": 360, "claim_supported": False, "materiality": []}, ()


def _sequential_payload(
    _: Mapping[str, SyntheticTrajectoryLaw], __: TrajCertConfiguration
) -> tuple[Mapping[str, JSONValue], tuple[SequentialMetricEvidence, ...]]:
    return {"cell_count": 18, "claim_supported": False, "statistical_records": []}, ()
