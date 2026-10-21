"""Reconstruct revision summaries from frozen records without running experiments.

Run from any directory with the repository Python. The only output is JSON on
stdout; redirect it to retain the verification record. No scientific file is
modified. The older audit_evidence.py additionally checks publication exports.
"""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from zipfile import ZipFile

from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[2]
SELECTED = [
    ("Strong timing contrast power", 1, 5000),
    ("Strong timing contrast power", 2, 5000),
    ("Strong timing contrast power", 1, 50000),
    ("Matched no-timing control", 2, 50000),
    ("Matched no-timing control", 8, 50000),
]


def verify():
    publication = list(csv.DictReader((ROOT / "results/experiments/anytime-certification-power/"
                                      "tables/main/certification_power.csv").open()))
    by_checkpoint = {(r["scenario_name"], int(r["K"]), int(r["n_matured"])): r
                     for r in publication}
    records, longest, medians, source_hashes = {}, {}, [], {}
    batches = incompatible = 0
    certificate_margins = []
    record_root = ROOT / "outputs/experiments/anytime-certification-power/evaluations/records"
    for path in sorted(record_root.rglob("scientific_result.json")):
        data = json.loads(path.read_text())
        source_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        execution = ROOT / str(path.parent.relative_to(ROOT)).replace(
            "evaluations/records", "checkpoints/execution")
        assert (execution / "COMPLETED.json").exists()
        outcomes = []
        for batch in sorted(execution.glob("batch_*_result.json")):
            outcomes.extend(json.loads(batch.read_text())["outcomes"])
            batches += 1
            source_hashes[str(batch.relative_to(ROOT))] = hashlib.sha256(batch.read_bytes()).hexdigest()
        assert sorted(o["stream_index"] for o in outcomes) == list(range(1000000, 1000100))
        assert sum(o["full_precision"] for o in outcomes) == 4
        assert sum(o["exclusion_matured"] is not None for o in outcomes) == data["confidence_sequence_exclusions"]
        key = data["scenario_name"], data["band_count"]
        records[key] = data, outcomes
        for checkpoint in data["checkpoints"]:
            n = checkpoint["matured_count"]
            current = [c for o in outcomes for c in o["checkpoints"] if c["matured_count"] == n]
            timed = [c for o in outcomes if not o["full_precision"]
                     for c in o["checkpoints"] if c["matured_count"] == n]
            count = sum(any(c["matured_count"] <= n and c["scientific_state"] == "CERTIFIED"
                            for c in o["checkpoints"]) for o in outcomes)
            assert count == checkpoint["trajcert_ever_certified"]
            row = by_checkpoint[*key, n]
            assert count == round(100 * float(row["ever_certified_rate"]))
            lower = 0 if count == 0 else beta.ppf(.025, count, 101-count)
            upper = 1 if count == 100 else beta.ppf(.975, count+1, 100-count)
            assert abs(lower - float(row["ever_certified_cp_lower"])) < 1e-12
            assert abs(upper - float(row["ever_certified_cp_upper"])) < 1e-12
            runtime = median(c["runtime_ms"] for c in timed)
            assert runtime == checkpoint["median_runtime_ms"]
            medians.append(runtime)
            incompatible += sum(c["scientific_state"] == "MODEL_INCOMPATIBLE" for c in current)
            assert checkpoint["trajcert"]["model_incompatible"] == 0
            certificate_margins.extend(float(row["beta"]) - c["proven_upper"]
                                       for c in current if c["scientific_state"] == "CERTIFIED")
        law_key = data["law_name"], data["band_count"]
        horizon = max(c["matured_count"] for c in data["checkpoints"])
        exclusions = tuple((o["stream_index"], o["exclusion_matured"]) for o in outcomes)
        if law_key not in longest or horizon > longest[law_key]["horizon"]:
            longest[law_key] = {"horizon": horizon, "count": data["confidence_sequence_exclusions"],
                                "exclusions": exclusions}
    decomposition = []
    for scenario, k, n in SELECTED:
        data, outcomes = records[scenario, k]
        counts = Counter()
        for outcome in outcomes:
            if outcome["full_precision"]:
                continue
            here = [c for c in outcome["checkpoints"] if c["matured_count"] == n]
            if not here:
                assert outcome["sequence_empty"]
                counts["stopped"] += 1
            elif here[0]["scientific_state"] == "CERTIFIED":
                counts["certified"] += 1
            elif here[0]["termination_reason"] == "DECISION_REFUTED":
                counts["refuted"] += 1
            else:
                assert here[0]["termination_reason"] == "STALLED"
                counts["unresolved"] += 1
        assert sum(counts.values()) == 96
        decomposition.append({"scenario": scenario, "K": k, "n": n,
                              **{label: counts[label] for label in
                                 ("certified", "refuted", "unresolved", "stopped")}})
    assert len(records) == 32 and batches == 320 and len(medians) == 160
    assert incompatible == 0
    assert len(longest) == 21 and sum(v["count"] for v in longest.values()) == 58
    assert max(v["count"] for v in longest.values()) == 6
    with ZipFile(ROOT / "paper/supplementary/evidence.zip") as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
        for item in manifest["files"]:
            assert hashlib.sha256(archive.read(item["path"])).hexdigest() == item["sha256"]
            assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    return {"power_cells": len(records), "batches": batches, "checkpoints": len(medians),
            "decomposition": decomposition, "runtime_medians_ms":
            {"median": median(medians), "maximum": max(medians),
             "over_10000": sum(x > 10000 for x in medians)},
            "long_horizon": {"sets": len(longest), "indexed_outcomes": 2100,
                             "exclusions": 58, "maximum_per_set": 6,
                             "selection": {str(k): v for k, v in longest.items()}},
            "incompatibility_detections": incompatible,
            "minimum_saved_certificate_margin": min(certificate_margins),
            "archive_payloads_verified": len(manifest["files"]),
            "source_sha256": source_hashes}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
