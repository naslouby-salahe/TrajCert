from __future__ import annotations

import math
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from trajcert.configuration.models import MethodConfiguration, SyntheticDataConfiguration
from trajcert.data.partitions import ObservableLaw
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import atomic_write_bytes
from trajcert.math.information_profile import InformationProfile

SYNTHETIC_LAW_CATALOG_RELATIVE_PATH = Path(
    "outputs/preprocessing/metadata/synthetic_law_catalog.json"
)
SYNTHETIC_SCALING_CATALOG_RELATIVE_PATH = Path(
    "outputs/preprocessing/metadata/synthetic_scaling_law_catalog.json"
)
SYNTHETIC_LAW_CATALOG_MANIFEST_RELATIVE_PATH = Path(
    "outputs/preprocessing/metadata/synthetic_law_catalog.manifest.json"
)
SYNTHETIC_SCALING_CATALOG_MANIFEST_RELATIVE_PATH = Path(
    "outputs/preprocessing/metadata/synthetic_scaling_law_catalog.manifest.json"
)


@dataclass(frozen=True, slots=True)
class SyntheticLawCatalogManifest:
    catalog_type: str
    semantic_identity: str
    dependency_identity: str
    content_digest: str
    payload_relative_path: str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class SyntheticTrajectoryLaw:
    name: str
    theta: float
    q1: float
    q0: float
    lambda1: float
    lambda0: float
    resolved_band_count: int
    terminal_horizon: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("synthetic law name must be nonempty")
        if self.resolved_band_count < 1 or self.terminal_horizon <= 0:
            raise ValueError("synthetic law requires positive band count and terminal horizon")
        if any(not 0 <= value <= 1 for value in (self.theta, self.q1, self.q0)):
            raise ValueError("synthetic probabilities must lie in [0, 1]")
        if any(not math.isfinite(value) for value in (self.lambda1, self.lambda0)):
            raise ValueError("synthetic timing slopes must be finite")

    def resolution_weights(self, slope: float) -> tuple[float, ...]:
        centered = tuple(
            slope * (index - (self.resolved_band_count + 1) / 2)
            for index in range(1, self.resolved_band_count + 1)
        )
        offset = max(centered)
        unnormalized = tuple(math.exp(value - offset) for value in centered)
        normalizer = sum(unnormalized)
        return tuple(value / normalizer for value in unnormalized)

    def conditional_resolution_masses(self, label: bool) -> tuple[float, ...]:
        terminal_probability = self.q1 if label else self.q0
        slope = self.lambda1 if label else self.lambda0
        return tuple(
            (1 - terminal_probability) * weight for weight in self.resolution_weights(slope)
        )

    def conditional_terminal_mass(self, label: bool) -> float:
        return self.q1 if label else self.q0

    def observable_law(self) -> ObservableLaw:
        harmful_masses = tuple(
            self.theta * mass for mass in self.conditional_resolution_masses(True)
        )
        correct_masses = tuple(
            (1 - self.theta) * mass for mass in self.conditional_resolution_masses(False)
        )
        unresolved_mass = self.theta * self.conditional_terminal_mass(True) + (
            1 - self.theta
        ) * self.conditional_terminal_mass(False)
        return ObservableLaw(harmful_masses, correct_masses, unresolved_mass)

    def band_horizons(self) -> tuple[float, ...]:
        return tuple(
            index * self.terminal_horizon / self.resolved_band_count
            for index in range(1, self.resolved_band_count + 1)
        )

    def with_resolved_band_count(self, resolved_band_count: int) -> SyntheticTrajectoryLaw:
        return SyntheticTrajectoryLaw(
            self.name,
            self.theta,
            self.q1,
            self.q0,
            self.lambda1,
            self.lambda0,
            resolved_band_count,
            self.terminal_horizon,
        )

    def minimum_information_completion(self) -> SyntheticTrajectoryLaw:
        observable_law = self.observable_law()
        compatibility_floor = InformationProfile(observable_law).compatibility_floor()
        hidden_harmful_mass = compatibility_floor.hidden_harmful_mass
        if hidden_harmful_mass is None:
            raise ValueError("minimum-information completion requires resolved mass")
        harmful_probability = observable_law.harmful_total + hidden_harmful_mass
        correct_probability = 1 - harmful_probability
        return SyntheticTrajectoryLaw(
            f"Minimum-information completion of {self.name}",
            harmful_probability,
            hidden_harmful_mass / harmful_probability,
            (observable_law.c - hidden_harmful_mass) / correct_probability,
            self.lambda1,
            self.lambda0,
            self.resolved_band_count,
            self.terminal_horizon,
        )


