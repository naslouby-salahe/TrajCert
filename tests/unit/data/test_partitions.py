import math

import pytest

from trajcert.data.partitions import (
    AnalysisPartition,
    HiddenHarmfulMass,
    ObservableLaw,
    PartitionBandIndex,
    ResolutionAge,
)
from trajcert.math.entropy import binary_entropy


def test_partition_and_observable_law_contract() -> None:
    partition = AnalysisPartition((1, 3, 8))
    law = ObservableLaw((0.1, 0.0, 0.1), (0.2, 0.0, 0.3), 0.3)

    assert partition.band_for_age(ResolutionAge(0)) == PartitionBandIndex(1)
    assert partition.band_for_age(ResolutionAge(3)) == PartitionBandIndex(2)
    assert partition.band_for_age(ResolutionAge(8)) == PartitionBandIndex(3)
    assert partition.band_for_age(ResolutionAge(9)) is None
    assert math.isclose(0.2, law.harmful_total)
    assert math.isclose(0.5, law.correct_total)
    assert math.isclose(law.latent_risk(HiddenHarmfulMass(0.2)), 0.4)
    assert law.resolved_harmful_rate(PartitionBandIndex(2)) is None
    assert math.isclose(
        law.resolved_entropy_sum(), 0.3 * binary_entropy(1 / 3) + 0.4 * binary_entropy(0.25)
    )
    assert binary_entropy(0.0) == 0.0
    assert math.isclose(binary_entropy(0.5), math.log(2))


def test_observable_law_rejects_invalid_simplex_and_hidden_mass() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        ObservableLaw((0.1,), (0.1,), 0.1)

    law = ObservableLaw((0.1,), (0.2,), 0.7)
    with pytest.raises(ValueError, match="hidden terminal"):
        law.latent_risk(HiddenHarmfulMass(0.8))
