from __future__ import annotations

from itertools import pairwise
from math import isfinite
from typing import Self

import numpy as np
from pydantic import model_validator

from trajcert.config import active_config
from trajcert.constants import ENDPOINT_PARTITION_NAME
from trajcert.exceptions import InvalidPartitionError
from trajcert.types import BandCount, BandIndex, DomainModel, PartitionName, TerminalHorizon, Vector


class TrajectoryPartition(DomainModel):
    name: PartitionName
    finest_band_count: BandCount
    band_count: BandCount
    terminal_horizon: TerminalHorizon
    boundaries: tuple[TerminalHorizon, ...]
    coarsening_map_from_finest: tuple[BandIndex, ...]

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        finest = self.finest_band_count
        bands = self.band_count
        horizon = self.terminal_horizon
        _validate_partition_shape(
            finest, bands, horizon, self.boundaries, self.coarsening_map_from_finest
        )
        boundary_values = self.boundaries
        if any(not isfinite(value) for value in boundary_values):
            raise InvalidPartitionError("partition boundaries must be finite")
        if any((left >= right for left, right in pairwise(boundary_values))):
            raise InvalidPartitionError("partition boundaries must be strictly increasing")
        if boundary_values[-1] != horizon:
            raise InvalidPartitionError("final partition boundary must equal the terminal horizon")
        mapped = self.coarsening_map_from_finest
        if any(value < 1 or value > bands for value in mapped):
            raise InvalidPartitionError("coarsening map contains an invalid coarse-band index")
        if mapped != _coarsening_map_values(finest, bands):
            raise InvalidPartitionError(
                "coarsening map is inconsistent with deterministic equal-width coarsening"
            )
        return self

    def coarse_band_for_finest(self, finest_band: BandIndex) -> BandIndex:
        index = finest_band
        if index < 1 or index > self.finest_band_count:
            raise InvalidPartitionError("finest-band index is outside the partition domain")
        return self.coarsening_map_from_finest[index - 1]


def _validate_partition_shape(
    finest: BandCount,
    bands: BandCount,
    horizon: TerminalHorizon,
    boundaries: tuple[TerminalHorizon, ...],
    coarsening_map: tuple[BandIndex, ...],
) -> None:
    if finest <= 0 or bands <= 0:
        raise InvalidPartitionError("partition band counts must be positive")
    if bands > finest or finest % bands != 0:
        raise InvalidPartitionError(
            "partition must be a deterministic coarsening of the finest partition"
        )
    if not isfinite(horizon) or horizon <= 0.0:
        raise InvalidPartitionError("terminal horizon must be finite and positive")
    if len(boundaries) != bands:
        raise InvalidPartitionError("partition boundary count does not match band count")
    if len(coarsening_map) != finest:
        raise InvalidPartitionError("coarsening map length does not match finest band count")


def build_partition(
    finest_band_count: BandCount, band_count: BandCount, terminal_horizon: TerminalHorizon
) -> TrajectoryPartition:
    finest = finest_band_count
    bands = band_count
    horizon = terminal_horizon
    if finest <= 0 or bands <= 0 or bands > finest or (finest % bands != 0):
        raise InvalidPartitionError("invalid finest/coarse partition relationship")
    if not isfinite(horizon) or horizon <= 0.0:
        raise InvalidPartitionError("terminal horizon must be finite and positive")
    boundaries = tuple(horizon * band_index / bands for band_index in range(1, bands + 1))
    mapping = _coarsening_map_values(finest, bands)
    return TrajectoryPartition(
        name=partition_name(bands),
        finest_band_count=finest,
        band_count=bands,
        terminal_horizon=horizon,
        boundaries=boundaries,
        coarsening_map_from_finest=mapping,
    )


def configured_partitions() -> tuple[TrajectoryPartition, ...]:
    config = active_config.get()
    finest = config.method.finest_bands
    horizon = config.method.terminal_horizon
    return tuple(
        build_partition(finest, band_count, horizon) for band_count in config.grids.partitions
    )


def partition_name(band_count: BandCount) -> PartitionName:
    bands = band_count
    if bands <= 0:
        raise InvalidPartitionError("partition band count must be positive")
    if bands == 1:
        return PartitionName(ENDPOINT_PARTITION_NAME)
    return PartitionName(f"{bands}-band partition")


def _is_refinement(fine: TrajectoryPartition, coarse: TrajectoryPartition) -> bool:
    return (
        fine.finest_band_count == coarse.finest_band_count
        and fine.terminal_horizon == coarse.terminal_horizon
        and (fine.band_count >= coarse.band_count)
        and (fine.band_count % coarse.band_count == 0)
    )


def coarsen_mass_vector(
    values: Vector, fine: TrajectoryPartition, coarse: TrajectoryPartition
) -> Vector:
    if len(values) != fine.band_count:
        raise InvalidPartitionError("mass vector length does not match fine partition")
    if not _is_refinement(fine, coarse):
        raise InvalidPartitionError("target partition is not a deterministic coarsening")
    if fine.band_count == coarse.band_count:
        return values
    ratio = fine.band_count // coarse.band_count
    return np.sum(values.reshape(-1, ratio), axis=1)


def _coarsening_map_values(finest: int, bands: int) -> tuple[int, ...]: #TODO: don't use primitive int and check why tests aren't catching it
    return tuple((fine_band * bands - 1) // finest + 1 for fine_band in range(1, finest + 1))
