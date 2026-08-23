from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from trajcert.configuration.models import SensitivityConfiguration


class RhoOffsetFamily(StrEnum):
    SHARP_SET = "sharp_set"
    ORACLE_VALIDATION = "oracle_validation"
    REFINEMENT_ABOVE_FINE_TAU = "refinement_above_fine_tau"


class RhoOffsetBase(StrEnum):
    PARTITION_TRUE_INFORMATION = "partition_true_information"
    FINE_PARTITION_TRUE_INFORMATION = "fine_partition_true_information"


class ResolvedRhoValidity(StrEnum):
    VALID = "VALID"
    INVALID_NEGATIVE_RHO = "INVALID_NEGATIVE_RHO"


@dataclass(frozen=True, slots=True)
class InformationQuantity:
    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("information quantity must be finite")


@dataclass(frozen=True, slots=True)
class RhoOffset:
    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("rho offset must be finite")


@dataclass(frozen=True, slots=True)
class RhoOffsetResolutionInput:
    sensitivity: SensitivityConfiguration
    partition_true_information: InformationQuantity
    fine_partition_true_information: InformationQuantity


@dataclass(frozen=True, slots=True)
class ResolvedRhoCoordinate:
    family: RhoOffsetFamily
    base: RhoOffsetBase
    source_quantity: InformationQuantity
    offset: RhoOffset
    rho: float
    validity: ResolvedRhoValidity


def resolve_rho_offsets(input_value: RhoOffsetResolutionInput) -> tuple[ResolvedRhoCoordinate, ...]:
    offset_sets = (
        (
            RhoOffsetFamily.SHARP_SET,
            RhoOffsetBase.PARTITION_TRUE_INFORMATION,
            input_value.partition_true_information,
            input_value.sensitivity.theorem_rho_offsets.sharp_set,
        ),
        (
            RhoOffsetFamily.ORACLE_VALIDATION,
            RhoOffsetBase.PARTITION_TRUE_INFORMATION,
            input_value.partition_true_information,
            input_value.sensitivity.theorem_rho_offsets.oracle_validation,
        ),
        (
            RhoOffsetFamily.REFINEMENT_ABOVE_FINE_TAU,
            RhoOffsetBase.FINE_PARTITION_TRUE_INFORMATION,
            input_value.fine_partition_true_information,
            input_value.sensitivity.theorem_rho_offsets.refinement_above_fine_tau,
        ),
    )
    coordinates: list[ResolvedRhoCoordinate] = []
    for family, base, source_quantity, configured_offsets in offset_sets:
        for configured_offset in configured_offsets:
            offset = RhoOffset(configured_offset)
            rho = source_quantity.value + offset.value
            validity = (
                ResolvedRhoValidity.VALID
                if rho >= 0.0
                else ResolvedRhoValidity.INVALID_NEGATIVE_RHO
            )
            coordinates.append(
                ResolvedRhoCoordinate(family, base, source_quantity, offset, rho, validity)
            )
    return tuple(coordinates)
