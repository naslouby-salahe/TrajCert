from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from trajcert.configuration.models import FailureBoundaryAxis, TrajCertConfiguration
from trajcert.data.synthetic.laws import ResolvedBandCount, SyntheticTrajectoryLaw
from trajcert.domain.enums import ExperimentName, ScientificState

type FailureBoundaryLevel = float | int | tuple[float, float]


class FailureBoundaryAxisName(StrEnum):
    TERMINAL_UNRESOLVED_SEVERITY = "Terminal unresolved severity"
    TIMING_CONTRAST = "Timing contrast"
    HARMFUL_PREVALENCE = "Harmful prevalence"
    PATH_RESOLUTION = "Path resolution"
    SENSITIVITY_MARGIN_ABOVE_COMPATIBILITY = "Sensitivity margin above compatibility"
    RISK_BUDGET_OFFSET_FROM_INTRINSIC_BOUNDARY = "Risk-budget offset from intrinsic boundary"
    MATURED_SAMPLE_SIZE = "Matured sample size"
    TERMINAL_SELECTION_ASYMMETRY = "Terminal-selection asymmetry"
    OPTIMIZER_NODE_BUDGET = "Optimizer-node budget"


class BoundaryInputKind(StrEnum):
    POPULATION = "POPULATION"
    DETERMINISTIC_FINITE_SAMPLE = "DETERMINISTIC_FINITE_SAMPLE"


@dataclass(frozen=True, slots=True)
class InformationNats:
    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("information values must be finite")


@dataclass(frozen=True, slots=True)
class RiskProbability:
    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value) or not 0.0 <= self.value <= 1.0:
            raise ValueError("risk probabilities must lie in [0, 1]")


@dataclass(frozen=True, slots=True)
class FailureBoundaryReference:
    compatibility_floor: InformationNats
    intrinsic_risk_boundary: RiskProbability


@dataclass(frozen=True, slots=True)
class FailureBoundaryAtlasInput:
    configuration: TrajCertConfiguration
    base_law: SyntheticTrajectoryLaw
    reference: FailureBoundaryReference

    def __post_init__(self) -> None:
        if self.base_law.name != self.configuration.failure_boundary.base_law:
            raise ValueError("failure-boundary base law must equal the configured base law")


@dataclass(frozen=True, slots=True)
class FailureBoundaryCell:
    axis: FailureBoundaryAxisName
    level_index: int
    level: str
    law: SyntheticTrajectoryLaw
    rho: InformationNats
    beta: RiskProbability
    input_kind: BoundaryInputKind
    matured_sample_size: int | None
    optimizer_node_cap: int | None

    def __post_init__(self) -> None:
        if self.level_index < 0:
            raise ValueError("failure-boundary levels must have nonnegative indices")
        finite_sample = self.input_kind is BoundaryInputKind.DETERMINISTIC_FINITE_SAMPLE
        if finite_sample != (self.matured_sample_size is not None):
            raise ValueError("finite-sample boundary cells require exactly one sample size")
        if self.matured_sample_size is not None and self.matured_sample_size <= 0:
            raise ValueError("matured sample sizes must be positive")
        if self.optimizer_node_cap is not None and self.optimizer_node_cap <= 0:
            raise ValueError("optimizer node caps must be positive")


@dataclass(frozen=True, slots=True)
class FailureBoundaryResult:
    cell: FailureBoundaryCell
    operational_state: ScientificState
    optimizer_gap: float | None
    runtime_ms: float | None

    def __post_init__(self) -> None:
        if self.optimizer_gap is not None and (
            not math.isfinite(self.optimizer_gap) or self.optimizer_gap < 0.0
        ):
            raise ValueError("optimizer gaps must be finite and nonnegative")
        if self.runtime_ms is not None and (
            not math.isfinite(self.runtime_ms) or self.runtime_ms < 0.0
        ):
            raise ValueError("runtimes must be finite and nonnegative")
        if self.cell.input_kind is BoundaryInputKind.POPULATION and (
            self.optimizer_gap is not None or self.runtime_ms is not None
        ):
            raise ValueError("population boundary cells cannot report optimizer diagnostics")


@dataclass(frozen=True, slots=True)
class PlannedNonapplicability:
    experiment_name: ExperimentName
    executable_cell_count: int

    def __post_init__(self) -> None:
        if self.experiment_name not in {
            ExperimentName.REAL_TRAJECTORY_VALIDATION,
            ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
        }:
            raise ValueError("only roadmap-planned nonapplicabilities are valid here")
        if self.executable_cell_count != 0:
            raise ValueError("planned nonapplicabilities must retain zero executable cells")


def failure_boundary_cells(
    input_value: FailureBoundaryAtlasInput,
) -> tuple[FailureBoundaryCell, ...]:
    configuration = input_value.configuration
    configured_axes = tuple(
        FailureBoundaryAxisName(axis.name) for axis in configuration.failure_boundary.axes
    )
    if configured_axes != tuple(FailureBoundaryAxisName):
        raise ValueError("failure-boundary axes must match the canonical nine-axis order")
    cells: list[FailureBoundaryCell] = []
    for configured_axis, axis_name in zip(
        configuration.failure_boundary.axes, configured_axes, strict=True
    ):
        for level_index, level_value in enumerate(_axis_levels(configured_axis, axis_name)):
            cells.append(_boundary_cell(input_value, axis_name, level_index, level_value))
    return tuple(cells)


