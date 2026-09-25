# Sequential Utility Power and Precision Design

## Decision and claim gate

The replication unit is one IID synthetic event stream. Finest-path and endpoint-only methods use that same stream, so the paired within-stream difference is analyzed; checkpoints within a stream are not independent observations.

The prospective design target is an absolute certified-update-fraction paired gain of **0.07**. This seven-percentage-point value was fixed before campaign execution as a rounded methodological sensitivity informed by the pre-campaign precision/power analysis, two points above the unchanged **0.05** observed-effect materiality floor. It is not an empirically validated domain threshold, a claimed minimum worthwhile application effect, or evidence of effectiveness. The power target is **80%** for the complete claim requiring three qualifying laws. This target is proportionate for the theory/methods study and tests sensitivity under the declared synthetic laws; the power analysis deliberately challenges each of three supporting comparisons at the harshest Holm step.

The implemented claim gate remains unchanged. Its test null is the one-sided paired-mean null E[D] <= 0 against E[D] > 0; a law qualifies if at least one of its three rho conditions has (1) observed mean certified-update-fraction gain at least 0.05, (2) a 95% paired percentile-bootstrap lower endpoint above zero, and (3) Holm-adjusted p-value below 0.05. At least three of six laws must qualify. The 0.05 condition is an observed-effect filter, not the inferential null. The sign-flip p-values are asymptotically valid under the IID/bounded stream-level conditions, not finite-sample exact absent sign symmetry; see docs/.audit/sign-flip-validity.md. Accordingly, the design does not promise 80% power at exactly 0.05; at the boundary, the observed-effect filter alone has approximately one-half probability per law.

The utility family remains the prespecified Cartesian product `6 laws × 3 rho values × 3 metrics = 54 tests`, with one-sided alpha 0.05 and Holm adjustment. The first Holm step is `0.05/54 = 0.000925926`. The power calculation conservatively requires each of three designated law-level supporting comparisons to clear this first step, even though later Holm steps are less stringent. For each supporting law it counts only one prespecified rho as having the planning alternative; it does not use the three-rho search to inflate power.

## Paired precision

The conservative design model uses independent paired differences `D ∈ {-1,+1}`. For a mean gain μ, it has variance `1-μ²`, the maximum possible variance of a variable in `[-1,1]` at that mean. This models the pairing directly and bounds variance without assuming independent method outcomes. Time to first certification is recorded from 200 through 2,000 matured events, with never-certified coded as 2,001; its paired difference lies in `[-1,801,1,801]` and has worst-case SD 1,801.

| Paired metric | Difference range | Worst-case SD | n=500 SE / 95% half-width | n=6,000 SE / 95% half-width |
|---|---:|---:|---:|---:|
| Certified-update-fraction gain | [-1, 1] | 1.000 | 0.0447 / 0.0875 | 0.0129 / 0.0253 |
| Mean anytime upper-risk gain | [-1, 1] | 1.000 | 0.0447 / 0.0875 | 0.0129 / 0.0253 |
| Time-to-first-certification gain | [-1,801, 1,801] | 1,801 | 80.59 / 158.0 events | 23.25 / 45.58 events |

These are conservative, pointwise normal-approximation precision summaries for the paired mean, not the implemented sign-flip test and not simultaneous 54-interval coverage. For a fraction gain of 0.07, the exact worst-case model gives a paired SE of about 0.0129 at 6,000 streams; the 95% pointwise half-width is about 0.0253. This resolves seven-point gains at useful precision while keeping the five-point materiality filter fixed.

## Exact integration of design-only gate power

[`../.audit/sequential_utility_power_design.py`](../.audit/sequential_utility_power_design.py) is a `DESIGN_ONLY` calculation. It generates no TrajCert event streams and writes no experiment results. It integrates over the binomial count of positive paired differences under the `{-1,+1}` model, the configured 20,000 Monte Carlo sign flips and plus-one p-value, the configured 10,000 paired-bootstrap resamples and implemented percentile endpoint, the observed-mean materiality filter, and the conservative first Holm cutoff. The complete gate power is then combined across the minimum three supporting laws under independent stream samples. The design assumes exactly three laws have one rho condition at the planning alternative; it does not count favorable outcomes from other laws or rho values.

Here, exact describes integration under the stated design distribution and implemented Monte Carlo gate; it does not claim finite-sample exactness of sign-flip p-values under every mean-zero distribution. The exact calculation gives:

| Streams per condition | Paired fraction SE bound | Pointwise 95% half-width | Full gate at true gain 0.05 | Full gate at true gain 0.07 |
|---:|---:|---:|---:|---:|
| 500 | 0.0447 | 0.0875 | 0.0008% | — |
| 5,272 (minimum for 80%) | 0.0138 | 0.0270 | — | 80.00% |
| 6,000 (selected) | 0.0129 | 0.0253 | 12.90% | 83.40% |

The per-law full-gate probability at `n=6,000`, true gain `0.07` is 0.941272. Cubing this gives 0.833959 for the three designated supporting laws. The smallest integer count reaching the 80% target is 5,272; rounding up to the next thousand gives the selected 6,000 streams. At exactly 0.05, the full gate has approximately 12.90% three-law power because each law must first pass the observed-mean threshold. These calculations do not convert the planning alternative into scientific evidence or justify interpreting a null at a different true effect as proof of no benefit.

The configured count is the single source of truth. With batches of 50, 6,000 streams produce 120 batches per law/rho condition. The sequential utility study remains 18 law/rho experiment cells and 108,000 law/rho-cell stream uses. Because the event-stream seed namespace omits rho, each law reuses the same 6,000 deterministic event streams across its three rho values, for 36,000 distinct law/seed event ledgers overall. Within every cell, endpoint-only reuses each paired stream artifact. The cross-rho reuse induces dependence among rho-specific comparisons; the fixed Holm procedure controls the family under arbitrary dependence. The power calculation assigns the planning alternative to one rho per law, so it does not assume independent rho samples; it combines only the three designated gates across distinct law namespaces.

## Bootstrap resampling precision

The 10,000 resamples estimate the bootstrap interval conditional on the `n` observed independent stream pairs; they do not increase `n` or power. Under a smooth normal approximation, the Monte Carlo SE of a 2.5th-percentile endpoint is about 0.0267 bootstrap standard errors. For the worst-case certified-fraction SE this is approximately 0.0012 at `n=500` and 0.00034 at `n=6,000`, compared with sampling half-widths 0.0875 and 0.0253. For time to first certification it is approximately 2.15 events at `n=500` and 0.62 events at `n=6,000`, compared with sampling half-widths 158.0 and 45.58 events. This approximation describes bootstrap Monte Carlo error for smooth distributions; discrete or irregular empirical distributions may have larger endpoint jumps. More resamples cannot remedy too few independent streams.

## Limitations

The planning alternative is a methodological design target because the project contains no application-specific evidence to validate a minimum practically important improvement. The `{-1,+1}` distribution is a worst-case bounded paired-variance model, not a fitted model for future outcomes. The first Holm cutoff is a conservative sufficient condition for adjusted significance; exact realized Holm ranks may be less stringent. Independent law-level samples and one designated qualifying rho per each of exactly three laws give a conservative representation of the claim gate. The analysis plans sensitivity to an effect of 0.07; it does not establish effectiveness, guarantee support at the materiality boundary, or create campaign evidence. No scientific utility campaign or pilot was run.
