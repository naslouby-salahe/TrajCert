from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_MODULE_STEMS = frozenset({"common", "helpers", "misc", "stuff", "utils"})


def test_production_module_names_are_descriptive_and_canonical() -> None:
    for source_file in (PROJECT_ROOT / "src/trajcert").glob("**/*.py"):
        if source_file.name == "__init__.py":
            continue
        assert source_file.stem not in FORBIDDEN_MODULE_STEMS
        assert source_file.stem.replace("_", "").isalnum()
