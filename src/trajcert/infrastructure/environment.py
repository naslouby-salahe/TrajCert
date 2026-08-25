from __future__ import annotations

import hashlib
import importlib.metadata
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NewType

from trajcert.domain.records.artifacts import Digest, GitCommit

ContainerImageDigest = NewType("ContainerImageDigest", str)


@dataclass(frozen=True, slots=True)
class ImplementationComponentDigestInput:
    project_root: Path
    relative_paths: tuple[Path, ...]


def implementation_component_digest(input_value: ImplementationComponentDigestInput) -> Digest:
    normalized_paths = tuple(sorted(input_value.relative_paths, key=lambda path: path.as_posix()))
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ValueError("registered implementation paths must be unique")
    digest = hashlib.sha256()
    for relative_path in normalized_paths:
        absolute_path = (input_value.project_root / relative_path).resolve()
        try:
            normalized_relative_path = absolute_path.relative_to(input_value.project_root.resolve())
        except ValueError as error:
            raise ValueError("registered implementation path escapes the project root") from error
        if normalized_relative_path != relative_path or not absolute_path.is_file():
            raise ValueError("registered implementation path must name an existing project file")
        file_digest = hashlib.sha256(absolute_path.read_bytes()).hexdigest()
        digest.update(normalized_relative_path.as_posix().encode("utf-8"))
        digest.update(b"\x00")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class GitProvenance:
    commit: GitCommit
    dirty_tree: bool


@dataclass(frozen=True, slots=True)
class RuntimeEnvironmentManifest:
    python_implementation_version: str
    os_kernel: str
    cpu_model: str
    package_versions: tuple[str, ...]
    arithmetic_threading_environment: tuple[str, ...]
    container_image_digest: ContainerImageDigest


def runtime_environment_manifest() -> RuntimeEnvironmentManifest:
    package_versions = tuple(
        sorted(
            f"{distribution.metadata['Name']}=={distribution.version}"
            for distribution in importlib.metadata.distributions()
        )
    )
    arithmetic_environment = tuple(
        f"{name}={os.environ[name]}"
        for name in sorted(os.environ)
        if name
        in {"OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"}
    )
    return RuntimeEnvironmentManifest(
        f"{platform.python_implementation()} {platform.python_version()}",
        f"{platform.system()} {platform.release()}",
        platform.processor() or platform.machine(),
        package_versions,
        arithmetic_environment,
        authoritative_container_image_digest(),
    )


CONTAINER_IMAGE_DIGEST_PATTERN = re.compile(
    r"^(sha256:[0-9a-f]{64}|[A-Za-z0-9][A-Za-z0-9._:@/-]*)$"
)


def git_provenance(project_root: Path) -> GitProvenance:
    commit = _git_output(project_root, ("rev-parse", "HEAD"))
    dirty_status = _git_output(project_root, ("status", "--porcelain=v1", "--untracked-files=all"))
    if dirty_status:
        raise ValueError("claim-bearing execution requires a clean Git worktree")
    return GitProvenance(commit=commit, dirty_tree=False)


def authoritative_container_image_digest() -> ContainerImageDigest:
    value = os.environ.get("TRAJCERT_CONTAINER_IMAGE_DIGEST", "")
    if not CONTAINER_IMAGE_DIGEST_PATTERN.fullmatch(value):
        raise ValueError(
            "environment_or_prerequisite_block: missing immutable container image digest"
        )
    return ContainerImageDigest(value)


def _git_output(project_root: Path, arguments: tuple[str, ...]) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError("Git metadata is unavailable; environment_or_prerequisite_block")
    return completed.stdout.strip()
