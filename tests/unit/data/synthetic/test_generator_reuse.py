from trajcert.data.synthetic.generator import (
    SyntheticStreamGenerationInput,
    ValidatedEventStream,
    ValidatedStreamReuseInput,
    generate_synthetic_stream,
    reuse_or_extend_validated_stream,
)
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw


def test_validated_stream_can_be_reused_as_a_shorter_prefix_or_extended() -> None:
    law = SyntheticTrajectoryLaw("test", 0.4, 0.1, 0.2, 0.3, -0.1, 2, 10.0)
    longer = reuse_or_extend_validated_stream(
        ValidatedStreamReuseInput(None, law, "synthetic-v1", 17, 8)
    )
    shorter = reuse_or_extend_validated_stream(
        ValidatedStreamReuseInput(longer, law, "synthetic-v1", 17, 3)
    )
    extended = reuse_or_extend_validated_stream(
        ValidatedStreamReuseInput(shorter, law, "synthetic-v1", 17, 10)
    )

    assert shorter.events == longer.events[:3]
    assert (
        extended.events
        == generate_synthetic_stream(SyntheticStreamGenerationInput(law, 17, 10)).events
    )


def test_stream_reuse_rejects_different_identity_or_nonsemantic_prefix() -> None:
    law = SyntheticTrajectoryLaw("test", 0.4, 0.1, 0.2, 0.3, -0.1, 2, 10.0)
    stream = reuse_or_extend_validated_stream(
        ValidatedStreamReuseInput(None, law, "synthetic-v1", 17, 3)
    )

    try:
        reuse_or_extend_validated_stream(
            ValidatedStreamReuseInput(stream, law, "synthetic-v2", 17, 3)
        )
    except ValueError as error:
        assert "generator and seed" in str(error)
    else:
        raise AssertionError("a changed generator identity must reject reuse")

    invalid = ValidatedEventStream(
        "synthetic-v1",
        17,
        generate_synthetic_stream(SyntheticStreamGenerationInput(law, 18, 3)).events,
    )
    try:
        reuse_or_extend_validated_stream(
            ValidatedStreamReuseInput(invalid, law, "synthetic-v1", 17, 3)
        )
    except ValueError as error:
        assert "validated prefix" in str(error)
    else:
        raise AssertionError("a different semantic stream must reject reuse")
