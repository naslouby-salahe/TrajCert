# Safe command execution audit

All actual public command help surfaces were inspected. The only commands are
`doctor`, `preprocess`, `plan`, `smoke`, `run`, `status`, and `report`; the only
public mutating control is `--overwrite` on its declared commands. No seed, rho,
beta, delta, partition, baseline, method, internal-cell, config-path, or cache-mode
selection flag exists.

| Command | Observed result | Side-effect/reuse evidence |
|---|---|---|
| `doctor` | PASS / exit 0 | Read-only checksum unchanged; structured workspace, environment, dataset, experiment, artifact-DAG, and next-action fields emitted. |
| `preprocess` | Synthetic and real production preparation passed | Typed prepared manifests/inventories written, then verified reuse. |
| `plan` | 1,738 executable cells / exit 0 | Aggregate `outputs`/`results` checksum unchanged. |
| `smoke` | PASS, 6/6 fixtures / exit 0 | Aggregate `outputs`/`results` checksum unchanged; no completed experiment family. |
| `status` | 0/29 completed, 29 blocked / exit 0 | Aggregate `outputs`/`results` checksum unchanged. |
| `report` | Missing-evidence refusal / exit 30 | Aggregate `outputs`/`results` checksum unchanged. |
| `run` | Not invoked | Prohibited during pre-experiment audit. |

The final before/after aggregate checksum for the read-only command sequence was
`75c117e38607f503a1937356f8a2c5b268192b4d0d881413d2863b1021f554ae`.

## Final WSL rerun (2026-09-25)

Doctor passed; plan returned 1,738 executable and 0 invalid cells; smoke passed 6/6;
status returned 0 complete, 0 failed, 29 blocked, and 0 running. `report` refused
missing evidence with its intended exit code 30. `preprocess hitl-iot` verified the
pinned source checksum/schema and 127,845-row inventory; 10,227 rows were eligible
and 117,618 excluded, and an immediate second invocation reused the prepared cohort.
The safe commands did not run a scientific experiment.
