# Artifact, cache, provenance, and reporting audit

`experiments/artifacts.py` owns semantic result paths, artifact keys, dependency
fingerprints, completion compatibility, checksum verification, and verified reads.
`CompletionRecord` is accepted only when semantic key, plan digest, specification
digest, dependency fingerprint, required/produced keys, seed completion, artifact
index, and checksums all agree. Partial, corrupt, mismatched, or path-escaping
artifacts are rejected before consumption.

`runner.execute_dispatched_cell` writes the result/index before completion; tests
cover compatible reuse, explicit overwrite, failure without completion, corrupt
completion recovery, stale dependency rejection, and checkpoint-range reuse.

`reporting/export.py` now consumes the workflow-established active configuration
context rather than independently loading configuration. It requires synthesis and
upstream completion validation before reading verified source data, stages output,
atomically replaces publication trees, validates the allowlisted results layout, and
records source/result lineage. Report refusal for missing evidence is verified with
exit code 30; it does not invoke solvers or scientific execution.
