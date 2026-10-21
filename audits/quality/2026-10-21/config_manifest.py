import ast, json
from collections.abc import Mapping
from pathlib import Path
from trajcert import config as module
from trajcert.config import ConfigModel, TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH

out = Path(__file__).resolve().parent
root = out.parents[2]
_COLUMN_MAPPING = "column mapping"
reads = json.loads((out / "runtime-config-reads.json").read_text())
manual = {
    "DecisionValueConfig.beta": ("execution", "src/trajcert/experiments/dispatch.py:616"),
    "NumericsConfig.projection_refinement_candidates": (
        "execution",
        "src/trajcert/experiments/anytime.py:1328",
    ),
    "NumericsConfig.projection_refinement_steps": (
        "execution",
        "src/trajcert/experiments/anytime.py:1329",
    ),
    "NumericsConfig.compatibility_floor_offset": (
        "execution",
        "src/trajcert/experiments/dispatch.py:360",
    ),
    "BenchmarkConfig.outer_sample_size": ("execution", "src/trajcert/experiments/scaling.py:282"),
    "BenchmarkConfig.scaling_information_margin": (
        "execution",
        "src/trajcert/experiments/scaling.py:251",
    ),
    "HandCaseOptimizerFallbackConfig.case_index": (
        "diagnostic identity",
        "src/trajcert/experiments/anytime.py:1341",
    ),
    "HandCaseOptimizerFallbackConfig.event_count": (
        "execution",
        "src/trajcert/experiments/anytime.py:1296",
    ),
    "HandCaseOptimizerFallbackConfig.rho_margin": (
        "execution",
        "src/trajcert/experiments/anytime.py:1319",
    ),
    "HandCasesConfig.optimizer_fallback": ("execution", "src/trajcert/experiments/anytime.py:1292"),
    "RealTrajectoryColumnConfig.device_type": (
        _COLUMN_MAPPING,
        "src/trajcert/data/real_trajectories.py:502",
    ),
    "RealTrajectoryColumnConfig.annotator_id": (
        _COLUMN_MAPPING,
        "src/trajcert/data/real_trajectories.py:503",
    ),
    "RealTrajectoryColumnConfig.human_confidence": (
        _COLUMN_MAPPING,
        "src/trajcert/data/real_trajectories.py:507",
    ),
    "ConfidenceConfig.level": ("validation and provenance", "src/trajcert/config.py:138"),
    "ConfidenceConfig.alpha": ("validation and provenance", "src/trajcert/config.py:139"),
    "GridsConfig.beta": ("validated reference grid and provenance", "src/trajcert/config.py:321"),
    "TrajCertConfig.schema_version": (
        "schema validation and provenance",
        "src/trajcert/config.py:836",
    ),
    "CertificationPowerConfig.checkpoints": ("execution resolver", "src/trajcert/config.py:488"),
    "CertificationPowerScenarioConfig.checkpoints": (
        "execution resolver",
        "src/trajcert/config.py:488",
    ),
    "StrictTimingCaseConfig.expectation": (
        "expected outcome check",
        "src/trajcert/experiments/dispatch.py:233",
    ),
}
internal = {}
for node in ast.walk(ast.parse((root / "src/trajcert/config.py").read_text())):
    if isinstance(node, ast.Attribute):
        internal.setdefault(node.attr, []).append("src/trajcert/config.py:" + str(node.lineno))
rows = []
for name, cls in vars(module).items():
    if isinstance(cls, type) and issubclass(cls, ConfigModel) and cls is not ConfigModel:
        for field in cls.model_fields:
            key = name + "." + field
            role = "execution or reporting"
            evidence = reads.get(key, [])
            basis = "observed source read during full test run"
            if key in manual:
                role, location = manual[key]
                evidence = sorted(set(evidence + [location]))
                basis = "reviewed model-qualified consumer" + (
                    "; runtime observation" if key in reads else ""
                )
            elif "Overrides" in name:
                role = "execution size override"
                evidence = internal.get(field, [])
                basis = "reviewed override application in config.py:960-1050"
            if not evidence:
                raise AssertionError("Unaccounted field " + key)
            rows.append(
                {"model_field": key, "role": role, "basis": basis, "consumer_locations": evidence}
            )
bykey = {x["model_field"]: x for x in rows}
instances = []


def walk(value, path):
    if isinstance(value, ConfigModel):
        for f in type(value).model_fields:
            key = type(value).__name__ + "." + f
            v = getattr(value, f)
            instances.append(
                {
                    "path": path + "." + f if path else f,
                    "model_field": key,
                    "role": bykey[key]["role"],
                }
            )
            walk(v, path + "." + f if path else f)
    elif isinstance(value, Mapping):
        for k, v in value.items():
            walk(v, path + "[" + str(k) + "]")
    elif isinstance(value, (tuple, list)):
        for i, v in enumerate(value):
            walk(v, path + "[" + str(i) + "]")


walk(TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH), "")
record = {
    "declared_model_fields": len(rows),
    "runtime_observed_model_fields": len(reads),
    "canonical_field_instances": len(instances),
    "unaccounted_fields": [],
    "fields": rows,
    "canonical_instances": instances,
    "limits": "Shared model-field consumers do not imply every campaign cell or every canonical value was executed. Runtime tracing excludes config.py and spawned workers. The remaining consumers were reviewed statically. No experimental campaign was run.",
}
(out / "configuration-usage.json").write_text(json.dumps(record, indent=2))
print({k: v for k, v in record.items() if k not in ("fields", "canonical_instances")})
