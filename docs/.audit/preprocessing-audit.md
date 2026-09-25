# Preprocessing audit

Synthetic preprocessing was executed with overwrite and then without overwrite. It
materialized 12 typed prepared-law manifests with validated masses, partitions,
specification digest, and per-manifest SHA-256 values; the rerun reused the current
inventory.

Real `hitl-iot` preprocessing was executed with overwrite and then without
overwrite. The raw release checksum was
`162121f804c2e177dddae4fb9c91e70045aaccaa6e918adde25fc7964acb0c04`.
The persisted inventory records one source file, 127,845 observed rows, twelve
device labels, the raw schema, the five-field duplicate-check key, and the distinct
`decision_time` field. The source README documents 19,215 attack rows while the
observed CSV contains 19,177; the 38-row deviation is preserved. Eligibility
selected 10,227 human-reviewed rows; all five annotated-row quality exclusions were
zero, while 117,618 non-reviewed rows were explicitly excluded rather than treated
as unresolved. The five-field key is a duplicate-check key, not a verified natural
event identity.

Reuse requires current raw checksum verification, typed cohort deserialization,
matching specification digest, and matching cohort checksum. It does not accept an
existing path merely because it exists.
