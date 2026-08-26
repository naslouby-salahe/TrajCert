from __future__ import annotations

from trajcert.config import TrajCertConfig
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import summarize_full_law
from trajcert.experiments.plan import build_plan
from trajcert.experiments.registry import authoritative_registry
from trajcert.types import DomainModel


class InventoryValidationResult(DomainModel):
    configured_law_count: int
    configured_partition_count: int
    registry_experiment_count: int
    registry_cell_count: int
    semantic_cell_uniqueness_pass: bool
    nonnegative_mass_pass: bool
    law_sum_pass: bool
    valid: bool


def validate_scientific_inventory(config: TrajCertConfig) -> InventoryValidationResult:
    law_sum_pass = True
    nonnegative_mass_pass = True
    for key, law_config in config.ordered_laws:
        parameters = LawParameters(
            key=key,
            name=LAW_DISPLAY_NAMES[key],
            theta=law_config.theta,
            q1=law_config.q1,
            q0=law_config.q0,
            lambda1=law_config.lambda1,
            lambda0=law_config.lambda0,
        )
        full_law = build_full_law(parameters, config.method.finest_bands)
        masses = (
            *tuple(float(value) for value in full_law.harmful_resolved),
            *tuple(float(value) for value in full_law.correct_resolved),
            float(full_law.terminal_harmful),
            float(full_law.terminal_correct),
        )
        nonnegative_mass_pass = nonnegative_mass_pass and all(value >= 0.0 for value in masses)
        law_sum_pass = law_sum_pass and abs(float(full_law.total) - 1.0) <= config.numerics.comparison_guard
        partition = build_partition(
            config.method.finest_bands,
            config.method.finest_bands,
            config.method.terminal_horizon,
        )
        summarize_full_law(partition, full_law, config.numerics.comparison_guard)
    registry = authoritative_registry()
    plan = build_plan(config)
    keys = tuple(cell.identity.semantic_cell_key for cell in plan.cells)
    uniqueness = len(keys) == len(set(keys))
    valid = (
        len(config.laws) == 12
        and len(registry) == 30
        and plan.registry_total == 1423
        and uniqueness
        and nonnegative_mass_pass
        and law_sum_pass
    )
    return InventoryValidationResult(
        configured_law_count=len(config.laws),
        configured_partition_count=len(config.grids.partitions),
        registry_experiment_count=len(registry),
        registry_cell_count=plan.registry_total,
        semantic_cell_uniqueness_pass=uniqueness,
        nonnegative_mass_pass=nonnegative_mass_pass,
        law_sum_pass=law_sum_pass,
        valid=valid,
    )
