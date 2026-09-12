# Enum audit

Closed domains reviewed in the diff: partition labels, config filenames, seed grammar,
dataset identity, real-trajectory strata, coordinate names/grammar, publication
regimes, report extensions, telemetry labels, and skeleton leaves. All use existing or
new `StrEnum` types internally. Open display text, dataset contract fields, generated
slugs, hashes, and CSV column names deliberately remain distinct aliases rather than
false enums. No introduced `.value` unwrapping remains.
