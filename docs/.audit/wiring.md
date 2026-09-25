# Wiring audit

The public CLI has exactly the seven roadmap commands. Its parser rejects unknown
dataset and experiment names, and it exposes no scientific-selection controls. The
workflow roots load the active configuration once, derive semantic identities, and
persist only typed artifacts under the configured workspace.

The execution route is:

```text
CLI dispatch -> workflow -> plan/catalog -> runner -> typed dispatch registry
             -> artifact index/completion/provenance -> status/report
```

The report route is intentionally terminal: it reads completed evidence only and
now converts missing or unreadable evidence to the declared completion/evidence
failure class (exit 30). It does not execute missing computation.

Preprocessing has separate synthetic and real routes. Synthetic preprocessing writes
per-law typed manifests with a specification digest and checksum inventory. The real
route verifies the pinned source checksum before cache reuse, writes schema,
provenance, eligibility, prepared cohort, and documented-versus-observed dataset
inventory artifacts, then accepts reuse only when source/cohort/specification
digests and typed deserialization all remain valid.
