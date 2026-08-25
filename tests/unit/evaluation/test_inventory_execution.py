from pathlib import Path

from trajcert.configuration.loading import load_configuration
from trajcert.evaluation.inventory_execution import execute_inventory_validation
from trajcert.experiments.definitions.scientific_inventory import InventoryValidationState
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


def test_inventory_execution_persists_verified_synthetic_inventory_evidence(tmp_path: Path) -> None:
    record = execute_inventory_validation(tmp_path, load_configuration())

    records = completion_records(
        tmp_path, CompletionExperimentName("Scientific and Data Inventory")
    )

    assert record.state is InventoryValidationState.PASS
    assert len(record.generated_law_names) == 12
    assert len(records) == 1
    assert records[0].valid
