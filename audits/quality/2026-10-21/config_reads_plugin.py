import json, sys
from collections import defaultdict
from pathlib import Path
from tempfile import mkdtemp
from trajcert.config import ConfigModel

READS = defaultdict(set)
ORIGINAL = ConfigModel.__getattribute__
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path(mkdtemp(prefix="trajcert-config-reads-"))


def tracked(self, name):
    value = ORIGINAL(self, name)
    cls = object.__getattribute__(self, "__class__")
    if name in cls.model_fields:
        frame = sys._getframe(1)
        filename = frame.f_code.co_filename
        if filename.startswith(str(ROOT / "src")) and filename != str(
            ROOT / "src/trajcert/config.py"
        ):
            READS[cls.__name__ + "." + name].add(
                str(Path(filename).relative_to(ROOT)) + ":" + str(frame.f_lineno)
            )
    return value


def pytest_sessionstart():
    ConfigModel.__getattribute__ = tracked


def pytest_sessionfinish():
    ConfigModel.__getattribute__ = ORIGINAL
    (OUTPUT_DIR / "runtime-config-reads.json").write_text(
        json.dumps({k: sorted(v) for k, v in sorted(READS.items())}, indent=2)
    )
    print("Configuration trace:", OUTPUT_DIR / "runtime-config-reads.json")
