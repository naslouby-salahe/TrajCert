from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_TERMS = ("FedCampaign", "federated campaign", "Fed Campaign")


def test_source_uses_current_project_vocabulary() -> None:
    source_files = tuple(PROJECT_ROOT.glob("src/**/*.py")) + tuple(
        PROJECT_ROOT.glob("tests/**/*.py")
    )
    for source_file in source_files:
        if source_file == Path(__file__).resolve():
            continue
        source = source_file.read_text(encoding="utf-8")
        assert not any(term in source for term in FORBIDDEN_TERMS)
