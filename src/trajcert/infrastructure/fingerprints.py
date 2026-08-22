from __future__ import annotations

import hashlib

from trajcert.domain.records.execution import DependencyFingerprintInput, ProvenanceFingerprintInput
from trajcert.infrastructure.provenance import (
    canonical_dependency_payload,
    canonical_provenance_payload,
)


def provenance_fingerprint(value: ProvenanceFingerprintInput) -> str:
    return hashlib.sha256(canonical_provenance_payload(value)).hexdigest()


def dependency_fingerprint(value: DependencyFingerprintInput) -> str:
    return hashlib.sha256(canonical_dependency_payload(value)).hexdigest()
