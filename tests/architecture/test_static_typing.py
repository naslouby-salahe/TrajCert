import subprocess
from pathlib import Path
from shutil import which

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_strict_pyright_passes() -> None:
    executable = which("pyright") or str(Path.home() / ".local" / "bin" / "pyright")
    completed = subprocess.run(
        [executable], cwd=PROJECT_ROOT, check=False, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
