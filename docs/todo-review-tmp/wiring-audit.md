# Wiring audit

| Workflow | Entry point | Reachable chain reviewed | Leaf operations | Finding |
|---|---|---|---|---|
| Experiment run | `cli.main` → `workflows.run_experiment` | plan → runner → dispatch | scientific cell evaluators | No alternative forwarding path introduced by the diff. |
| Real trajectory | experiment preprocessing command | `workflows._preprocess_real_trajectory` → integrity/schema/eligibility → persisted cohort → dispatch cache → `evaluate_real_trajectory_cell` | empirical summary/oracle | Fully wired; the moved contract is read at preprocessing and planning through active config. |
| Reporting | report CLI action | export → source verification → table/figure render | filesystem/CSV/TeX/SVG writers | Enum serialization remains at filenames/output boundaries. |

Graphify's AST graph does not mark Pydantic validators or property access as direct call
edges. These reported zero-inbound methods are framework/property false positives;
they were retained. Manual searches verified every real-trajectory production function
is called by preprocessing, dispatch, or its evaluator.

Final Graphify extraction was refreshed after the last type fixes: 3568 nodes and
30433 edges. No production item requires missing wiring.
