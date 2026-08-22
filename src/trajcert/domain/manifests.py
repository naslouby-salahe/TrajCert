from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from trajcert.domain.identity import Identifier, LocalCertificateIdentity


class EpochManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    identity: LocalCertificateIdentity
    detector_model_identity: Identifier
    action_policy: Identifier
    adjudication_regime: Identifier
    event_logging_semantics: Identifier
    terminal_horizon_age_units: int = Field(gt=0)
    finest_trajectory_representation: Identifier

    def materially_differs_from(self, other: EpochManifest) -> bool:
        return self != other

    def close_for_material_change(self, replacement: EpochManifest) -> ClosedEpoch:
        if self.identity != replacement.identity:
            raise ValueError("epoch replacement must preserve local certificate identity")
        if not self.materially_differs_from(replacement):
            raise ValueError("an epoch closes only for a material change")
        return ClosedEpoch(closed_manifest=self, replacement_manifest=replacement)


@dataclass(frozen=True, slots=True)
class ClosedEpoch:
    closed_manifest: EpochManifest
    replacement_manifest: EpochManifest
