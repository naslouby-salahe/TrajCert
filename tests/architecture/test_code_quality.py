import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_ruff_format_and_lint_pass() -> None:
    commands = (("ruff", "format", "--check", "."), ("ruff", "check", "."))
    for command in commands:
        completed = subprocess.run(
            command, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
