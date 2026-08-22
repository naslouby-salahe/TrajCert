from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


def implementation_component_digest(project_root: Path, relative_paths: tuple[Path, ...]) -> str:
    normalized_paths = tuple(sorted(relative_paths, key=lambda path: path.as_posix()))
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ValueError("registered implementation paths must be unique")
    digest = hashlib.sha256()
    for relative_path in normalized_paths:
        absolute_path = (project_root / relative_path).resolve()
        try:
            normalized_relative_path = absolute_path.relative_to(project_root.resolve())
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


def scientific_dependency_digest(
    clause_text: tuple[str, ...],
    configuration_fragments: tuple[bytes, ...],
) -> str:
    if not clause_text:
        raise ValueError("scientific dependency digest requires at least one clause")
    digest = hashlib.sha256()
    for clause in clause_text:
        if not clause:
            raise ValueError("scientific dependency clauses must be nonempty")
        digest.update(clause.encode("utf-8"))
        digest.update(b"\x00")
    for fragment in configuration_fragments:
        digest.update(fragment)
        digest.update(b"\x00")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class GitProvenance:
    commit: str
    dirty_tree: bool


CONTAINER_IMAGE_DIGEST_PATTERN = re.compile(
    r"^(sha256:[0-9a-f]{64}|[A-Za-z0-9][A-Za-z0-9._:@/-]*)$"
)


def git_provenance(project_root: Path) -> GitProvenance:
    commit = _git_output(project_root, ("rev-parse", "HEAD"))
    dirty_status = _git_output(project_root, ("status", "--porcelain=v1", "--untracked-files=all"))
    if dirty_status:
        raise ValueError("claim-bearing execution requires a clean Git worktree")
    return GitProvenance(commit=commit, dirty_tree=False)


def authoritative_container_image_digest() -> str:
    value = os.environ.get("TRAJCERT_CONTAINER_IMAGE_DIGEST", "")
    if not CONTAINER_IMAGE_DIGEST_PATTERN.fullmatch(value):
        raise ValueError(
            "environment_or_prerequisite_block: missing immutable container image digest"
        )
    return value


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
