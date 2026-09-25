# POC Results

The raw census is implemented in [`pocs/raw_census.py`](pocs/raw_census.py); machine-readable output is [`pocs/raw_census.json`](pocs/raw_census.json). The directory is gitignored because it contains local-path-dependent diagnostics, not source data. The source CSV remains outside this repository.

## Raw-file census

- SHA-256: `162121f804c2e177dddae4fb9c91e70045aaccaa6e918adde25fc7964acb0c04`.
- 127,845 rows, 54 columns, 12 device labels, from 2024-01-15 00:00:15 through 2024-01-21 23:59:51.
- 10,227 reviewed and 117,618 unreviewed rows. Reviewed rows contain no duplicate rows under the source's five-field duplicate-check key `(timestamp, src_mac, dst_ip, src_port, dst_port)`; this is not claimed to be a verified natural event identity.
- Observed truth-positive count is 19,177; the configured documented count is 19,215. The 38-row difference is recorded by preprocessing inventory as `OBSERVED_DEVIATION`.
- In the reviewed cohort, 279 model predictions disagree with `is_attack` (2.73%) and 1,001 human decisions disagree (9.79%). The file's `ml_human_agreement` indicator matches prediction/decision agreement on all reviewed rows.
- Model error among reviewed attack rows is 16.96% (279/1,645) versus 6.12% among unreviewed attack rows (1,073/17,532); both cohorts have zero observed model errors among benign rows. This is evidence of reviewed-cohort selection, not a population estimate.
- The production inventory persists these reviewed/unreviewed attack counts and rates, and the HITL diagnostic publication table schema includes them alongside each replay row.

## Configured support gates

At the configured planned horizons, pooled and all device/expertise strata pass the current minimum gate (`n >= 200` and at least 50 resolved events). For example, the smallest expertise group has 524 reviewed rows and 260 resolved by 30 seconds. At 15 seconds, the novice group has only 3 resolved rows, but novice-at-15s is not a planned coordinate; 15 seconds is pooled-only. The 60-second horizon resolves all reviewed records.

The route remains prospective and diagnostic. Passing count gates only means the configured calculation has adequate minimum support under its operational rule; it does not establish representativeness, annotation provenance, independence, or generalization.