def planned_nonapplicabilities() -> tuple[PlannedNonapplicability, ...]:
    return (
        PlannedNonapplicability(ExperimentName.REAL_TRAJECTORY_VALIDATION, 0),
        PlannedNonapplicability(ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL, 0),
    )


def _axis_levels(
    configured_axis: FailureBoundaryAxis, axis: FailureBoundaryAxisName
) -> tuple[FailureBoundaryLevel, ...]:
    values = (
        configured_axis.q1_equals_q0_values
        or configured_axis.d_values
        or configured_axis.theta_values
        or configured_axis.resolved_band_values
        or configured_axis.n_values
        or configured_axis.q1_q0_pairs
        or configured_axis.node_values
    )
    if values is None:
        raise ValueError(f"failure-boundary axis {axis} has no configured levels")
    return cast(tuple[FailureBoundaryLevel, ...], tuple(values))


def _boundary_cell(
    input_value: FailureBoundaryAtlasInput,
    axis: FailureBoundaryAxisName,
    level_index: int,
    level: FailureBoundaryLevel,
) -> FailureBoundaryCell:
    configuration = input_value.configuration
    base_law = input_value.base_law
    law = base_law
    rho = InformationNats(configuration.budgets.primary_information_nats)
    beta = RiskProbability(configuration.budgets.primary_risk)
    input_kind = BoundaryInputKind.POPULATION
    sample_size: int | None = None
    node_cap: int | None = None
    if axis is FailureBoundaryAxisName.TERMINAL_UNRESOLVED_SEVERITY:
        value = _float_level(level, axis)
        law = _law_with(base_law, q1=value, q0=value)
    elif axis is FailureBoundaryAxisName.TIMING_CONTRAST:
        value = _float_level(level, axis)
        law = _law_with(base_law, lambda1=value / 2.0, lambda0=-value / 2.0)
    elif axis is FailureBoundaryAxisName.HARMFUL_PREVALENCE:
        law = _law_with(base_law, theta=_float_level(level, axis))
    elif axis is FailureBoundaryAxisName.PATH_RESOLUTION:
        law = base_law.with_resolved_band_count(ResolvedBandCount(_integer_level(level, axis)))
    elif axis is FailureBoundaryAxisName.SENSITIVITY_MARGIN_ABOVE_COMPATIBILITY:
        rho = InformationNats(
            input_value.reference.compatibility_floor.value + _float_level(level, axis)
        )
    elif axis is FailureBoundaryAxisName.RISK_BUDGET_OFFSET_FROM_INTRINSIC_BOUNDARY:
        beta = RiskProbability(
            min(
                1.0,
                max(
                    0.0,
                    input_value.reference.intrinsic_risk_boundary.value + _float_level(level, axis),
                ),
            )
        )
    elif axis is FailureBoundaryAxisName.MATURED_SAMPLE_SIZE:
        input_kind = BoundaryInputKind.DETERMINISTIC_FINITE_SAMPLE
        sample_size = _integer_level(level, axis)
    elif axis is FailureBoundaryAxisName.TERMINAL_SELECTION_ASYMMETRY:
        q1, q0 = _pair_level(level, axis)
        law = _law_with(base_law, q1=q1, q0=q0)
    elif axis is FailureBoundaryAxisName.OPTIMIZER_NODE_BUDGET:
        input_kind = BoundaryInputKind.DETERMINISTIC_FINITE_SAMPLE
        sample_size = _configured_optimizer_sample_size(configuration)
        node_cap = _integer_level(level, axis)
    return FailureBoundaryCell(
        axis, level_index, str(level), law, rho, beta, input_kind, sample_size, node_cap
    )


def _configured_optimizer_sample_size(configuration: TrajCertConfiguration) -> int:
    sample_size = configuration.failure_boundary.axes[-1].deterministic_matured_sample_size
    if sample_size is None:
        raise ValueError("optimizer-node axis requires configured deterministic sample size")
    return sample_size


def _law_with(
    law: SyntheticTrajectoryLaw,
    *,
    theta: float | None = None,
    q1: float | None = None,
    q0: float | None = None,
    lambda1: float | None = None,
    lambda0: float | None = None,
) -> SyntheticTrajectoryLaw:
    return SyntheticTrajectoryLaw(
        law.name,
        law.theta if theta is None else theta,
        law.q1 if q1 is None else q1,
        law.q0 if q0 is None else q0,
        law.lambda1 if lambda1 is None else lambda1,
        law.lambda0 if lambda0 is None else lambda0,
        law.resolved_band_count,
        law.terminal_horizon,
    )


def _float_level(value: FailureBoundaryLevel, axis: FailureBoundaryAxisName) -> float:
    if not isinstance(value, float):
        raise TypeError(f"failure-boundary axis {axis} requires a floating-point level")
    return value


def _integer_level(value: FailureBoundaryLevel, axis: FailureBoundaryAxisName) -> int:
    if not isinstance(value, int):
        raise TypeError(f"failure-boundary axis {axis} requires an integer level")
    return value


def _pair_level(value: FailureBoundaryLevel, axis: FailureBoundaryAxisName) -> tuple[float, float]:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not all(isinstance(item, float) for item in value)
    ):
        raise TypeError(f"failure-boundary axis {axis} requires a pair of floating-point levels")
    return value
