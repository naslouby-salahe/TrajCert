from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from math import isfinite

from trajcert.config import TrajCertConfig
from trajcert.constants import ENDPOINT_PARTITION_NAME
from trajcert.exceptions import InvalidPartitionError
from trajcert.types import (
    BandCount,
    BandIndex,
    Mass,
    PartitionName,
    TerminalHorizon,
)


@dataclass(frozen=True, slots=True)
class TrajectoryPartition:
    name: PartitionName
    finest_band_count: BandCount
    band_count: BandCount
    terminal_horizon: TerminalHorizon
    boundaries: tuple[TerminalHorizon, ...]
    coarsening_map_from_finest: tuple[
        BandIndex,
        ...,
    ]

    def __post_init__(self) -> None:
        finest = int(self.finest_band_count)
        bands = int(self.band_count)
        horizon = float(self.terminal_horizon)

        if finest <= 0 or bands <= 0:
            raise InvalidPartitionError("partition band counts must be positive")

        if bands > finest or finest % bands != 0:
            raise InvalidPartitionError(
                "partition must be a deterministic coarsening of the finest partition"
            )

        if not isfinite(horizon) or horizon <= 0.0:
            raise InvalidPartitionError("terminal horizon must be finite and positive")

        if len(self.boundaries) != bands:
            raise InvalidPartitionError("partition boundary count does not match band count")

        if len(self.coarsening_map_from_finest) != finest:
            raise InvalidPartitionError("coarsening map length does not match finest band count")

        boundary_values = tuple(float(value) for value in self.boundaries)

        if any(not isfinite(value) for value in boundary_values):
            raise InvalidPartitionError("partition boundaries must be finite")

        if any(left >= right for left, right in pairwise(boundary_values)):
            raise InvalidPartitionError("partition boundaries must be strictly increasing")

        if boundary_values[-1] != horizon:
            raise InvalidPartitionError("final partition boundary must equal the terminal horizon")

        mapped = tuple(int(value) for value in self.coarsening_map_from_finest)

        if any(value < 1 or value > bands for value in mapped):
            raise InvalidPartitionError("coarsening map contains an invalid coarse-band index")

        if mapped != _coarsening_map_values(
            finest,
            bands,
        ):
            raise InvalidPartitionError(
                "coarsening map is inconsistent with deterministic equal-width coarsening"
            )

    def coarse_band_for_finest(
        self,
        finest_band: BandIndex,
    ) -> BandIndex:
        index = int(finest_band)

        if index < 1 or index > int(self.finest_band_count):
            raise InvalidPartitionError("finest-band index is outside the partition domain")

        return self.coarsening_map_from_finest[index - 1]


def build_partition(
    finest_band_count: BandCount,
    band_count: BandCount,
    terminal_horizon: TerminalHorizon,
) -> TrajectoryPartition:
    finest = int(finest_band_count)
    bands = int(band_count)
    horizon = float(terminal_horizon)

    if finest <= 0 or bands <= 0 or bands > finest or finest % bands != 0:
        raise InvalidPartitionError("invalid finest/coarse partition relationship")

    if not isfinite(horizon) or horizon <= 0.0:
        raise InvalidPartitionError("terminal horizon must be finite and positive")

    boundaries = tuple(
        TerminalHorizon(horizon * band_index / bands)
        for band_index in range(
            1,
            bands + 1,
        )
    )

    mapping = tuple(
        BandIndex(value)
        for value in _coarsening_map_values(
            finest,
            bands,
        )
    )

    return TrajectoryPartition(
        name=partition_name(BandCount(bands)),
        finest_band_count=BandCount(finest),
        band_count=BandCount(bands),
        terminal_horizon=TerminalHorizon(horizon),
        boundaries=boundaries,
        coarsening_map_from_finest=mapping,
    )


def configured_partitions(
    config: TrajCertConfig,
) -> tuple[TrajectoryPartition, ...]:
    finest = BandCount(config.method.finest_bands)
    horizon = TerminalHorizon(config.method.terminal_horizon)

    return tuple(
        build_partition(
            finest,
            BandCount(band_count),
            horizon,
        )
        for band_count in config.grids.partitions
    )


def partition_name(
    band_count: BandCount,
) -> PartitionName:
    bands = int(band_count)

    if bands <= 0:
        raise InvalidPartitionError("partition band count must be positive")

    if bands == 1:
        return PartitionName(ENDPOINT_PARTITION_NAME)

    return PartitionName(f"{bands}-band partition")


def _is_refinement(
    fine: TrajectoryPartition,
    coarse: TrajectoryPartition,
) -> bool:
    return (
        fine.finest_band_count == coarse.finest_band_count
        and fine.terminal_horizon == coarse.terminal_horizon
        and int(fine.band_count) >= int(coarse.band_count)
        and int(fine.band_count) % int(coarse.band_count) == 0
    )


def coarsen_mass_vector(
    values: tuple[Mass, ...],
    fine: TrajectoryPartition,
    coarse: TrajectoryPartition,
) -> tuple[Mass, ...]:
    if len(values) != int(fine.band_count):
        raise InvalidPartitionError("mass vector length does not match fine partition")

    if not _is_refinement(
        fine,
        coarse,
    ):
        raise InvalidPartitionError("target partition is not a deterministic coarsening")

    if fine.band_count == coarse.band_count:
        return values

    ratio = int(fine.band_count) // int(coarse.band_count)

    result: list[Mass] = []

    for coarse_zero_index in range(int(coarse.band_count)):
        start = coarse_zero_index * ratio
        stop = start + ratio

        result.append(Mass(sum(float(value) for value in values[start:stop])))

    return tuple(result)


def _coarsening_map_values(
    finest: int,
    bands: int,
) -> tuple[int, ...]:
    return tuple(
        ((fine_band * bands - 1) // finest) + 1
        for fine_band in range(
            1,
            finest + 1,
        )
    )
