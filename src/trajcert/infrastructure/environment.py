from __future__ import annotations

import hashlib
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
