from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class EvidenceDisposition(StrEnum):
    EXECUTABLE_COMPLETED = "EXECUTABLE_COMPLETED"
    PLANNED_INVALID = "PLANNED_INVALID"
    ZERO_CELL_NONAPPLICABLE = "ZERO_CELL_NONAPPLICABLE"


class EvidenceValidationState(StrEnum):
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    STALE = "STALE"
    MALFORMED = "MALFORMED"
    INVALID = "INVALID"
    PROVENANCE_INCOMPATIBLE = "PROVENANCE_INCOMPATIBLE"
    TECHNICALLY_FAILED = "TECHNICALLY_FAILED"


@dataclass(frozen=True, slots=True)
class SemanticCellEvidence:
    semantic_cell_key: str
    disposition: EvidenceDisposition
    validation_state: EvidenceValidationState
    completion_marker_digest: str | None
    dependency_fingerprint: str | None
    schema_valid: bool
    checksums_valid: bool
    dependencies_compatible: bool

    def __post_init__(self) -> None:
        if not self.semantic_cell_key:
            raise ValueError("semantic cell evidence requires a semantic cell key")
        if self.disposition is EvidenceDisposition.EXECUTABLE_COMPLETED and (
            self.completion_marker_digest is None or self.dependency_fingerprint is None
        ):
            raise ValueError("completed semantic cells require completion and dependency digests")
        if self.validation_state is EvidenceValidationState.VERIFIED and (
            self.completion_marker_digest is None or self.dependency_fingerprint is None
        ):
            raise ValueError("verified evidence requires completion and dependency digests")
        digests = (self.completion_marker_digest, self.dependency_fingerprint)
        if any(
            digest is not None and _DIGEST_PATTERN.fullmatch(digest) is None for digest in digests
        ):
            raise ValueError("evidence digests must be SHA-256 values")
        if self.validation_state is EvidenceValidationState.VERIFIED and not all(
            (self.schema_valid, self.checksums_valid, self.dependencies_compatible)
        ):
            raise ValueError(
                "verified evidence requires schema, checksum, and dependency validation"
            )


@dataclass(frozen=True, slots=True)
class EvidenceAuditInput:
    expected_semantic_cell_count: int
    cells: tuple[SemanticCellEvidence, ...]

    def __post_init__(self) -> None:
        if self.expected_semantic_cell_count <= 0:
            raise ValueError("evidence audit requires a positive planned-cell count")
        if len(self.cells) != self.expected_semantic_cell_count:
            raise ValueError("evidence audit must account for every planned semantic cell")
        keys = tuple(cell.semantic_cell_key for cell in self.cells)
        if len(set(keys)) != len(keys):
            raise ValueError("evidence audit cannot contain duplicate semantic cells")


@dataclass(frozen=True, slots=True)
class EvidenceAuditResult:
    completed_cell_count: int
    planned_invalid_cell_count: int
    zero_cell_nonapplicable_count: int
    blocking_cells: tuple[SemanticCellEvidence, ...]

    @property
    def passes(self) -> bool:
        return not self.blocking_cells


def audit_evidence(input_value: EvidenceAuditInput) -> EvidenceAuditResult:
    blocking_cells = tuple(
        cell
        for cell in input_value.cells
        if cell.validation_state is not EvidenceValidationState.VERIFIED
    )
    return EvidenceAuditResult(
        sum(
            cell.disposition is EvidenceDisposition.EXECUTABLE_COMPLETED
            for cell in input_value.cells
        ),
        sum(cell.disposition is EvidenceDisposition.PLANNED_INVALID for cell in input_value.cells),
        sum(
            cell.disposition is EvidenceDisposition.ZERO_CELL_NONAPPLICABLE
            for cell in input_value.cells
        ),
        blocking_cells,
    )
