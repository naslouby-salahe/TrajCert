# Graphify audit

Final fresh AST extraction: `graphify update . --force --no-cluster`, after all
remediation edits: 3568 extracted nodes and 59467 raw edges (3489 post-build nodes
and 28611 directed edges).

`graphify diagnose multigraph` found extraction edge-collapse characteristics (904
dangling inferred endpoints and 29952 directed same-endpoint collapses), not
repository dead-code findings. Its examples are repeated call/reference/type edges
to numerical-library symbols and a local count annotation, rather than isolated
production functionality. Manual inspection of the affected workflows found no
unexplained unreachable or unwired production code. This is the final-source-state
graph.
