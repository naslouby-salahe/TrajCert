import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_strict_pyright_passes() -> None:
    completed = subprocess.run(
        ["pyright"], cwd=PROJECT_ROOT, check=False, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
