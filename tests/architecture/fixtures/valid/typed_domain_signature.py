from trajcert.types import (
    BandCount,
    ClientId,
    DomainModel,
    LawKey,
    Mass,
    Probability,
    SensitivityBudget,
    SeedValue,
)


class TypedRecord(DomainModel):
    client_id: ClientId
    band_count: BandCount
    probability: Probability
    mass: Mass
    seed: SeedValue
    rho: SensitivityBudget
    law: LawKey


def summarise(
    records: tuple[TypedRecord, ...], lookup: dict[LawKey, tuple[Mass, ...]]
) -> tuple[tuple[ClientId, Mass], ...]:
    return tuple(
        (record.client_id, sum(lookup[record.law], record.mass)) for record in records
    )
