# Audit findings

## Resolved

1. **CFG-015 / ART-015 — competing and noncompliant dependency lock authority.**
   `requirements.lock` was absent, while code used `uv.lock`. Replaced the runtime
   authority with a pip-tools 7.6.0 hash lock, updated provenance and tests, and
   removed `uv.lock`.
2. **WIRE-010 / WIRE-018 — report evidence refusal had wrong exit class.**
   A missing synthesis completion surfaced as `SerializationError`, which CLI mapped
   to exit 20. Reporting now converts unreadable/missing evidence into the declared
   evidence failure class, producing exit 30. Regression coverage was updated.
3. **DATA-012 / DATA-013 / WIRE-005 — synthetic preprocessing was only a config copy.**
   It now persists validation-ready law manifests with probability masses and deterministic
   partition/coarsening models, verifies category probabilities, and reuses only matching,
   checksum-valid manifests.
4. **WIRE-016 / ART-011 — real preprocessing reused an existing cohort blindly.**
   Reuse now requires current source integrity, a matching specification digest, and
   checksum-valid, schema-readable prepared cohort metadata.
5. **CFG-015 — development automation retained a second lock authority.**
   Nox and CI no longer call `uv sync --locked`; they install the authoritative
   hash-locked requirements first, then the pinned quality extra. The migrated Nox
   quality session passed end to end.
6. **DATA-016 — real dataset preparation omitted documented-versus-observed values.**
   Added a typed dataset inventory with documented and observed release structures,
   discrepancy status, and field-mapping status. Real preprocessing now writes it
   before schema/eligibility preparation; the pinned raw release matched.

## Environment correction

The roadmap previously named CPython 3.13.15, but the configured Python distributor
has no such build; installed CPython 3.13.12 is the actual validated interpreter.
This is a reproducibility-environment correction, not a scientific-contract change.

## Roadmap consistency correction

The `Same Endpoint, Different Timing` grid has four partitions and six configured rho
values, including the mandatory exact log(2) endpoint. The plan and total of 1,738 were
already correct; two stale roadmap references claiming 20 cells and one claiming 1,422
total cells were corrected to 24 and 1,738, respectively. A final micro-audit found EXP-016 in the canonical matrix still claimed 20
cells; it now records the verified 24-cell design. A direct plan regression protects the
4 partitions × 6 configured rho values and preserves the 1,738-cell plan.