def synthetic_law_catalog(
    synthetic_data: SyntheticDataConfiguration,
    method: MethodConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    base_laws = tuple(
        SyntheticTrajectoryLaw(
            law.name,
            law.theta,
            law.q1,
            law.q0,
            law.lambda1,
            law.lambda0,
            method.primary_finest_resolved_bands,
            float(method.synthetic_terminal_horizon_age_units),
        )
        for law in synthetic_data.laws
    )
    derived_sources = set(synthetic_data.minimum_information_completion_laws)
    return base_laws + tuple(
        law.minimum_information_completion() for law in base_laws if law.name in derived_sources
    )


def synthetic_scaling_laws(
    law: SyntheticTrajectoryLaw,
    resolved_band_counts: tuple[int, ...],
) -> tuple[SyntheticTrajectoryLaw, ...]:
    if not resolved_band_counts:
        raise ValueError("synthetic scaling requires at least one resolved-band count")
    return tuple(
        law.with_resolved_band_count(resolved_band_count)
        for resolved_band_count in resolved_band_counts
    )


def canonical_synthetic_law_catalog(
    laws: tuple[SyntheticTrajectoryLaw, ...],
) -> bytes:
    return canonical_json_bytes(
        tuple(_synthetic_law_table_row(law) for law in sorted(laws, key=lambda law: law.name))
    )


def write_synthetic_law_catalog(
    project_root: Path,
    laws: tuple[SyntheticTrajectoryLaw, ...],
) -> str:
    payload = canonical_synthetic_law_catalog(laws)
    digest = atomic_write_bytes(
        project_root / SYNTHETIC_LAW_CATALOG_RELATIVE_PATH,
        payload,
        lambda candidate: _validate_synthetic_law_catalog(candidate, laws),
    )
    _write_synthetic_law_catalog_manifest(
        project_root,
        "synthetic-law-catalog",
        SYNTHETIC_LAW_CATALOG_RELATIVE_PATH,
        laws,
    )
    return digest


def synthetic_law_catalog_manifest(
    catalog_type: str,
    payload_relative_path: Path,
    laws: tuple[SyntheticTrajectoryLaw, ...],
) -> SyntheticLawCatalogManifest:
    payload = canonical_synthetic_law_catalog(laws)
    source_names = tuple(sorted(law.name for law in laws))
    semantic_identity = canonical_json_bytes(
        {"catalog_type": catalog_type, "law_names": source_names}
    ).decode("utf-8")
    dependency_identity = sha256(
        canonical_json_bytes(
            tuple(
                {
                    "K": law.resolved_band_count,
                    "lambda0": law.lambda0,
                    "lambda1": law.lambda1,
                    "q0": law.q0,
                    "q1": law.q1,
                    "theta": law.theta,
                }
                for law in sorted(laws, key=lambda law: law.name)
            )
        )
    ).hexdigest()
    return SyntheticLawCatalogManifest(
        catalog_type,
        semantic_identity,
        dependency_identity,
        sha256(payload).hexdigest(),
        payload_relative_path.as_posix(),
    )


def write_synthetic_scaling_catalog(
    project_root: Path,
    law: SyntheticTrajectoryLaw,
    resolved_band_counts: tuple[int, ...],
) -> str:
    laws = synthetic_scaling_laws(law, resolved_band_counts)
    payload = canonical_synthetic_law_catalog(laws)
    digest = atomic_write_bytes(
        project_root / SYNTHETIC_SCALING_CATALOG_RELATIVE_PATH,
        payload,
        lambda candidate: _validate_synthetic_law_catalog(candidate, laws),
    )
    _write_synthetic_law_catalog_manifest(
        project_root,
        "synthetic-scaling-law-catalog",
        SYNTHETIC_SCALING_CATALOG_RELATIVE_PATH,
        laws,
    )
    return digest


def _write_synthetic_law_catalog_manifest(
    project_root: Path,
    catalog_type: str,
    payload_relative_path: Path,
    laws: tuple[SyntheticTrajectoryLaw, ...],
) -> str:
    manifest_path = (
        SYNTHETIC_LAW_CATALOG_MANIFEST_RELATIVE_PATH
        if catalog_type == "synthetic-law-catalog"
        else SYNTHETIC_SCALING_CATALOG_MANIFEST_RELATIVE_PATH
    )
    manifest = synthetic_law_catalog_manifest(catalog_type, payload_relative_path, laws)
    payload = canonical_json_bytes(
        {
            "catalog_type": manifest.catalog_type,
            "content_digest": manifest.content_digest,
            "dependency_identity": manifest.dependency_identity,
            "payload_relative_path": manifest.payload_relative_path,
            "schema_version": manifest.schema_version,
            "semantic_identity": manifest.semantic_identity,
        }
    )
    return atomic_write_bytes(
        project_root / manifest_path,
        payload,
        lambda candidate: _validate_synthetic_law_catalog_manifest(candidate, manifest),
    )


def _synthetic_law_table_row(law: SyntheticTrajectoryLaw) -> dict[str, JSONValue]:
    observable_law = law.observable_law()
    return {
        "conditional_terminal_mass_label_0": law.conditional_terminal_mass(False),
        "conditional_terminal_mass_label_1": law.conditional_terminal_mass(True),
        "correct_masses": observable_law.correct_masses,
        "harmful_masses": observable_law.harmful_masses,
        "lambda0": law.lambda0,
        "lambda1": law.lambda1,
        "name": law.name,
        "q0": law.q0,
        "q1": law.q1,
        "resolved_band_count": law.resolved_band_count,
        "terminal_horizon": law.terminal_horizon,
        "unresolved_mass": observable_law.unresolved_mass,
        "theta": law.theta,
    }


def _validate_synthetic_law_catalog(
    payload: bytes,
    laws: tuple[SyntheticTrajectoryLaw, ...],
) -> None:
    if payload != canonical_synthetic_law_catalog(laws):
        raise ValueError("synthetic law catalog payload is not canonical")


def _validate_synthetic_law_catalog_manifest(
    payload: bytes,
    manifest: SyntheticLawCatalogManifest,
) -> None:
    expected = canonical_json_bytes(
        {
            "catalog_type": manifest.catalog_type,
            "content_digest": manifest.content_digest,
            "dependency_identity": manifest.dependency_identity,
            "payload_relative_path": manifest.payload_relative_path,
            "schema_version": manifest.schema_version,
            "semantic_identity": manifest.semantic_identity,
        }
    )
    if payload != expected:
        raise ValueError("synthetic law catalog manifest payload is not canonical")


@dataclass(frozen=True, slots=True)
class SyntheticLawRoles:
    utility_and_coherence: tuple[str, ...]
    sharpness_oracle: tuple[str, ...]
    safety_and_impossibility: tuple[str, ...]


def synthetic_law_roles(synthetic_data: SyntheticDataConfiguration) -> SyntheticLawRoles:
    return SyntheticLawRoles(
        synthetic_data.utility_and_coherence_laws,
        synthetic_data.sharpness_oracle_laws,
        synthetic_data.safety_and_impossibility_laws,
    )
