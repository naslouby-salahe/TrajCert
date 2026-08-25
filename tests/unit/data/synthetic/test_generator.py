import ast
from pathlib import Path
from typing import cast

import pytest

from trajcert.data.synthetic.generator import (
    SyntheticEvent,
    SyntheticStreamGenerationInput,
    generate_synthetic_stream,
)
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_seeded_stream_is_iid_deterministic_and_hides_terminal_labels() -> None:
    law = SyntheticTrajectoryLaw("terminal", 0.5, 1.0, 1.0, 0.0, 0.0, 2, 10.0)
    stream = generate_synthetic_stream(SyntheticStreamGenerationInput(law, 7, 4)).events

    assert stream == generate_synthetic_stream(SyntheticStreamGenerationInput(law, 7, 4)).events
    assert tuple(event.action_index for event in stream) == (0, 1, 2, 3)
    assert all(event.admitted and event.resolution_band is None for event in stream)
    assert all(event.observed_label is None for event in stream)


def test_synthetic_events_reject_non_boolean_labels() -> None:
    with pytest.raises(ValueError, match="boolean"):
        SyntheticEvent(0, cast(bool, 1), 1, True)


def test_synthetic_generator_uses_a_local_pcg64_generator() -> None:
    tree = ast.parse(
        (PROJECT_ROOT / "src/trajcert/data/synthetic/generator.py").read_text(encoding="utf-8")
    )
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    calls = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
    }

    assert "random" not in imported_modules
    assert {"Generator", "PCG64"}.issubset(calls)
