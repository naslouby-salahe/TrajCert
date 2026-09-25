# Paired sign-flip validity audit

## Current implementation and tested null

For one utility comparison, each independently generated event stream produces a
paired difference \(D_i = Y_{method,i}-Y_{baseline,i}\), oriented so positive favors
TrajCert. The implementation uses the raw mean \(\bar D\) as its statistic. It draws
20,000 independent Rademacher sign vectors, computes the sign-flipped means, and
returns

\[
 p = \frac{1 + \#\{\bar D_b^* \ge \bar D\}}{20{,}001}.
\]

The intended one-sided null is \(H_0:E[D]\le 0\), against \(E[D]>0\); the boundary
\(E[D]=0\) is least favorable. The signs are Monte Carlo multiplier draws. Methods
are paired on shared event streams, but method labels were not randomized within
streams, so there is no design-based randomization argument.

## Primary methodological source

Jesse Hemerik, Jelle J. Goeman, and Livio Finos (2020), “Robust Testing in Generalized
Linear Models by Sign Flipping Score Contributions,” *Journal of the Royal Statistical
Society: Series B* 82(3), 841–864, [doi:10.1111/rssb.12369](https://doi.org/10.1111/rssb.12369).

Section 2.1 treats independent random variables \(\nu_i\), not only GLM scores. Its
Assumption 1 requires independent contributions, finite variances, a Lindeberg
condition, and convergence of their average variance to a positive limit. Theorem 1
establishes asymptotic level for the basic sign-flipping test when the null implies
\(E[\nu_i]=0\); Corollary 1 extends the upper-tail test to nulls implying
\(E[\nu_i]\le0\). Proposition 1 separately gives finite-sample validity under
independence and sign symmetry \(\nu_i\overset d=-\nu_i\) under the null (with exact
attainable levels under full enumeration and no ties; ties/random Monte Carlo draws can
make the test conservative). The theorem does not require approximate or exact symmetry.

The source includes the observed identity transform plus independent random transforms.
TrajCert’s 20,000 random sign draws and plus-one observed count correspond to 20,001
reference transforms, with a fixed transform count as in the theorem.

## Applicability to TrajCert

For each fixed law/rho/metric condition, the inferential unit is an independently
seeded synthetic stream; the two methods are evaluated on the same stream. Thus the
paired differences are IID under the declared stream-generating model. They are bounded:
certified-update fractions and anytime-risk differences lie in \([-1,1]\); each
time-to-first-certification value lies in \([0,2001]\), so its difference lies in
\([-2001,2001]\). Bounded IID differences satisfy the finite-variance and Lindeberg
conditions. For nondegenerate comparisons the variance limit is positive. If variance
is zero, a nonpositive constant difference cannot cause an upper-tail rejection.

The synthetic-law design does **not** guarantee sign symmetry of the paired differences.
Common random streams create pairing but do not make the method difference distribution
symmetric. Consequently, the current sign-flip p-values are **not claimed to be
finite-sample exact** for the general mean null. They are **asymptotically valid** for
the one-sided mean null under the IID/bounded/nondegenerate conditions above. The
asymptotic theorem justifies the procedure’s limiting behavior; it gives no finite-sample
type-I error bound at the configured \(n=6{,}000\).

The 6,000 count is selected by the separate power design: 80% target power for the
complete three-law gate at the 0.07 planning alternative, with 83.3959% modeled power.
That power calculation does not establish finite-sample sign-flip validity. This
limitation must stay explicit in the roadmap and reviewer-facing wording.

## Holm dependence

The 54 raw p-values form one fixed Holm family. Reusing the same stream IDs across rho
values creates dependence among rho-specific p-values. Holm’s step-down family-wise
error control does not require independence; it does require each input p-value to be
valid under its own null. Under the assumptions above, those inputs are asymptotically
valid, so the fixed family has asymptotic family-wise error control. Dependence is not
the validity problem; finite-sample sign-exchangeability is absent, while individual
p-value validity follows asymptotically from the cited theorem.

## Design and cell-count reconciliation

The planning alternative 0.07 was fixed before campaign execution as a rounded
methodological sensitivity informed by the pre-campaign precision/power analysis. The
0.05 value remains the observed-effect materiality filter. Neither is evidence of
empirical effectiveness, and 0.07 is not an application-specific minimum important
effect.

The Same Endpoint, Different Timing plan has four configured partitions and six
configured rho values (0.01, 0.05, 0.10, 0.20, 0.40, and \(\log 2\)); its paired
semantic cell count is 24. Direct production plan expansion returns 24 family cells
and 1,738 total executable cells. The 20-cell statement in EXP-016 was stale and has
been corrected; no code or scientific configuration change was needed.
