from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, model_validator

from trajcert.domain.enums import PublicExecutionState, ScientificState
from trajcert.domain.identity import Identifier, LocalCertificateIdentity


@dataclass(frozen=True, slots=True)
class PendingAction:
    event_id: Identifier
    issuing_identity: LocalCertificateIdentity


class ExecutionOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    public_execution_state: PublicExecutionState
    scientific_state: ScientificState | None = None

    @model_validator(mode="after")
    def validate_state_separation(self) -> ExecutionOutcome:
        no_evidence_states = {PublicExecutionState.FAILED, PublicExecutionState.INVALID}
        if self.public_execution_state in no_evidence_states and self.scientific_state is not None:
            raise ValueError("failed or invalid execution cannot carry scientific evidence")
        if (
            self.scientific_state is not None
            and self.public_execution_state is not PublicExecutionState.COMPLETED
        ):
            raise ValueError("scientific evidence requires completed execution")
        return self


@dataclass(frozen=True, slots=True)
class SemanticExecutionIdentity:
    semantic_cell_key: Identifier
    material_dependency_identity: Identifier

    def reusable_with(self, candidate: SemanticExecutionIdentity, *, overwrite: bool) -> bool:
        return not overwrite and self == candidate
