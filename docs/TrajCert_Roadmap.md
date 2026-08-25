# TrajCert — Authoritative Research Roadmap

**Contribution:** **TrajCert — Trajectory-Aware Partial-Identification and Sensitivity-Certification Framework**

**Research object:** **Latent Operational Error Risk** $\theta=P(L=1)$

**Verification setting:** **Delayed, selective/outcome-dependent, and potentially unresolved outcome verification**

**Theoretical principle:** **Path-Information Sensitivity (PIS)** — $I(L;J^*)\le\rho$

**Primary finest trajectory resolution:** **`method.finest_bands` (resolved value: 8 bands, $K=8$)**

**Scientific authority:** **this roadmap**

Source basis:

# 1. Authority, Identity, States, and Execution

TrajCert is a trajectory-aware partial-identification and sensitivity-certification framework for determining whether latent operational error risk can be certified when outcome verification is delayed, selective/outcome-dependent, and potentially unresolved.

This roadmap is the authoritative standalone scientific and execution specification. Typed code, generated plans, manifests, configuration snapshots, and derived artifacts may transcribe it but may not override its scientific, statistical, experimental, numerical, or reproducibility-critical requirements.

The partition-dependent legacy comparator is exactly:

```text
Legacy bandwise odds-ratio sensitivity
```

Scientific states:

```text
CERTIFIED
UNCERTIFIED
MODEL_INCOMPATIBLE
INTRINSICALLY_UNCERTIFIABLE
INSUFFICIENT_EVIDENCE
```

Public experiment execution states:

```text
NOT_STARTED
BLOCKED
READY
RUNNING
COMPLETED
FAILED
INVALID
```

Internal execution states:

```text
PLANNED
RUNNING
COMPLETED
FAILED
INVALID
```

Evidence classes:

```text
VALIDATION
EXPLORATORY
CONFIRMATORY
ABLATION
ROBUSTNESS
GENERALIZATION
FAILURE_BOUNDARY
DIAGNOSTIC
```

The authoritative registry uses `VALIDATION`, `CONFIRMATORY`, `ABLATION`, `ROBUSTNESS`, `GENERALIZATION`, `FAILURE_BOUNDARY`, and `DIAGNOSTIC`. Exploratory evidence cannot be retrospectively promoted to confirmatory evidence.

Execution state and scientific state are distinct. A valid scientific null, unfavorable bound, incompatibility result, intrinsic impossibility result, or theorem falsification is completed scientific evidence rather than a technical execution failure.

A semantic experiment cell has one execution only for each material dependency identity. Re-execution with identical dependencies is an idempotent reuse operation unless `--overwrite` is explicitly supplied.

# 2. Research Problem, Questions, Claims, and Boundaries

## 2.1 Problem and unit of validity

For one stable operational stream, certify the latent action-error risk

$$
\theta=P(L=1),
$$

where $L=1$ means an automatic action is wrong or harmful, correctness is observed only if an outcome-dependent adjudication process resolves the action, and some actions remain unresolved through a terminal horizon. Complete-case error can be optimistic under informative resolution; unresolved-as-harm is assumption-free but can be excessively conservative.

Every certificate is local to one immutable:

$$
(\texttt{client＿id},\texttt{action＿channel＿id},\texttt{epoch＿id}).
$$

The epoch manifest fixes detector/model identity, action policy, adjudication regime, event/logging semantics, terminal horizon, and finest trajectory representation. A material change closes the epoch; pending actions remain assigned to the epoch in which they were issued.

## 2.2 Research questions

1. Does one fixed path-information sensitivity budget retain its meaning under deterministic trajectory coarsening and generate nested sharp risk sets?
2. Is resolved timing information identifiable, and when does finer timing strictly improve the upper risk bound?
3. Does the one-dimensional information profile generate the exact compatible latent-risk set?
4. Can the method distinguish model contradiction, sensitivity-driven non-certification, and intrinsic impossibility?
5. Does projection of a simultaneous observable-law confidence sequence through the conservative sharp-map envelope provide the declared time-uniform upper-risk guarantee?
6. Over a predeclared $\rho$ domain, when is the certificate informative, incompatible, or practically vacuous?
7. If a future eligible action/adjudication ledger exists, does real resolved timing materially improve certification?
8. Does local validity remain independent of foreign-client information?

The confirmatory claim names, exact wording, evidence gates, scopes, and failure states are authoritative in Section 21.

## 2.3 Scope and prohibited extrapolation

The contribution does **not** claim invention of callback/repeated-attempt data, outcome-dependent timing as missing-data information, mutual information, entropy/divergence sensitivity generally, partial identification, sharp bounds generally, falsification/breakdown frontiers generally, data processing, confidence sequences/e-processes, delayed-outcome inference generally, active querying/abstention/selective acting, or federated evidence borrowing.

It does **not** claim finite-sample minimax optimality; universal $\rho$ calibration; universal odds-ratio-to-$\rho$ conversion; continuous-time or unrestricted serial-drift validity; covariate-conditional validity; active-adjudication optimality; detector-training superiority; privacy protection; poisoning/Byzantine robustness; OOD/zero-day superiority; constrained-device deployment feasibility; or current real-trajectory validation.

The theorem assumes trustworthy event IDs, issue/adjudication timestamps, terminal status, and resolved correctness labels. Tampering, malicious adjudicators/clients, poisoning, detector evasion, secure aggregation, and privacy leakage are outside scope; a data-integrity violation yields no certificate. Federation is unnecessary for local validity and foreign-client information does not enter the core inference procedure.

# 3. Formal Observation and Mathematical Contract

For an analysis partition

$$
\Pi=\lbrace H_1\lt \cdots\lt H_K\rbrace,
$$

define

$$
J_\Pi\in\lbrace1,\ldots,K,\infty\rbrace,
$$

where $J_\Pi=k$ means adjudication first completes in resolved band $k$, and $J_\Pi=\infty$ means unresolved through $H_K$.

Observable masses are

$$
a_k=P(J_\Pi=k,L=1),
$$

$$
b_k=P(J_\Pi=k,L=0),
$$

$$
c=P(J_\Pi=\infty).
$$

Define

$$
A=\sum_{k=1}^{K}a_k,
\qquad
G=\sum_{k=1}^{K}b_k,
\qquad
A+G+c=1.
$$

The latent outcome is binary, $L\in\lbrace0,1\rbrace$. The only hidden binary terminal mass is

$$
u=P(J_\Pi=\infty,L=1),
\qquad
0\le u\le c.
$$

Therefore

$$
\theta(u)=A+u.
$$

For each resolved band,

$$
m_k=a_k+b_k
$$

and

$$
r_k=
\begin{cases}
a_k/m_k,&m_k\gt 0,\\
\text{undefined},&m_k=0.
\end{cases}
$$

Empty bands contribute exactly zero to entropy sums.

All information quantities use natural logarithms and are reported in **nats**.

Binary entropy is

$$
h(x)=-x\log x-(1-x)\log(1-x),
$$

with the continuous extension $0\log0=0$.

Define

$$
R=\mathbf1\lbrace J_\Pi\lt \infty\rbrace.
$$

## 3.1 Event-ledger and fixed-horizon maturation

Each action has immutable:

```text
event_id
client_id
action_channel_id
epoch_id
t_issue
terminal_horizon
```

and zero or one valid adjudication record.

An adjudication may be operationally recorded immediately, but **inferential ingestion occurs only when the action reaches terminal age $H_K$**.

At maturity the category is permanently:

```text
(k,1)       resolved harmful/wrong in band k
(k,0)       resolved correct in band k
infinity    unresolved through H_K
```

Faster-resolving actions therefore do not enter the sequential statistical sample earlier than unresolved actions.

Matured actions are ordered by:

```text
(maturity_timestamp, event_id)
```

with `event_id` compared lexicographically for timestamp ties.

The sequential estimator updates exactly once per matured event.

For observable category $j$, the stable-epoch condition is

$$
E[\mathbf1\lbrace Y_n=j\rbrace\mid\mathcal F_{n-1}]=p_j
$$

for one fixed categorical probability vector $p$ throughout the epoch.

IID categorical observations satisfy the assumption. No theorem is claimed under arbitrary serial drift.

All confirmatory synthetic sequential streams are IID from their prespecified full laws.

Integrity failures are:

* duplicate `event_id`;
* maturity before issue;
* adjudication before issue;
* adjudication after the stored terminal horizon while marked finite;
* correctness label attached to terminal-unresolved status;
* finite resolved status without a correctness label;
* category inconsistent with the configured partition.

Integrity failures are data-validity failures, not evidence-count shortfalls. Their execution consequence is defined in Sections 9.7 and 25.

## 3.2 Path-Information Sensitivity

The finest trajectory representation $J^*$ is fixed before corresponding outcomes are inspected.

$$
\boxed{I(L;J^*)\le\rho.}
$$

Every analysis partition is a deterministic coarsening

$$
J_\Pi=g_\Pi(J^*).
$$

The same numerical $\rho$ therefore remains valid after deterministic coarsening.

## 3.3 Observable timing information

$$
\boxed{
\tau_\Pi=(A+G)I(L;J_\Pi\mid R=1).
}
$$

For $A+G\gt 0$,

$$
\tau_\Pi=
(A+G)h\left(\frac{A}{A+G}\right) -
\sum_{k=1}^{K}m_kh(r_k).
$$

## 3.4 Exact information profile

$$
\boxed{
\mathcal S_\Pi(u) =
h(A+u) -
\sum_k m_k h(r_k) -
c,h(u/c).
}
$$

For $0\lt u\lt c$,

$$
\mathcal S_\Pi'(u) =
\log\frac{u(G+c-u)}
{(A+u)(c-u)}
$$

and

$$
\mathcal S_\Pi''(u) =
\frac{A}{u(A+u)}
+
\frac{G}{(c-u)(G+c-u)} \gt 0
$$

under nondegenerate conditions.

## 3.5 Minimum-information completion and compatibility floor

When $A+G\gt 0$,

$$
u^\dagger=\frac{Ac}{A+G},
$$

$$
\theta^\dagger=\frac{A}{A+G},
$$

$$
\boxed{\rho_{\min}=\tau_\Pi.}
$$

## 3.6 Sharp risk set

$$
\mathcal U_\Pi(\rho) =
\lbrace u\in[0,c]:\mathcal S_\Pi(u)\le\rho\rbrace.
$$

The regimes are:

$$
\rho\lt \tau_\Pi
\Rightarrow
\mathcal U_\Pi(\rho)=\varnothing,
$$

$$
\rho=\tau_\Pi
\Rightarrow
\mathcal U_\Pi(\rho)=\lbrace u^\dagger\rbrace,
$$

and for $\rho\gt \tau_\Pi$,

$$
\mathcal U_\Pi(\rho)=[u_L,u_U].
$$

The sharp latent-risk interval is

$$
\boxed{
\Theta_\Pi(\rho) =
[A+u_L,A+u_U].
}
$$

## 3.7 Refinement and exact timing value

If $\Pi_f$ refines $\Pi_c$ under the same terminal horizon,

$$
\mathcal S_{\Pi_c}(u)
\le
\mathcal S_{\Pi_f}(u),
$$

so

$$
\Theta_{\Pi_f}(\rho)
\subseteq
\Theta_{\Pi_c}(\rho).
$$

Moreover,

$$
\mathcal S_{\Pi_f}(u)-\mathcal S_{\Pi_c}(u) =
I(L;J_{\Pi_f}\mid J_{\Pi_c})
=:\Delta\tau.
$$

Under the theorem's compatibility and interior-upper-root conditions,

$$
\Delta\tau\gt 0
\iff
u_U^f(\rho)\lt u_U^c(\rho).
$$

## 3.8 Safety regimes

For action-risk budget $\beta$, define

$$
u_\beta=\beta-A.
$$

Regimes:

1. If $\beta\lt A$, resolved harmful mass already exceeds the budget.
2. If
   $$
   \beta\lt \theta^\dagger=\frac{A}{A+G},
$$
   the state is intrinsically uncertifiable.
3. If
   $$
   \theta^\dagger\le\beta\lt A+c,
$$
   then
   $$
   \boxed{
   \rho^\star=\mathcal S_\Pi(\beta-A).
   }
$$
4. If
   $$
   \beta\ge A+c,
$$
   the action is safe even under unresolved-as-harm.

For deterministic safety-boundary validation, define

$$
\theta_{\max}=A+c.
$$

The five fixed safety-budget cases are:

| Case                                         | Risk budget $\beta$                | Validity rule                                                        |
| -------------------------------------------- | ---------------------------------- | -------------------------------------------------------------------- |
| Below resolved harmful mass                  | $\max(0,A-0.005)$                  | always defined                                                       |
| Between resolved mass and intrinsic boundary | $(A+\theta^\dagger)/2$             | invalid when $A=\theta^\dagger$; record `DEGENERATE_SAFETY_INTERVAL` |
| At intrinsic boundary                        | $\theta^\dagger$                   | always defined when $\theta^\dagger$ exists                          |
| Interior safety frontier                     | $(\theta^\dagger+\theta_{\max})/2$ | always defined when $\theta^\dagger$ exists                          |
| Assumption-free boundary                     | $\theta_{\max}$                    | always defined                                                       |

These are fixed scientific constructions, not independently editable configuration values.

## 3.9 Endpoint special case

For $K=1$,

$$
\tau=0,
$$

and

$$
\mathcal S(u)=I(L;R).
$$

This is the mandatory endpoint-only PIS baseline.

## 3.10 Population solver contract

The production population solver is fixed methodology rather than a configurable algorithm choice.

Sufficient-statistic accumulation is $O(K)$. Entropy terms use a numerically stable `xlogy`-equivalent evaluation with the exact continuous boundary extension. Compatibility is classified before root solving, and exact boundary cases are evaluated before iteration.

For compatible nondegenerate cases, the solver uses bisection and solves the lower and upper branches separately.

For each branch:

1. initialize the branch bracket using $[0,u^\dagger]$ for the lower root and $[u^\dagger,c]$ for the upper root;
2. retain an exact sign-valid bracket for $\mathcal S_\Pi(u)-\rho$;
3. bisect until bracket width is no greater than `numerics.root_atol`;
4. return the bracket midpoint;
5. store the final bracket endpoints, width, returned root, residual, and iteration count.

The iteration cap is

$$
\left\lceil
\log_2\frac{w_0}
{\texttt{numerics.population＿root＿absolute＿tolerance}}
\right\rceil+2,
$$

where $w_0$ is the initial branch width. It is derived, not independently configured.

The population solver validation requirement is:

```text
final root bracket width <= numerics.root_atol
returned-root absolute information residual <= numerics.identity_atol
```

This distinguishes the root-location tolerance from the theorem-identity residual tolerance.

The solver returns explicit degeneracy/scientific states rather than hiding boundary behavior. Scientific quantities are never rounded before comparison, and sensitivity budgets are never clipped to force compatibility.

# 4. Configuration YAML

This section is the single authoritative source for values that are genuinely supplied, selected, or swept as configuration data. It contains numerical parameters, thresholds, tolerances, counts, probabilities, seed-index ranges, booleans, paths, environment identifiers, categorical experiment selections, and experiment-grid values only.

Derived quantities, mathematical formulas, fixed scientific or algorithmic behavior, validation and failure semantics, provenance rules, reporting procedures, semantic-identity rules, experiment-registry definitions, and claim wording are intentionally excluded from YAML. Those requirements are defined in the authoritative roadmap sections where they belong and are computed or enforced by the implementation.

One production scientific/runtime configuration file is sufficient for the current study. `configs/tests.yml` and `configs/smoke.yml` contain runner settings only and do not define independently editable production scientific values.

## `configs/trajcert.yaml`

```yaml
schema_version: 1

method:
  finest_bands: 8
  terminal_horizon: 8

budgets:
  risk: 0.05
  information_nats: 0.05

confidence:
  anytime_delta: 0.05
  level: 0.95
  alpha: 0.05

minimum_evidence:
  matured_events: 200
  resolved_events: 50

laws:
  no_path_dependence:
    theta: 0.05
    q1: 0.10
    q0: 0.10
    lambda1: 0.00
    lambda0: 0.00

  timing_harmful_late:
    theta: 0.05
    q1: 0.10
    q0: 0.10
    lambda1: 0.45
    lambda0: -0.15

  terminal_harmful_unresolved:
    theta: 0.05
    q1: 0.30
    q0: 0.05
    lambda1: 0.00
    lambda0: 0.00

  timing_terminal_harmful_late:
    theta: 0.05
    q1: 0.30
    q0: 0.05
    lambda1: 0.45
    lambda0: -0.15

  timing_terminal_harmful_early:
    theta: 0.05
    q1: 0.05
    q0: 0.30
    lambda1: -0.45
    lambda0: 0.15

  high_unresolvedness:
    theta: 0.05
    q1: 0.70
    q0: 0.40
    lambda1: 0.35
    lambda0: -0.10

  low_prevalence:
    theta: 0.01
    q1: 0.30
    q0: 0.05
    lambda1: 0.45
    lambda0: -0.15

  high_prevalence:
    theta: 0.20
    q1: 0.30
    q0: 0.05
    lambda1: 0.45
    lambda0: -0.15

  intrinsic_impossibility:
    theta: 0.15
    q1: 0.10
    q0: 0.10
    lambda1: 0.00
    lambda0: 0.00

  near_degeneracy:
    theta: 0.01
    q1: 0.90
    q0: 0.01
    lambda1: 0.80
    lambda0: -0.80

  same_endpoint_no_timing:
    theta: 0.05
    q1: 0.20
    q0: 0.10
    lambda1: 0.00
    lambda0: 0.00

  same_endpoint_with_timing:
    theta: 0.05
    q1: 0.20
    q0: 0.10
    lambda1: 0.60
    lambda0: -0.20

grids:
  partitions: [8, 4, 2, 1]
  scaling_bands: [1, 2, 4, 8, 16, 32, 64, 128]

  rho:
    [0, 0.0025, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075,
     0.10, 0.15, 0.20, 0.30, 0.40, 0.50]

  beta: [0.01, 0.025, 0.05, 0.10, 0.20]

numerics:
  root_atol: 1.0e-12
  identity_atol: 1.0e-10
  comparison_guard: 1.0e-12
  oracle_digits: 100
  anytime_root_atol: 1.0e-12
  outer_gap: 1.0e-6
  outer_max_nodes: 2000000
  arbitrary_precision_bits: 128

comparators:
  legacy_gamma: [1, 1.25, 1.5, 2, 4, 8]

  pattern_mixture:
    c: [0, 1, 2, 3]
    coefficient_bounds: [-20, 20]
    ftol: 1.0e-15
    gtol: 1.0e-12
    max_iterations: 10000

sequential:
  coverage:
    streams: 5000
    max_events: 500
    checkpoint_every: 100
    acceptance_upper_limit: 0.06

  utility:
    streams: 500
    max_events: 2000
    checkpoint_every: 50
    rho: [0.05, 0.10, 0.20]

statistics:
  bootstrap_resamples: 10000
  sign_flip_randomizations: 20000

materiality:
  population:
    absolute_tightening: 0.005
    relative_unresolved_gain: 0.20
    qualifying_laws: 3
    compatible_rho_values: 2

  sequential:
    certified_fraction_gain: 0.05
    qualifying_laws: 3

benchmark:
  warmup_repetitions: 5
  measured_repetitions: 30

failure_boundary:
  unresolvedness: [0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9]
  timing_contrast: [0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
  prevalence: [0.001, 0.005, 0.01, 0.025, 0.05, 0.10, 0.20]
  bands: [1, 2, 4, 8, 16, 32, 64]
  information_margin: [0, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05]
  risk_offset: [-0.05, -0.02, -0.005, 0, 0.005, 0.02, 0.05]
  sample_size: [25, 50, 100, 200, 500, 1000, 2000]
```

`PyYAML 6.0.3` is explicitly included because the authoritative configuration is YAML and that release supports CPython 3.13.

`pip-tools 7.6.0` is the prescribed dependency-resolution tool. The dependency file is generated with hashes because `pip-compile --generate-hashes` is specifically intended to produce hash-checking requirements files.

The YAML stores configuration data only. Mathematical constants, derivations, algorithm procedures, validation conditions, deterministic ordering rules, reporting contracts, and claim semantics remain authoritative scientific or execution text outside YAML.

The following configuration-adjacent rules are mandatory:

1. No generic scientific epsilon exists. Entropy, mutual-information, latent-risk, and sensitivity formulas use their exact continuous extensions and declared numerical algorithms rather than an undocumented epsilon.
2. `numerics.comparison_guard` may prevent a false strong classification caused only by binary representation error, but it may never relax certification. `CERTIFIED` still requires the proven upper risk to be no greater than the applicable risk budget.
3. The exact binary maximum-information endpoint is the mathematical constant $\log 2$. It is required where Sections 7.12 and 18.9 specify it and is not stored as an approximate configurable constant.
4. The file order of `laws` is authoritative where deterministic law ordering is required.
5. Experiment ordering is authoritative in Section 17.
6. `grids.beta` is a prespecified descriptive reference grid included in Table 1 and configuration provenance. No current registry experiment sweeps that grid independently; beta values used by executable experiments are defined by their experiment-specific contracts.
7. Descriptive categorical values in YAML are semantic names only where they genuinely select configured laws, partitions, methods, or runtime identifiers.
8. Scientific/statistical grid membership is prespecified. A scientific parameter change creates a different dependency identity for only the artifacts that actually consume it.

## 4.1 Dependency-lock generation and installation

The canonical direct dependency declaration is `pyproject.toml`; `requirements.lock` is generated inside the authoritative Python 3.13.15 container using exactly:

```text
python -m pip install "pip-tools==7.6.0"
python -m piptools compile \
  --generate-hashes \
  --resolver=backtracking \
  --strip-extras \
  --output-file=requirements.lock \
  pyproject.toml
```

Resolution uses the default public Python Package Index unless an explicitly documented organization mirror is required. The resulting `requirements.lock` is stored in the repository and becomes the authoritative transitive dependency artifact.

Authoritative installation is:

```text
python -m pip install --require-hashes -r requirements.lock
```

Scientific execution never re-resolves dependencies when a valid `requirements.lock` exists.

# 5. Synthetic Data Protocol

## 5.1 Synthetic trajectory generator

For $K$ resolved bands, terminal probability $q$, and slope $\lambda$,

$$
w_k(\lambda)=
\frac{
\exp{\lambda(k-(K+1)/2)}
}{
\sum_{j=1}^{K}
\exp{\lambda(j-(K+1)/2)}
}.
$$

For harmful outcomes,

$$
P(J=k\mid L=1) =
(1-q_1)w_k(\lambda_1),
$$

$$
P(J=\infty\mid L=1)=q_1.
$$

For correct outcomes,

$$
P(J=k\mid L=0) =
(1-q_0)w_k(\lambda_0),
$$

$$
P(J=\infty\mid L=0)=q_0.
$$

Finally,

$$
P(L=1)=\theta.
$$

Positive $\lambda$ shifts resolved mass later; negative $\lambda$ shifts it earlier.

The observed law hides $L$ for $J=\infty$.

The synthetic terminal horizon is `method.terminal_horizon`. For any resolved-band count $K$, the synthetic resolved boundaries are equally spaced over that fixed horizon:

$$
H_k=\frac{k}{K}H_K,\qquad k=1,\ldots,K.
$$

Thus changing $K$ in a declared resolution experiment changes trajectory resolution without silently changing the terminal horizon.

Every generated synthetic action is admitted to the ledger; action coverage is fixed at 1.0 and no hidden action subsampling occurs.

## 5.2 Primary law roles

* `No outcome-path dependence`: exact zero-information control;
* `Timing only: harmful outcomes resolve late`: timing dependence without terminal-selection difference;
* `Terminal only: harmful outcomes remain unresolved`: terminal selection with zero resolved-timing information;
* `Timing and terminal: harmful outcomes resolve late`: principal informative-resolution case;
* `Timing and terminal: harmful outcomes resolve early`: opposite direction;
* `High terminal unresolvedness`: strong censoring;
* `Low error prevalence`: rare harmful outcome;
* `High error prevalence`: high harmful prevalence;
* `Intrinsic safety impossibility`: intrinsic-risk boundary;
* `Near numerical degeneracy`: extreme small cells/timing;
* `Same endpoint without timing information`: same-endpoint zero-timing control;
* `Same endpoint with timing information`: same $(A,G,c)$, positive timing-information counterpart.

## 5.3 Derived minimum-information laws

For observed masses $(a_k,b_k,c)$, define:

```text
Minimum-information completion of <law name>
```

by setting

$$
u=u^\dagger=\frac{Ac}{A+G}
$$

while preserving every observable mass.

The full-law path information is exactly $\tau$.

These laws are used only in declared compatibility-boundary stress tests.

## 5.4 K-scaling laws

For each $K$ in `grids.scaling_bands`, regenerate the same conditional-law functional form with unchanged:

```text
theta
q1
q0
lambda1
lambda0
```

and only change $K$.

## 5.5 Stochastic stream generation

For each event:

1. sample
   $$
   L\sim\mathrm{Bernoulli}(\theta);
$$
2. conditional on $L$, sample $J$;
3. reveal `(J,L)` when finite;
4. reveal only `infinity` when terminal unresolved.

The underlying stream is IID.

## 5.6 Synthetic ledger

For zero-based stream index `s` and event index `t`:

```text
client_id         = "synthetic-client"
action_channel_id = "automatic-action"
epoch_id          = slug(<law name>) + "::static-epoch"

event_id =
  slug(<law name>)
  + "::S"
  + zero_pad(s,6)
  + "::E"
  + zero_pad(t,6)

issue_age_unit    = t
maturity_age_unit = t + H_K
```

For resolved band $k$:

```text
adjudication_completion_age = t + H_k
correctness_label = sampled L
```

For terminal unresolved:

```text
adjudication_completion_age = null
correctness_label = null
```

Inferential insertion occurs only at maturity.

## 5.7 Preprocessing

Synthetic preprocessing performs only:

1. schema validation;
2. probability-normalization verification;
3. duplicate-event rejection;
4. finite-number/range verification;
5. deterministic trajectory construction;
6. deterministic finest-to-coarse mapping;
7. canonical sorting;
8. checksumming;
9. law-manifest generation.

It performs no normalization, imputation, feature scaling, train/validation/test split, duplicate collapsing, label remapping, or learned preprocessing.

A probability sum must equal one within `numerics.comparison_guard`.

Any `NaN`, infinity, duplicate ID, impossible category, invalid label, or probability outside `[0,1]` invalidates preprocessing.

## 5.8 Deterministic count apportionment

Whenever a deterministic finite-sample construction converts target category probabilities into integer counts, use Hamilton apportionment.

The canonical category order is exactly:

```text
(1,1),(1,0),(2,1),(2,0),...,infinity
```

For total count $n$ and target category probabilities $p_j$:

1. compute exact quotas $q_j=np_j$;
2. assign $f_j=\lfloor q_j\rfloor$;
3. let
   $$
   r=n-\sum_j f_j;
$$
4. assign one additional count to the $r$ categories having the largest fractional remainders $q_j-f_j$;
5. break equal-remainder ties by canonical category order.

### Balanced-prefix construction

For deterministic sequential constructions, let $C_{j,t}$ be the count of category $j$ after $t$ events, with $C_{j,0}=0$.

For each $t=1,\ldots,n$, append the category

$$
j_t=
\arg\max_j\left\lbrace
t,p_j-C_{j,t-1}
\right\rbrace.
$$

Any exact tie is broken by canonical category order.

Then set

$$
C_{j_t,t}=C_{j_t,t-1}+1
$$

and leave all other category counts unchanged.

The resulting sequence is the authoritative `balanced-prefix construction`. It is deterministic for a fixed probability vector and category ordering.

When a construction first specifies exact terminal counts rather than probabilities, define target probabilities as those exact counts divided by $n$, then apply the same balanced-prefix rule. Its final prefix must reproduce the supplied exact counts; otherwise preprocessing is invalid.

# 6. Dataset Authority and Real-Trajectory Decision

For any external dataset, record both:

```text
documented_expected_value
observed_raw_dataset_value
```

Official dataset documentation and the corresponding primary publication define the expected release semantics. The raw files actually present at execution time are authoritative for observed counts, filenames, row counts, entity counts, schemas, and physically available fields.

Inventory records:

```text
expected source/release
official documentation reference
primary publication reference when available
raw checksum
file count
row count
entity count
raw schema
labels
temporal fields
client/entity identifiers
exclusions
discrepancy status
field-mapping status
eligibility status
```

No dataset-specific count, schema, feature list, timestamp field, client identity, or row total is assumed solely from documentation.

If the raw dataset differs from documented expectations:

1. preserve both expected and observed values;
2. determine whether an observed field is semantically equivalent to a required documented field;
3. if equivalent, record the deterministic mapping in the dataset manifest and use the observed raw field;
4. adapt file discovery, column names, physical types, file counts, and row counts to the actual release without changing scientific event semantics;
5. do not fabricate missing values required for action identity, adjudication timing, correctness, terminal status, or stream identity;
6. if a required scientific semantic cannot be established from the raw source, mark the dataset `INELIGIBLE`;
7. never silently substitute an unrelated timestamp, derived pseudo-client, reconstructed verdict, or inferred terminal status.

Current real-trajectory planning status is exactly:

```text
NOT_IN_CURRENT_CONFIRMATORY_PLAN
```

Current confirmatory execution uses the synthetic benchmark defined under `synthetic_data`. `Real-Trajectory Validation` is a zero-cell planned nonapplicability in the authoritative registry, no current real-trajectory execution exists, and the Real-Trajectory Value claim remains `NOT_TESTED`.

The synthetic generator is authoritative, so generated and expected probability tables must agree within deterministic numerical tolerance.

A later separate real study is eligible only if the same action unit has:

* immutable event identifier;
* issue timestamp;
* automatic-action channel;
* adjudication completion timestamp;
* binary correctness verdict;
* operationally justified terminal horizon;
* explicit unresolved-at-horizon versus missing-logging distinction;
* stable detector/action-policy/adjudication/logging regime;
* provenance proving adjudication time is not merely an event/capture timestamp.

If any required element must be fabricated or inferred from an unrelated timestamp, the source is ineligible.

A future real study is a separate study and does not alter the current synthetic registry.

# 7. Baseline and Comparator Contracts

## 7.1 Complete-case arrival-only

$$
\hat\theta_{\text{complete}} =
\frac{A}{A+G}
$$

when $A+G\gt 0$.

Terminal unresolved mass is ignored. This is an optimistic descriptive reference, not a PIS certificate.

## 7.2 Unresolved-as-harm worst case

$$
\theta_U^{\text{worst}}=A+c.
$$

This is assumption-free.

## 7.3 Endpoint-only path information

All finite bands are merged into $K=1$ using the same numerical $\rho$. Because

$$
\tau=0,
$$

this isolates the value of resolved timing.

## 7.4 Legacy bandwise odds-ratio sensitivity

Define:

$$
A_k^+=\sum_{j\gt k}a_j,
\qquad
B_k^+=\sum_{j\gt k}b_j.
$$

For candidate hidden mass $u$,

$$
h_{1k}(u) =
\frac{a_k}{a_k+A_k^++u},
$$

$$
h_{0k}(u) =
\frac{b_k}{b_k+B_k^++c-u}.
$$

Response-hazard odds ratio:

$$
\psi_k(u) =
\frac{h_{1k}/(1-h_{1k})}
{h_{0k}/(1-h_{0k})} =
\frac{a_k(B_k^++c-u)}
{b_k(A_k^++u)}.
$$

When both outcome-specific response hazards are structurally zero:

```text
UNINFORMATIVE_BAND
```

and the band is omitted from the all-band constraint.

Other structural-zero cases use exact extended-real limits.

Feasibility requires

$$
\Gamma^{-1}\le\psi_k(u)\le\Gamma
$$

for every informative band.

No universal mapping between $\Gamma$ and $\rho$ is reported.

The feasible interval is solved analytically from the linear-rational inequalities when denominators are positive; boundary cases use exact limits. No numerical optimizer default is used.

## 7.4.1 Deterministic legacy partition-incoherence construction

For each configured pair

$$
(\Gamma,q)
\in
\texttt{legacy＿partition＿incoherence.gamma＿values}
\times
\texttt{legacy＿partition＿incoherence.q＿values},
$$

construct a two-band full law with

$$
P(L=1)=P(L=0)=0.5.
$$

Define the odds-shift operation

$$
T(q,\gamma) =
\frac{\gamma q}{1-q+\gamma q}.
$$

For $L=0$, set conditional response hazards

$$
h_{01}=q,
\qquad
h_{02}=q.
$$

For $L=1$, set

$$
h_{11}=T(q,\Gamma),
\qquad
h_{12}=T(q,\Gamma^{-1}).
$$

The full-law masses are:

$$
P(J=1,L=\ell)=P(L=\ell)h_{\ell1},
$$

$$
P(J=2,L=\ell) =
P(L=\ell)(1-h_{\ell1})h_{\ell2},
$$

$$
P(J=\infty,L=\ell) =
P(L=\ell)(1-h_{\ell1})(1-h_{\ell2}).
$$

Under the fine two-band representation, the true hidden terminal harmful mass satisfies exactly:

$$
\psi_1=\Gamma,
\qquad
\psi_2=\Gamma^{-1},
$$

so the fine legacy model is compatible at the true completion.

The same observable law is then coarsened to the endpoint-only partition and evaluated under the identical numerical $\Gamma$.

The counterexample passes when:

```text
true hidden mass is feasible under the two-band legacy model
two-band and endpoint-only legacy feasible risk sets are not identical
set-endpoint difference exceeds numerics.identity_atol
```

The exact direction and magnitude of the set difference are reported; only non-invariance is required.

## 7.5 ALHO common-slope callback

For candidate $u$, define

$$
g_k(u)=\log\psi_k(u)
$$

for every informative band with finite positive $\psi_k$, and

$$
Q(u)=
\sum_k
(g_k(u)-\bar g(u))^2.
$$

The model is compatible when an accepted root satisfies:

$$
Q(u)\le\texttt{numerics.callback＿q＿acceptance}.
$$

`numerics.callback_q_acceptance` is the common-slope acceptance tolerance.

Algorithm:

1. use `numerics.oracle_digits` decimal digits;
2. evaluate exactly `numerics.callback_grid_points` equally spaced $u$ points including `0` and `c`;
3. every point no greater than available immediate neighbors defines a local minimization bracket;
4. endpoints are brackets when locally minimal;
5. apply deterministic golden-section minimization;
6. stop when bracket width is no greater than `numerics.callback_golden_section_width`;
7. accept if $Q(u)\le\texttt{numerics.callback＿q＿acceptance}$;
8. sort accepted roots;
9. deduplicate roots whose absolute difference is no greater than `numerics.callback_root_dedup_tolerance`, retaining the smaller root;
10. if no accepted root, return `MODEL_INCOMPATIBLE`;
11. risk set is the convex hull of $A+u$ over accepted roots.

If fewer than two informative bands remain:

```text
NOT_APPLICABLE
```

## 7.6 Stable-resistance callback

For $K\ge2$, impose

$$
\log\psi_1(u)=\log\psi_2(u).
$$

Define residual

$$
E(u)=\left|\log\psi_1(u)-\log\psi_2(u)\right|.
$$

Use the same high-precision grid/local-minimization procedure as Section 7.5, replacing $Q$ by $E$.

Accept a root when

$$
E(u)\le\texttt{numerics.callback＿equality＿tolerance}.
$$

Sort and deduplicate accepted roots using `numerics.callback_root_dedup_tolerance`.

Attempts after the second add no identifying equality restriction.

If $K\lt 2$:

```text
NOT_APPLICABLE
```

## 7.7 Binary repeated-attempt pattern mixture

For nonempty finite band $k$,

$$
r_k=\frac{a_k}{m_k}.
$$

Fit

$$
\mathrm{logit}(r_k) =
\zeta_0+\zeta_1k
$$

using weighted Bernoulli cross-entropy with weight $m_k$.

The optimizer is fixed to `L-BFGS-B`.

Coefficient bounds, convergence tolerances, iteration limit, and initial slope are the numerical values under `comparators.pattern_mixture`.

Initialization:

$$
\zeta_1=0,
$$

$$
\zeta_0=
\mathrm{logit}
\left[
\mathrm{clip}
\left(
\frac{A}{A+G},
\texttt{numerics.pattern＿mixture＿initial＿probability＿clip},
1-\texttt{numerics.pattern＿mixture＿initial＿probability＿clip}
\right)
\right].
$$

Successful fit requires:

* optimizer convergence;
* gradient infinity norm no greater than `numerics.pattern_mixture_gradient_infinity_limit`;
* finite objective;
* finite gradient;
* neither coefficient within `numerics.pattern_mixture_bound_touch_tolerance` of a configured bound.

Otherwise:

```text
BASELINE_NUMERICALLY_UNSTABLE
```

For sensitivity $C$,

$$
r_\infty(C) =
\mathrm{expit}{\zeta_0+\zeta_1(K+C)},
$$

$$
\theta(C)=A+c,r_\infty(C).
$$

If fewer than two nonempty finite bands exist:

```text
NOT_APPLICABLE
```

## 7.8 Generic full-law information oracle

The independent oracle constructs the full $2\times(K+1)$ table directly.

For candidate $u$,

$$
I(L;J) =
\sum_{\ell,j}
p_{\ell j}
\log
\frac{p_{\ell j}}
{p_{\ell+}p_{+j}}.
$$

The oracle may use the mathematical fact that the feasible set is an interval, but it may not import or call the production information-profile, derivative, minimizer, or production root-solving implementation.

Oracle precision:

```text
decimal digits = numerics.oracle_digits
boundary bracket width <= numerics.oracle_boundary_bracket_width
```

The oracle uses `mpmath` at exactly `numerics.oracle_digits` decimal digits.

Its independent algorithm is:

1. construct the full table directly from $(a_k,b_k,c,u)$;
2. evaluate mutual information using the table formula above with exact zero-cell limits;
3. locate the global minimum over $[0,c]$ using an independently implemented golden-section search on the direct table objective;
4. stop minimum search when its $u$-bracket width is no greater than `numerics.oracle_boundary_bracket_width`;
5. let $I_{\min}$ be the minimum direct-table value at the midpoint;
6. define the oracle equality tolerance as
   $$
   \epsilon_{\text{oracle}}=10^{-\lfloor \texttt{numerics.oracle＿decimal＿digits}/2\rfloor};
$$
7. if $\rho\lt I_{\min}-\epsilon_{\text{oracle}}$, return `MODEL_INCOMPATIBLE`;
8. if $|\rho-I_{\min}|\le\epsilon_{\text{oracle}}$, return the singleton minimum bracket midpoint as both endpoints;
9. otherwise solve the left and right direct-table equations $I(L;J)=\rho$ by independent bisection on the two sides of the minimum;
10. terminate each boundary bisection when its bracket width is no greater than `numerics.oracle_boundary_bracket_width`;
11. return boundary bracket midpoints and retain the complete boundary brackets for validation.

This procedure detects the $\rho=\tau$ tangent/singleton case explicitly and therefore does not depend on arbitrary subdivision discovering a zero-width feasible component.

Production endpoints must agree with oracle endpoints within `numerics.identity_atol`.

## 7.9 Time-uniform observable-law projection

This is the generic sequential reference computation and the bound-producing core used by TrajCert. Its construction is Section 9.

The two configured names have distinct reporting roles:

```text
TrajCert
```

means:

```text
time-uniform observable-law projection
+ evidence gates
+ compatibility classification
+ intrinsic-impossibility classification
+ certification state assignment
```

whereas:

```text
Time-uniform observable-law projection
```

means the raw valid projected upper bound and its coverage diagnostics without TrajCert operational-state interpretation.

The numerical $U_n(\rho)$ calculation is shared by dependency identity and is never redundantly recomputed merely because both method labels are reported.

No sequential-method novelty is claimed.

## 7.10 Repeated-static-monitoring negative control

At every matured $n$, for category count $s$ and $\hat p=s/n$, use a Wilson score interval with per-category two-sided confidence level

$$
1-\frac{\delta}{d}.
$$

Let

$$
z=
\Phi^{-1}
\left(
1-\frac{\delta}{2d}
\right).
$$

Then

$$
center=
\frac{
\hat p+z^2/(2n)
}{
1+z^2/n
},
$$

$$
half=
\frac{z}{1+z^2/n}
\sqrt{
\frac{\hat p(1-\hat p)}{n}
+\frac{z^2}{4n^2}
}.
$$

Clip only interval endpoints to `[0,1]`.

At each individual $n$, apply Bonferroni across categories and project through the same outer routine. No across-time correction is applied.

This comparator is deliberately invalid under continuous monitoring and can never support deployment.

## 7.11 Ignorable-delay anytime reference

Applicable only when truth satisfies

$$
L\perp J.
$$

Among matured events, maintain the Jeffreys beta-binomial mixture confidence sequence defined in Section 9.2 on the binary harmful/correct outcome using only resolved labels.

At matured time $n$:

* $m_n$ is the resolved count;
* update the Bernoulli CS only when a resolved label appears;
* retain the previous CS on unresolved updates;
* use its upper endpoint as the risk upper under the ignorable assumption.

The same evidence-count gates apply.

In outcome-dependent cells:

```text
ASSUMPTION_VIOLATED
```

and the method is excluded from valid-method ranking.

## 7.12 Ablations

Exactly:

```text
Endpoint-only path information
Same Endpoint, Different Timing
rho = log(2)
```

The last uses the exact binary maximum-information budget $\log 2$ and removes the effective PIS restriction for binary $L$.

# 8. Metrics and Aggregation

| Metric                                          | Definition                                    | Direction                                |
| ----------------------------------------------- | --------------------------------------------- | ---------------------------------------- |
| `Latent error risk`                             | $\theta=A+u$                                  | lower safer                              |
| `Observed timing information`                   | $\tau$                                        | descriptive                              |
| `Conditional timing gain`                       | $\Delta\tau$                                  | larger indicates more timing information |
| `Minimum compatible sensitivity budget`         | $\tau$                                        | descriptive                              |
| `Minimum-information risk`                      | $\theta^\dagger$                              | lower safer                              |
| `Risk lower bound`                              | $A+u_L$                                       | descriptive                              |
| `Risk upper bound`                              | $A+u_U$                                       | lower better                             |
| `Identified-set width`                          | $u_U-u_L$                                     | lower tighter                            |
| `Safety-frontier sensitivity budget`            | $\rho^\star$                                  | larger more robust                       |
| `Anytime upper risk`                            | proven $U_n(\rho)$                            | lower better                             |
| `Anytime compatibility floor`                   | certified lower envelope of $\tau$            | descriptive                              |
| `Ever-violation indicator`                      | $\mathbf1\lbrace\exists n:\theta\gt U_n\rbrace$              | lower                                    |
| `Bound gain versus endpoint-only`               | endpoint upper minus fine upper               | higher better                            |
| `Absolute tightening versus unresolved-as-harm` | $(A+c)-\theta_U$                              | higher better                            |
| `Relative unresolved-mass gain`                 | $((A+c)-\theta_U)/c$                          | higher better                            |
| `Time to first certification`                   | first eligible certified $n$                  | lower better                             |
| `Certified update fraction`                     | certified eligible updates / eligible updates | higher better                            |
| `State frequency`                               | state count / eligible updates                | descriptive                              |
| `Compatibility-budget consumption`              | $\tau/\rho$                                   | descriptive                              |
| `Oracle absolute error`                         | production-oracle absolute difference         | lower                                    |
| `Runtime seconds`                               | monotonic elapsed target-computation time     | lower                                    |
| `Peak RSS MiB`                                  | peak resident memory                          | lower                                    |

For `Time to first certification`, a never-certified stream receives

$$
N_{\max}+1
$$

only in numeric comparison statistics.

Raw `first_certified_n` remains `null` with:

```text
never_certified=true
```

`eligible updates` are updates at which the evidence-count gates have passed and there is no data-validity or technical failure. Updates classified `MODEL_INCOMPATIBLE`, `INTRINSICALLY_UNCERTIFIABLE`, `CERTIFIED`, or `UNCERTIFIED` are eligible. `INSUFFICIENT_EVIDENCE` updates are not eligible for the certified-update-fraction denominator.

## 8.1 Undefined behavior

If $A+G=0$:

```text
tau = null
u_dagger = null
theta_dagger = null
```

and finite-sample substantive state cannot be assigned.

If $c=0$:

$$
u=0
$$

and the risk set is $\lbrace A\rbrace$.

If $m_k=0$:

```text
r_k = null
entropy contribution = 0
```

If $\rho=0$:

```text
Compatibility-budget consumption = null
```

For `Relative unresolved-mass gain`, if $c=0$:

```text
relative_unresolved_gain = null
```

Undefined scientific quantities are stored as `null`. `NaN`, positive infinity, and negative infinity are forbidden in claim-bearing numeric fields; any exceptional state is represented by an explicit status field instead.

No detector AUC, F1, TPR, FPR, calibration, privacy, communication, or energy metric is claim-bearing.

# 9. Statistical and Sequential-Inference Protocol

## 9.1 Independent units

| Analysis                     | Independent unit                                   |
| ---------------------------- | -------------------------------------------------- |
| theorem identities           | deterministic case; no stochastic unit             |
| production/oracle validation | exact law × partition × sensitivity cell           |
| anytime coverage             | one independent event stream                       |
| paired sequential utility    | one independent event stream shared across methods |
| runtime                      | one isolated measured invocation                   |
| future real analysis         | one stable stream/epoch                            |

Monitoring times within one stream and optimizer evaluations are never independent replicates.

## 9.2 Categorical confidence sequence

For $K$ finite bands, let

$$
\delta=\texttt{confidence.anytime＿delta}
$$

and

$$
d=2K+1.
$$

Categories:

$$
(1,1),(1,0),\ldots,(K,1),(K,0),\infty.
$$

At matured $n$, category $j$ has count $S_{j,n}$.

For $p\in(0,1)$,

$$
\log M_{j,n}(p) =
\mathrm{betaln}
\left(
S_{j,n}+\frac12,
n-S_{j,n}+\frac12
\right) -
\mathrm{betaln}
\left(
\frac12,\frac12
\right) -
S_{j,n}\log p -
(n-S_{j,n})\log(1-p).
$$

Per-category allocation:

$$
\alpha_j=\frac{\delta}{d}.
$$

Raw confidence set:

$$
C^{raw}_{j,n} =
\left\lbrace
p:
\log M_{j,n}(p)
\lt 
\log\frac{d}{\delta}
\right\rbrace.
$$

The stored numerical interval is the closure of this set; inclusion of an equality boundary is conservative.

At $p=0$ and $p=1$, exact limiting likelihood values are used; `log(0)` is never numerically evaluated.

### Endpoint inversion

For each non-boundary endpoint, maintain a sign-valid bisection bracket around the root of

$$
\log M_{j,n}(p)-\log(d/\delta)=0.
$$

Stop only when bracket width is no greater than `numerics.anytime_root_atol`.

To preserve outward coverage:

```text
stored lower CS endpoint = lower coordinate of the lower-root bracket
stored upper CS endpoint = upper coordinate of the upper-root bracket
```

If the exact confidence set touches `0` or `1`, use that exact boundary.

Never return an inward midpoint as a stored CS endpoint.

Running interval:

$$
C_{j,n} =
\bigcap_{t\le n}
C^{raw}_{j,t}.
$$

Numerically:

```text
running lower = max(previous running lower, current raw lower)
running upper = min(previous running upper, current raw upper)
```

Simultaneous region:

$$
\mathcal C_n^{rect} =
\left\lbrace
p:
\ell_{j,n}\le p_j\le u_{j,n},
\quad
p_j\ge0,
\quad
\sum_jp_j=1
\right\rbrace.
$$

Simplex feasibility for a rectangular interval vector is tested exactly by:

$$
\sum_j\ell_{j,n}\le1\le\sum_j u_{j,n}.
$$

The running intersection and simplex intersection are mandatory parts of the procedure.

The monitor updates at every matured event and favorable early stopping is forbidden.

An unexpectedly empty rectangle/simplex intersection after valid CS construction is an implementation/numerical failure:

```text
TECHNICAL_FAIL
```

and the owning execution cell becomes `FAILED`.

## 9.3 Conservative summary envelope

Compute

$$
A_L=\sum_k\ell_{a_k},
\qquad
A_U=\sum_ku_{a_k},
$$

$$
G_L=\sum_k\ell_{b_k},
\qquad
G_U=\sum_ku_{b_k}.
$$

Terminal mass additionally satisfies

$$
c=1-A-G
$$

and the terminal-category interval.

Define

$$
q(a,b)=
\begin{cases}
-a\log\frac{a}{a+b}
-b\log\frac{b}{a+b},
&a+b\gt 0,\\
0,&a=b=0.
\end{cases}
$$

Then

$$
C_L=\sum_kq(\ell_{a_k},\ell_{b_k}),
$$

$$
C_U=\sum_kq(u_{a_k},u_{b_k}).
$$

Use

$$
\mathcal E_n=
\left\lbrace
(A,G,C):
A\in[A_L,A_U],
G\in[G_L,G_U],
c=1-A-G\in[c_L,c_U],
C\in[C_L,C_U]
\right\rbrace.
$$

The finite-sample procedure claims validity, not shortest possible width.

## 9.4 Certified outer optimization

Define

$$
S(A,G,C,u) =
h(A+u) -
C -
c,h(u/c),
\qquad
c=1-A-G.
$$

Then

$$
U_n(\rho) =
\sup
\left\lbrace
A+u:
(A,G,C)\in\mathcal E_n,
0\le u\le c,
S(A,G,C,u)\le\rho
\right\rbrace.
$$

Because $S$ is decreasing in $C$, optimization sets

$$
C=C_U.
$$

Deterministic interval branch-and-bound:

1. use Arb interval/ball arithmetic through `python-flint`;
2. use exactly `numerics.arbitrary_precision_bits` bits for the authoritative computation;
3. any operation that remains indeterminate at that precision invokes the conservative fallback rather than silently increasing precision;
4. initial coordinates are:

```text
A in [A_L,A_U]
G in [G_L,G_U]
u in [0,1]
```

5. intersect with
   $$
   A\ge0,\quad G\ge0,\quad A+G\le1,
$$
   $$
   c\in[c_L,c_U],
   \quad
   0\le u\le c;
$$
6. if an interval for $c$ crosses exactly zero, split at `c=0` before terminal entropy evaluation;
7. use exact continuous entropy extensions on boundary boxes;
8. prune when the interval lower bound of $S$ exceeds $\rho$;
9. objective upper bound is
   $$
   \min(1,A_{hi}+u_{hi});
$$
10. generate feasible incumbents from box midpoints;
11. for midpoint $(A,G)$, compute the maximal feasible $u$ with $C=C_U$ by deterministic upper-branch bisection using the same mathematical profile $S(A,G,C_U,u)$;
12. the scalar incumbent bisection stops at `numerics.root_atol`;
13. an incumbent is accepted only when direct Arb evaluation gives an upper bound on $S$ no greater than $\rho$;
14. normalized coordinate width is physical box width divided by that coordinate's width in the initial box;
15. if an initial coordinate width is zero, its normalized width is zero;
16. split the coordinate with longest normalized width;
17. normalized-width ties within `numerics.outer_split_tie_tolerance` use:

```text
A, then G, then u
```

18. let $U_{\text{queue}}$ be the largest objective upper bound among surviving boxes and $L_{\text{feasible}}$ the largest verified feasible incumbent;
19. stop when
    $$
    U_{\text{queue}}-L_{\text{feasible}}
    \le
    \texttt{numerics.outer＿certified＿gap};
$$
20. stop at `numerics.outer_max_nodes` if not already converged.

On node cap, arithmetic failure, or unresolved interval ambiguity:

* return the current proven queue upper;
* if no finite proven upper exists, return `1.0`;
* never return the feasible incumbent as the certified upper.

Each update records:

```text
initial envelope
precision_bits
visited_nodes
surviving_boxes
feasible_incumbent
proven_upper
final_gap
termination_reason
```

## 9.5 Finite-sample compatibility

For $A+G\gt 0$,

$$
\tau(A,G,C) =
(A+G)
h\left(\frac{A}{A+G}\right)-C.
$$

Compute

$$
\underline\rho_n^{comp} =
\inf_{(A,G,C)\in\mathcal E_n}\tau(A,G,C).
$$

Because $\tau$ decreases in $C$, the infimum uses $C=C_U$.

The certified lower bound is computed by deterministic Arb branch-and-bound over $(A,G)$:

1. initial box is $[A_L,A_U]\times[G_L,G_U]$;
2. enforce $A\ge0$, $G\ge0$, $A+G\le1$, and $1-A-G\in[c_L,c_U]$;
3. evaluate an Arb enclosure of $\tau(A,G,C_U)$ on every box;
4. maintain:

   * `global_lower` = minimum lower endpoint over all surviving boxes;
   * `feasible_upper` = smallest verified point value found;
5. split by longest normalized $A/G$ width with tie order `A`, then `G`;
6. stop when
   $$
   \texttt{feasible＿upper}-\texttt{global＿lower}
   \le
   \texttt{numerics.outer＿certified＿gap};
$$
7. use the same node cap and exact Arb precision as Section 9.4;
8. on node cap or ambiguity, return the current `global_lower`.

The returned value is always a **proven lower bound**, even when the optimization did not converge to the requested gap.

`MODEL_INCOMPATIBLE` requires

$$
\underline\rho_n^{comp} \gt 
\rho_{\text{deploy}}
+
\texttt{numerics.scientific＿comparison＿guard}.
$$

## 9.6 Finite-sample intrinsic impossibility

Define

$$
\theta^\dagger(A,G) =
\frac{A}{A+G}.
$$

The compatible subset consists of $(A,G)$ for which there exists $u\in[0,c]$ with

$$
S(A,G,C_U,u)\le\rho.
$$

Compute a certified lower bound

$$
\underline\theta_n^\dagger.
$$

Use deterministic Arb branch-and-bound over $(A,G,u)$:

1. initial domains are the same $A,G,u$ domains as Section 9.4;
2. enforce the envelope and simplex constraints;
3. prune a box when the interval lower bound of $S(A,G,C_U,u)$ exceeds $\rho$;
4. for each surviving box with $A+G$ bounded strictly above zero, compute an interval enclosure of
   $$
   \frac{A}{A+G};
$$
5. if any surviving compatible-plausible box includes $A+G=0$, set

   ```text
   zero_resolved_mass_plausible = true
   ```

   and the strong intrinsic state is withheld;
6. otherwise, the minimum lower endpoint across surviving boxes is the proven lower bound;
7. split by longest normalized width with tie order:

   ```text
   A, then G, then u
   ```
8. use `numerics.outer_gap`, the Section 9.4 precision, and `numerics.outer_max_nodes`;
9. on node cap or ambiguity, return the current conservative lower bound.

`INTRINSICALLY_UNCERTIFIABLE` requires:

* evidence gates passed;
* `zero_resolved_mass_plausible=false`;
* $$
  \underline\theta_n^\dagger \gt 
  \beta+\texttt{numerics.scientific＿comparison＿guard}.
$$

## 9.7 Evidence gate, failure precedence, and scientific-state precedence

Execution/data validity is evaluated before scientific evidence sufficiency.

The authoritative precedence is:

### A. Data/manifest validity

Any of the following makes the affected cell `INVALID` and produces no scientific state:

```text
ledger integrity failure
epoch-manifest integrity failure
invalid probability/simplex input
duplicate semantic identity
schema violation originating in authoritative input
```

### B. Technical/numerical validity

Any of the following makes the affected cell `FAILED` with internal result `TECHNICAL_FAIL` and produces no scientific state:

```text
unexpected empty simultaneous region
arithmetic exception
corrupt artifact
unresolved interval-arithmetic failure with no conservative fallback
serialization/checksum failure
implementation invariant violation
```

### C. Evidence-count gate

For otherwise valid execution, require:

```text
n_matured >= minimum_evidence.matured_events
n_resolved >= minimum_evidence.resolved_events
simultaneous confidence region nonempty
```

If either count requirement fails:

```text
INSUFFICIENT_EVIDENCE
```

There is no separate minimum harmful-event-count gate.

### D. Substantive scientific state

After all preceding checks:

1. certified incompatibility lower bound above $\rho$ → `MODEL_INCOMPATIBLE`;
2. otherwise certified intrinsic-risk lower bound above $\beta$ → `INTRINSICALLY_UNCERTIFIABLE`;
3. otherwise if
   $$
   U_n(\rho)\le\beta,
$$
   → `CERTIFIED`;
4. otherwise → `UNCERTIFIED`.

## 9.8 Clopper-Pearson validation

For $m$ independent streams and $v$ ever-violation streams, let

$$
q_{CP} =
\texttt{sequential＿inference.coverage＿validation.clopper＿pearson＿confidence}.
$$

The exact one-sided confidence limit is

$$
U_{CP} =
\begin{cases}
1,&v=m,\\
\mathrm{BetaQuantile}(q_{CP};v+1,m-v),&v\lt m.
\end{cases}
$$

Use the inverse regularized incomplete beta function with exactly those arguments.

A primary stress cell passes empirical validation only if

$$
U_{CP}
\le
\texttt{sequential＿inference.coverage＿validation.acceptance＿upper＿limit}.
$$

The theoretical target remains

$$
\delta=\texttt{confidence.anytime＿delta}.
$$

The acceptance upper limit is only the Monte Carlo implementation-validation tolerance.

Every configured primary TrajCert case in `sequential_stress_cases` must pass.

## 9.9 Paired practical inference

For favorable-direction paired difference $D_s$:

* upper-risk or time-to-certificate:
  $$
  D_s=Y_{\text{baseline},s}-Y_{\text{method},s};
$$
* certified fraction:
  $$
  D_s=Y_{\text{method},s}-Y_{\text{baseline},s}.
$$

Positive always favors TrajCert.

Report:

$$
\bar D,
$$

sample SD using denominator $n-1$,

$$
d_z=\frac{\bar D}{s_D}
$$

when $s_D\gt 0$, a paired percentile-bootstrap CI, and a one-sided favorable-direction sign-flip p-value.

### Paired percentile bootstrap

For one comparison:

1. use namespace:

   ```text
   Bootstrap|<semantic comparison key>
   ```
2. use seed index `0`;
3. instantiate the required `PCG64` generator;
4. for each of exactly `statistics.bootstrap_resamples` resamples, sample $n$ pair indices independently with replacement from `0..n-1`;
5. compute the resampled mean paired difference;
6. sort all bootstrap means;
7. for confidence level $1-\alpha$, use quantiles $\alpha/2$ and $1-\alpha/2$;
8. quantiles use linear interpolation at index $(B-1)q$.

### Sign-flip test

Define

$$
T_{\text{obs}}=\bar D.
$$

For randomization $b$:

1. independently draw signs $\sigma_{s,b}\in\lbrace-1,+1\rbrace$ with probability $1/2$;
2. define
   $$
   T_b=
   \frac1n\sum_s\sigma_{s,b}D_s.
$$

Use namespace:

```text
Permutation|<semantic comparison key>
```

with seed index `0`.

With

$$
B=\texttt{statistics.sign＿flip.randomizations},
$$

the one-sided p-value is

$$
p=
\frac{
1+\left\lvert\lbrace T_b\ge T_{\text{obs}}\rbrace\right\rvert
}{
1+B
}.
$$

### Effect-size edge cases

If all differences are zero:

```text
standardized_effect = 0
standardized_effect_status = FINITE
```

If SD=0 but mean is nonzero:

```text
standardized_effect = null
standardized_effect_status = POSITIVE_INFINITY
```

or

```text
standardized_effect_status = NEGATIVE_INFINITY
```

according to the sign of the mean.

### Holm adjustment

The `Trajectory operational gain` multiplicity family is the Cartesian product of:

```text
6 utility laws
× 3 sequential rho values
× 3 practical metrics
= 54 tests
```

Order the 54 raw p-values ascending.

Raw-p ties are broken by canonical `semantic_comparison_name`, then `metric_name`.

For ordered p-values $p_{(1)},\ldots,p_{(m)}$, compute

$$
\tilde p_{(i)} =
\min\left[
1,
\max_{1\le j\le i}
{(m-j+1)p_{(j)}}
\right].
$$

Map adjusted p-values back to their original semantic records.

Adjusted p-values are compared with `confidence.alpha`.

## 9.10 Failed stochastic executions

* no failed-seed deletion;
* no seed substitution;
* no complete-case analysis restricted to successful streams;
* technical interruption reuses the same semantic cell and original seeds;
* scientific nulls remain completed observations;
* planned invalid combinations remain in the plan with reason but are excluded from executable-cell totals.

## 9.11 Randomness and seed derivation

All stochastic seeds are derived deterministically from a zero-based integer index and an explicit semantic namespace:

```text
seed =
  big_endian_uint64(
    SHA256("TrajCert|" + namespace + "|" + decimal(index))[0:8]
  ) mod 2^63
```

The fixed namespace roles are:

```text
Synthetic law
Event stream
Monte Carlo
Oracle
Bootstrap
Permutation
Runtime
```

The semantic-descriptor separator is `|`.

The exact current namespace construction is:

```text
Event stream|law=<exact law name>|K=<integer K>
Bootstrap|<semantic comparison key>
Permutation|<semantic comparison key>
```

`Synthetic law`, `Monte Carlo`, `Oracle`, and `Runtime` remain reserved namespace roles and are not consumed by a current stochastic producer unless that producer actually uses randomness.

Event-stream namespace does not include experiment name, coverage/utility role, requested prefix length, rho, beta, or method. Therefore compatible consumers reuse the same semantic stream and shorter consumers use a validated prefix.

Bootstrap and permutation use seed index `0` for each unique semantic comparison namespace.

Event streams use the configured stream seed index directly.

Compared methods requiring pairing share the same event-stream artifact rather than merely deriving numerically equal seeds.

NumPy stochastic generation uses exactly:

```text
numpy.random.Generator(numpy.random.PCG64(seed))
```

Module-global random-number generators are forbidden.

# 10. Reference Implementation Architecture

Required project structure:

```text
trajcert/
│
├── README.md
├── pyproject.toml
├── requirements.lock
├── Dockerfile
├── noxfile.py
├── Makefile
├── .gitignore
│
├── configs/
│   ├── trajcert.yaml
│   ├── tests.yml
│   └── smoke.yml
│
├── data/
│   └── raw -> /external/datasets
│
├── outputs/
│   ├── preprocessing/
│   │   ├── inventories/
│   │   ├── validation/
│   │   ├── prepared/
│   │   └── metadata/
│   │
│   ├── artifacts/
│   │   ├── fitted/
│   │   ├── baselines/
│   │   └── derived/
│   │       ├── plans/
│   │       ├── streams/
│   │       ├── population/
│   │       └── sequential/
│   │
│   ├── experiments/
│   │   └── <descriptive-experiment-name>/
│   │       ├── artifacts/
│   │       │   ├── fitted/
│   │       │   └── derived/
│   │       ├── evaluations/
│   │       │   ├── records/
│   │       │   ├── comparisons/
│   │       │   └── aggregates/
│   │       ├── metrics/
│   │       │   ├── per_seed/
│   │       │   ├── per_condition/
│   │       │   └── aggregate/
│   │       ├── statistics/
│   │       │   ├── tests/
│   │       │   ├── confidence_intervals/
│   │       │   ├── effects/
│   │       │   └── multiplicity/
│   │       ├── checkpoints/
│   │       │   └── execution/
│   │       ├── diagnostics/
│   │       │   ├── scientific/
│   │       │   ├── numerical/
│   │       │   └── runtime/
│   │       ├── logs/
│   │       │   ├── execution/
│   │       │   └── failures/
│   │       └── provenance/
│   │           ├── configuration/
│   │           ├── data/
│   │           ├── seeds/
│   │           ├── code/
│   │           ├── environment/
│   │           └── dependencies/
│   │
│   └── cache/
│       ├── preprocessing/
│       ├── evaluation/
│       └── analysis/
│
├── results/
│   ├── experiments/
│   │   └── <descriptive-experiment-name>/
│   │       ├── figures/
│   │       │   ├── main/
│   │       │   └── supplementary/
│   │       ├── tables/
│   │       │   ├── main/
│   │       │   └── supplementary/
│   │       ├── metrics/
│   │       │   ├── primary/
│   │       │   ├── secondary/
│   │       │   └── summary/
│   │       └── statistics/
│   │           ├── tests/
│   │           ├── confidence_intervals/
│   │           ├── effects/
│   │           └── multiplicity/
│   │
│   └── project_summary/
│       ├── figures/
│       │   ├── main/
│       │   └── supplementary/
│       ├── tables/
│       │   ├── main/
│       │   └── supplementary/
│       ├── metrics/
│       │   ├── primary/
│       │   └── summary/
│       ├── statistics/
│       │   ├── comparisons/
│       │   ├── confidence_intervals/
│       │   ├── effects/
│       │   └── multiplicity/
│       ├── claims/
│       └── reproducibility/
│           ├── configuration/
│           ├── datasets/
│           ├── seeds/
│           ├── software/
│           └── execution/
│
├── docs/
│   └── Roadmap.md
│
├── src/
│   └── trajcert/
│       ├── __init__.py
│       │
│       ├── configuration/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── loading.py
│       │   ├── validation.py
│       │   └── protocol.py
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── enums.py
│       │   ├── identity.py
│       │   ├── operational.py
│       │   ├── manifests.py
│       │   └── records/
│       │       ├── __init__.py
│       │       ├── artifacts.py
│       │       ├── execution.py
│       │       ├── results.py
│       │       └── claims.py
│       │
│       ├── data/
│       │   ├── __init__.py
│       │   ├── inventory.py
│       │   ├── integrity.py
│       │   ├── partitions.py
│       │   ├── apportionment.py
│       │   └── synthetic/
│       │       ├── __init__.py
│       │       ├── laws.py
│       │       ├── generator.py
│       │       ├── ledger.py
│       │       └── preprocessing.py
│       │
│       ├── math/
│       │   ├── __init__.py
│       │   ├── entropy.py
│       │   ├── information_profile.py
│       │   ├── risk_set.py
│       │   ├── solver.py
│       │   ├── refinement.py
│       │   └── safety.py
│       │
│       ├── inference/
│       │   ├── __init__.py
│       │   ├── confidence_sequence.py
│       │   ├── envelope.py
│       │   ├── projection.py
│       │   ├── compatibility.py
│       │   └── states.py
│       │
│       ├── baselines/
│       │   ├── __init__.py
│       │   ├── references.py
│       │   ├── legacy_odds.py
│       │   ├── callbacks.py
│       │   ├── pattern_mixture.py
│       │   ├── information_oracle.py
│       │   └── sequential_references.py
│       │
│       ├── experiments/
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   ├── planning.py
│       │   ├── execution.py
│       │   ├── lifecycle.py
│       │   ├── recovery.py
│       │   └── definitions/
│       │       ├── __init__.py
│       │       ├── scientific_inventory.py
│       │       ├── formal_mathematics.py
│       │       ├── solver_validation.py
│       │       ├── comparator_reduction.py
│       │       ├── partition_timing.py
│       │       ├── compatibility_sharpness_safety.py
│       │       ├── anytime_validation.py
│       │       ├── utility_analysis.py
│       │       ├── failure_boundaries.py
│       │       ├── computational_scaling.py
│       │       └── statistical_synthesis.py
│       │
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── theorem_validation.py
│       │   ├── oracle_validation.py
│       │   ├── projection_oracle.py
│       │   ├── coverage_validation.py
│       │   └── benchmarking.py
│       │
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── metrics.py
│       │   ├── statistics.py
│       │   ├── materiality.py
│       │   ├── claims.py
│       │   ├── evidence.py
│       │   └── synthesis.py
│       │
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── workspace.py
│       │   ├── storage.py
│       │   ├── artifacts.py
│       │   ├── fingerprints.py
│       │   ├── components.py
│       │   ├── provenance.py
│       │   ├── environment.py
│       │   ├── evidence_manifest.py
│       │   └── diagnostics.py
│       │
│       ├── reporting/
│       │   ├── __init__.py
│       │   ├── tables.py
│       │   ├── figures.py
│       │   └── export.py
│       │
│       └── cli/
│           ├── __init__.py
│           ├── main.py
│           └── commands/
│               ├── __init__.py
│               ├── doctor.py
│               ├── preprocess.py
│               ├── plan.py
│               ├── smoke.py
│               ├── run.py
│               ├── status.py
│               └── report.py
│
└── tests/
    ├── conftest.py
    │
    ├── architecture/
    │   ├── test_dependency_boundaries.py
    │   │   — Enforces allowed dependency directions between architectural layers and prevents architectural responsibility violations.
    │   │
    │   ├── test_public_type_boundaries.py
    │   │   — Ensures public, domain, and application APIs use explicit meaningful types rather than loosely typed interfaces or inappropriate raw primitives.
    │   │
    │   ├── test_no_any_dict_object.py
    │   │   — Rejects inappropriate use of Any, object, and anonymous dict-based domain/configuration/artifact payloads, except narrowly justified external-library boundaries.
    │   │
    │   ├── test_no_primitive_leaks.py
    │   │   — Detects inappropriate str/int/float/bool/list/dict primitives crossing domain or architectural boundaries, including primitive public inputs and outputs where meaningful domain types should be used.
    │   │
    │   ├── test_no_hardcoded_values.py
    │   │   — Detects hardcoded scientific, experimental, statistical, dataset, seed, threshold, algorithm, protocol, and other governed values outside their authoritative owner.
    │   │
    │   ├── test_configuration_ownership.py
    │   │   — Ensures configuration values have one authoritative owner and are not repeated or copied into constants, implementation code, CLI defaults, tests, or parallel configuration structures.
    │   │
    │   ├── test_no_duplicate_constants.py
    │   │   — Detects duplicate constants and equivalent independently maintained values across the repository.
    │   │
    │   ├── test_dead_code.py
    │   │   — Detects dead, unused, unreachable, obsolete, and superseded production modules, classes, functions, methods, constants, and other symbols.
    │   │
    │   ├── test_enum_integrity.py
    │   │   — Detects unused enums and ensures authoritative enums are actually used rather than being bypassed by equivalent free-form strings or duplicate identities.
    │   │
    │   ├── test_no_test_only_production_code.py
    │   │   — Detects production code that exists or is referenced only for tests and has no legitimate production use.
    │   │
    │   ├── test_no_redirects_shims_reexports.py
    │   │   — Rejects obsolete redirect modules, compatibility shims, legacy aliases, transitional wrappers, and unnecessary re-export-only modules.
    │   │
    │   ├── test_naming_policy.py
    │   │   — Enforces descriptive names for modules, classes, functions, methods, variables, and parameters; rejects vague, generic, strange, misleading, or unjustifiably short names and abbreviations.
    │   │
    │   ├── test_canonical_vocabulary.py
    │   │   — Enforces canonical project, scientific, algorithm, dataset, policy, experiment, artifact, and architectural terminology and rejects stale aliases, obsolete terminology, opaque names, and artificial version naming.
    │   │
    │   ├── test_no_comments_or_docstrings.py
    │   │   — Rejects Python source comments and module/class/function/method docstrings.
    │   │
    │   ├── test_no_todos_or_temporary_code.py
    │   │   — Rejects TODO, FIXME, HACK, XXX, commented-out implementations, temporary markers, unfinished code residue, and similar development leftovers.
    │   │
    │   ├── test_static_typing.py
    │   │   — Runs repository-wide strict Pyright across production and tests so Pyright/Pylance-visible typing violations fail the test suite.
    │   │
    │   ├── test_code_quality.py
    │   │   — Enforces Ruff formatting and linting so unformatted or lint-invalid Python code cannot remain in the repository.
    │   │
    │   └── test_dependency_hygiene.py
    │       — Enforces dependency hygiene and detects unused, missing, or incorrectly declared dependencies.
    │
    ├── unit/
    │   ├── configuration/
    │   │   ├── test_loading_validation.py
    │   │   └── test_protocol_snapshot.py
    │   ├── domain/
    │   │   ├── test_identity.py
    │   │   ├── test_operational_records.py
    │   │   └── test_manifests.py
    │   ├── data/
    │   │   ├── test_partitions.py
    │   │   ├── test_apportionment.py
    │   │   ├── test_integrity.py
    │   │   └── synthetic/
    │   │       ├── test_laws.py
    │   │       ├── test_generator.py
    │   │       ├── test_ledger.py
    │   │       └── test_preprocessing.py
    │   ├── math/
    │   │   ├── test_entropy.py
    │   │   ├── test_information_profile.py
    │   │   ├── test_risk_set_solver.py
    │   │   ├── test_refinement.py
    │   │   └── test_safety.py
    │   ├── inference/
    │   │   ├── test_confidence_sequence.py
    │   │   ├── test_envelope.py
    │   │   ├── test_projection.py
    │   │   ├── test_compatibility.py
    │   │   └── test_states.py
    │   ├── baselines/
    │   │   ├── test_reference_bounds.py
    │   │   ├── test_legacy_odds.py
    │   │   ├── test_callbacks.py
    │   │   ├── test_pattern_mixture.py
    │   │   ├── test_information_oracle.py
    │   │   └── test_sequential_references.py
    │   ├── experiments/
    │   │   ├── test_registry_planning.py
    │   │   ├── test_execution_lifecycle.py
    │   │   ├── test_recovery.py
    │   │   └── test_experiment_definitions.py
    │   ├── evaluation/
    │   │   ├── test_theorem_validation.py
    │   │   ├── test_oracle_validation.py
    │   │   ├── test_projection_oracle.py
    │   │   ├── test_coverage_validation.py
    │   │   └── test_benchmarking.py
    │   ├── analysis/
    │   │   ├── test_metrics.py
    │   │   ├── test_statistics.py
    │   │   ├── test_materiality.py
    │   │   ├── test_claims.py
    │   │   ├── test_evidence.py
    │   │   └── test_synthesis.py
    │   ├── infrastructure/
    │   │   ├── test_workspace.py
    │   │   ├── test_artifacts_storage.py
    │   │   ├── test_fingerprints.py
    │   │   ├── test_component_digests.py
    │   │   ├── test_provenance.py
    │   │   ├── test_environment.py
    │   │   └── test_evidence_manifest.py
    │   ├── reporting/
    │   │   ├── test_tables.py
    │   │   ├── test_figures.py
    │   │   └── test_export.py
    │   └── cli/
    │       └── test_commands.py
    │
    ├── scientific/
    │   ├── test_data_invariants.py
    │   ├── test_population_identities.py
    │   ├── test_refinement_and_timing.py
    │   ├── test_sharpness_against_independent_oracle.py
    │   ├── test_safety_and_impossibility.py
    │   ├── test_anytime_validity_contract.py
    │   ├── test_experiment_contracts.py
    │   └── test_claim_boundaries.py
    │
    ├── integration/
    │   ├── data/
    │   │   └── test_synthetic_preprocessing_pipeline.py
    │   ├── population/
    │   │   ├── test_population_solver_pipeline.py
    │   │   └── test_oracle_comparator_pipeline.py
    │   ├── sequential/
    │   │   ├── test_stream_confidence_pipeline.py
    │   │   └── test_projection_state_pipeline.py
    │   ├── execution/
    │   │   ├── test_inventory_to_population.py
    │   │   ├── test_reuse_and_selective_invalidation.py
    │   │   ├── test_checkpoint_recovery.py
    │   │   ├── test_atomic_completion.py
    │   │   └── test_evidence_completion.py
    │   └── reporting/
    │       ├── test_outputs_to_results_export.py
    │       └── test_results_evidence_filter.py
    │
    ├── e2e/
    │   ├── test_preprocess_smoke_plan.py
    │   ├── test_run_status_report.py
    │   ├── test_reuse_overwrite_recovery.py
    │   └── test_full_execution_and_report.py
    │
    └── smoke/
        └── test_smoke.py
```

Responsibilities:

* `configs/trajcert.yaml`: sole production YAML containing the roadmap-defined configurable scientific and runtime values.
* `configs/tests.yml` and `configs/smoke.yml`: test-runner and smoke-runner settings only.
* `configuration`: typed transcription and validation of `configs/trajcert.yaml`, including the generated protocol/configuration snapshot.
* `domain`: immutable operational identities, enums, schemas, manifests, artifact types, dependency records, execution records, result records, and claim records.
* `math`: pure population mathematics without filesystem side effects.
* `inference`: confidence sequences, summary envelope, certified projection, compatibility/intrinsic calculations, and state assignment.
* `data`: synthetic laws, partitions, preprocessing, integrity validation, event-stream generation, deterministic apportionment, and deterministic coarsening.
* `baselines`: comparator and reference-method implementations only.
* `experiments`: registry expansion, semantic-cell lifecycle, dependency resolution, selective invalidation, recovery, idempotency, completion, and experiment-definition contracts.
* `evaluation`: theorem/oracle validation, finite-sample coverage validation, independent projection checks, and isolated benchmarking.
* `analysis`: metrics, prespecified statistics, materiality, claim evaluation, verified evidence views, and cross-experiment synthesis.
* `infrastructure`: fixed workspace/path resolution, dependency/component digests, artifact validation, atomic writes/promotions, provenance/environment capture, evidence-manifest construction, and execution diagnostics.
* `reporting`: deterministic rendering and export of already verified evidence; it performs no scientific recomputation.
* `cli`: public `trajcert` command dispatch and command implementations defined in Section 16.

The generic full-law information oracle must remain structurally independent of the production information-profile/population solver.

# 11. Execution Workspace Contract

The generated computational workspace is rooted at `artifacts.execution_workspace_root`.

The layout is:

```text
outputs/
├── preprocessing/
│   ├── inventories/
│   ├── validation/
│   ├── prepared/
│   └── metadata/
├── artifacts/
│   ├── fitted/
│   ├── baselines/
│   └── derived/
│       ├── plans/
│       ├── streams/
│       ├── population/
│       └── sequential/
├── experiments/
│   └── <descriptive-experiment-name>/
│       ├── artifacts/
│       │   ├── fitted/
│       │   └── derived/
│       ├── evaluations/
│       │   ├── records/
│       │   ├── comparisons/
│       │   └── aggregates/
│       ├── metrics/
│       │   ├── per_seed/
│       │   ├── per_condition/
│       │   └── aggregate/
│       ├── statistics/
│       │   ├── tests/
│       │   ├── confidence_intervals/
│       │   ├── effects/
│       │   └── multiplicity/
│       ├── checkpoints/
│       │   └── execution/
│       ├── diagnostics/
│       │   ├── scientific/
│       │   ├── numerical/
│       │   └── runtime/
│       ├── logs/
│       │   ├── execution/
│       │   └── failures/
│       └── provenance/
│           ├── configuration/
│           ├── data/
│           ├── seeds/
│           ├── code/
│           ├── environment/
│           └── dependencies/
└── cache/
    ├── preprocessing/
    ├── evaluation/
    └── analysis/
```

`outputs/preprocessing/` contains authoritative deterministic preparation products.

Project-wide reusable artifacts have exactly one canonical producer and active path under `outputs/artifacts/`.

Experiment-owned products live only under:

```text
outputs/experiments/<descriptive-experiment-name>/
```

Within an experiment-owned leaf directory, active semantic-cell paths use descriptive semantic coordinates, for example:

```text
outputs/experiments/population-sensitivity-utility/evaluations/records/
  law=timing-and-terminal-harmful-outcomes-resolve-late/
  partition=8-band-partition/
  method=trajcert/
  rho=0.05/
```

No execution-phase directory exists.

## 11.1 Canonical semantic serialization

All canonical JSON used for digests follows RFC 8785 JSON Canonicalization Scheme rules: deterministic property sorting, no insignificant whitespace, canonical primitive serialization, and UTF-8 output.

The implementation contains one internal canonicalization implementation and regression vectors derived from RFC 8785.

For digest-bearing JSON:

* duplicate keys are forbidden;
* `NaN` and infinities are forbidden;
* all scientific runtime floating-point values are finite IEEE-754 binary64 values;
* exact symbolic scientific constants that are not configuration literals are represented by semantic string tokens, e.g.:

  ```text
  "log(2)"
  ```

  in identity metadata while their evaluated numeric value is stored separately;
* arrays preserve their scientific order;
* object keys are canonicalized according to RFC 8785.

## 11.2 Filesystem-safe semantic rendering

Current semantic names consist of ASCII text.

For descriptive names:

1. lowercase;
2. replace each maximal run not matching `[a-z0-9]+` by one hyphen;
3. remove leading/trailing hyphens.

For numeric coordinates, use the exact canonical JSON number token produced for the binary64 value.

The exact symbolic endpoint $\log2$ is rendered:

```text
rho=log2
```

Inapplicable dimensions are omitted.

Hashes are never semantic path substitutes.

Incomplete writes use a temporary sibling path and are atomically promoted only after payload checksum, schema, invariant, and dependency validation pass.

Recoverable checkpoints never constitute completion evidence.

`outputs/cache/` is regenerable and never authoritative.

# 12. Manuscript Evidence Contract

The compact manuscript-facing workspace is rooted at `artifacts.results_root`.

`report` exports only completed, schema-valid, dependency-valid, provenance-valid evidence.

Experiment-specific evidence is published under:

```text
results/experiments/<descriptive-experiment-name>/
```

`Statistical Synthesis` owns cross-experiment claim and synthesis artifacts under:

```text
results/project_summary/
```

Every figure and table is rendered only from authoritative machine-readable evidence under `outputs/`.

`results/` is never consumed as scientific computational input.

Table and figure ordering is deterministic.

Favorable axis-limit selection, seed-subset selection, hiding incompatible points, and undeclared smoothing or fitted trends used as claim evidence are forbidden.

Rendering-only changes may regenerate SVG/PNG/TeX/CSV without invalidating scientific source data, metrics, statistical results, or experiment cells.

`results/` may not contain:

```text
cache files
debug logs
failed cells
invalid cells
stale cells
temporary artifacts
partial artifacts
drafts
checkpoints
authoritative computational provenance payloads
```

Only compact verified reproducibility summaries are exported.

# 13. Machine-Readable Schemas

Schemas compose a shared envelope rather than duplicating provenance fields.

## 13.1 Canonical physical types

Authoritative Parquet files use Apache Arrow-compatible physical types:

```text
string                    UTF-8 string
boolean                   Arrow bool
integer counts/indices    int64
nonnegative large IDs     uint64 when required
scientific real values    float64
timestamps                timestamp[us, UTC]
list of strings           list<string>
structured free JSON      canonical RFC-8785 JSON stored as string
SHA-256 digest            lowercase 64-character hexadecimal string
```

No claim-bearing float column may contain `NaN` or infinity.

Undefined scientific values are Arrow nulls.

String-enum columns reject values outside their declared enum.

Every authoritative schema has:

```text
schema_name
schema_version
```

with current `schema_version=1`.

## 13.2 Common envelope

Applicable scientific-cell and reusable artifacts inherit:

```text
artifact_key
artifact_type
artifact_owner
producer_component
semantic_cell_key
semantic_coordinates
experiment_name
classification
execution_group
scientific_specification_digest
scientific_dependency_digest
provenance_fingerprint
dependency_fingerprint
implementation_component_digest
environment_dependency_digest
plan_digest
cell_plan_digest
status
method_name
baseline_name
dataset_name
dataset_checksum
synthetic_law_name
partition_name
rho
beta
delta
environment_lock_digest
code_commit
seed_set_keys
parent_artifact_keys
parent_artifact_digests
input_paths
canonical_active_path
schema_name
schema_version
```

Required common fields are non-null:

```text
artifact_key
artifact_type
artifact_owner
producer_component
scientific_specification_digest
scientific_dependency_digest
provenance_fingerprint
dependency_fingerprint
implementation_component_digest
environment_dependency_digest
status
schema_name
schema_version
```

Cell-specific fields are non-null whenever applicable to the semantic cell.

`artifact_key` is a deterministic descriptive key for artifact type plus applicable semantic/dependency coordinates.

`semantic_cell_key` is a deterministic RFC-8785 serialization of the semantic coordinate object prefixed by the descriptive experiment name; it is never a hash.

## 13.3 Plan and manifests

`run` materializes the plan files when required:

```text
outputs/artifacts/derived/plans/experiment_plan.json
outputs/artifacts/derived/plans/experiment_plan.parquet
```

`plan` computes the same rows without mutating active scientific artifacts.

Plan-specific fields:

```text
executable
invalid_reason
gamma
sensitivity_parameter_json
seed_namespace
seed_index_start
seed_index_stop_exclusive
expected_stream_count
expected_artifact_schema
expected_output_path
upstream_artifact_types
producer_component
dependency_coordinates
```

Canonical plan ordering:

```text
execution_group
experiment_name
synthetic_law_name
partition_name
method_name
rho
beta
seed_index_start
semantic_cell_key
```

Nulls sort before non-null values; strings sort lexicographically by Unicode code point; numeric values sort numerically.

`plan_digest` is SHA-256 of the RFC-8785 canonical ordered-row array.

`cell_plan_digest` is SHA-256 of the canonical JSON object for one row.

Dataset manifest:

```text
dataset_name
dataset_kind
generator_name
generator_code_digest
source_version
source_checksum
license_or_permission
official_documentation_reference
primary_publication_reference
event_semantics
label_semantics
time_semantics
terminal_horizon
finest_partition_name
number_of_categories
documented_expected_structure
observed_raw_structure
field_mapping_json
population_parameters
known_full_law
known_theta
known_observable_probabilities
known_terminal_harmful_mass
known_information
preprocessing_digest
eligibility_status
ineligibility_reason
```

Current execution:

```text
dataset_kind = SYNTHETIC
known_full_law = true
```

Partition manifest:

```text
partition_name
finest_partition_name
terminal_horizon
K
boundaries
coarsening_map_from_finest
parent_partition_name
is_endpoint_only
is_precommitted
checksum
```

Seed manifest:

```text
seed_set_key
namespace
index_start
index_stop_exclusive
derivation_algorithm
seeds_sha256
seed_count
```

The actual seed list is stored as unsigned decimal strings.

Reusable artifact manifest:

```text
artifact_key
artifact_type
artifact_owner
producer_component
dependency_fingerprint
implementation_component_digest
environment_dependency_digest
scientific_dependency_digest
semantic_coordinates
parent_artifact_keys
parent_artifact_digests
scientific_content_digest
payload_paths
payload_sha256_map
schema_name
schema_version
status
created_timestamp
validated_timestamp
declared_downstream_consumers
```

## 13.4 Cell, execution, dependency, and provenance records

Active semantic-cell manifest adds:

```text
resolved_scientific_parameters
expected_artifacts
required_artifact_keys
produced_artifact_keys
execution_start_timestamp
execution_end_timestamp
host_runtime_fingerprint
checkpoint_recovery_history
```

No run ID, UUID, attempt number, timestamp, or hash-derived scientific identifier exists.

Execution-state record:

```text
state
semantic_cell_key
state_sequence_number
last_transition_timestamp
reason_code
reason_text
failed_seed_indices
completed_seed_indices
completed_batch_indices
checkpoint_recovery_eligible
stale_artifact_keys
blocking_artifact_keys
```

Aggregate experiment record:

```text
experiment_name
overall_state
expected_semantic_cells
completed_semantic_cells
failed_semantic_cells
invalid_semantic_cells
stale_semantic_cells
blocking_dependencies
active_provenance_digest
last_execution_outcome
results_export_state
```

The provenance fingerprint is SHA-256 of canonical JSON containing complete recorded lineage:

```text
scientific_specification_digest
code_commit
dirty_tree_flag
environment_lock_digest
container_image_digest
dataset/preprocessing checksums
partition checksum
seed-manifest checksums
plan_digest
```

The dependency fingerprint is SHA-256 of canonical JSON containing only material dependencies:

```text
artifact_type
applicable semantic coordinates
scientific_dependency_digest
implementation_component_digest
environment_dependency_digest
seed-manifest digest when stochastic
parent artifact identities
parent canonical scientific-content digests
other producer-specific immutable inputs
```

Repository commit, dirty-tree flag, timestamps, unrelated plan rows, unrelated source files, tests, documentation, logging code, and report-only code are excluded from the dependency fingerprint unless they are material inputs to the producer.

## 13.5 Scientific result records

Population metrics:

```text
law_name
A
G
c
C_timing_entropy
tau
delta_tau
u_dagger
theta_dagger
u_lower
u_upper
risk_lower
risk_upper
identified_width
rho_star
population_state
oracle_value
oracle_abs_error
numeric_status
```

Sequential updates:

```text
law_name
stream_seed_index
n_matured
n_resolved
n_unresolved
confidence_region_digest
rho_comp_lower
theta_dagger_lower
risk_upper_anytime
operational_state
evidence_gate_pass
optimizer_proven_upper
optimizer_feasible_lower
optimizer_gap
optimizer_node_count
optimizer_termination
true_theta
ever_violation_to_date
```

No undefined `rho_star_anytime` field is part of the current sequential schema.

Stream metrics:

```text
law_name
stream_seed_index
ever_violation
first_certified_n
never_certified
certified_update_fraction
model_incompatible_update_fraction
intrinsically_uncertifiable_update_fraction
uncertified_update_fraction
insufficient_evidence_update_fraction
final_risk_upper
technical_failure
```

Paired comparisons:

```text
claim_family
semantic_comparison_name
law_name
rho
partition_name
method_name
baseline_name
metric_name
stream_seed_index
method_value
baseline_value
paired_difference_favorable_direction
```

Statistical tests:

```text
claim_name
claim_family
comparison_name
metric_name
experimental_unit
n_pairs
alternative
test_name
permutation_count
raw_p_value
holm_family_size
holm_adjusted_p_value
decision_alpha
reject_null
```

Effect sizes:

```text
claim_name
comparison_name
metric_name
n_pairs
mean_paired_difference
sd_paired_difference
standardized_paired_effect
standardized_effect_status
```

Confidence intervals:

```text
claim_name
comparison_name
metric_name
estimand
method
confidence_level
resample_count
lower
estimate
upper
```

Theorem validation:

```text
theorem_name
case_name
law_name
partition_name
quantity
expected_relation
expected_value
observed_value
absolute_error
tolerance
pass
failure_reason
details_json
```

## 13.6 Failure, claim, and completion records

Failure:

```text
failure_record_key
semantic_cell_key
dependency_fingerprint
provenance_fingerprint
failure_class
execution_group
reason_code
message
exception_type
seed_index
input_artifact_keys
input_artifact_digests
last_valid_checkpoint
retry_allowed
downstream_blocking
```

Scientific nulls do not enter failure records.

Claim registry:

```text
claim_name
exact_claim
research_question
hypotheses_or_theorems
supporting_experiments
primary_metric
secondary_metrics
statistical_comparison
effect_size_rule
minimum_support_condition
failure_condition
valid_scope
forbidden_extrapolation
supporting_tables
supporting_figures
final_state
final_state_reason
evidence_artifact_digests
```

A semantic cell is complete only when the atomically written `artifacts.completion_marker_file` validates:

```text
semantic_cell_key
cell_plan_digest
scientific_specification_digest
scientific_dependency_digest
provenance_fingerprint
dependency_fingerprint
manifest_digest
required_artifact_keys
produced_artifact_keys
expected_artifact_count
artifact_sha256_map
completed_seed_count
expected_seed_count
metrics_complete
statistics_complete
schema_validation_pass
invariant_validation_pass
dependency_validation_pass
provenance_record_complete
exit_status
```

It is written last.

For a cell with no cell-level statistical artifact, `statistics_complete=true` means statistical output is not required at cell scope.

Directory, checkpoint, log, partial payload, or stale completion-marker existence alone never constitutes completion.

# 14. Semantic Identity, Dependency Reuse, Invalidation, and Recovery

Scientific identity is the fixed semantic coordinate tuple:

```text
experiment_name
dataset_id_or_synthetic_law_name
partition_name
comparison_pair_name
method_name
baseline_name
rho
beta
delta
Gamma
pattern_mixture_C
failure_boundary_axis_and_level
K
seed_index_or_deterministic_seed_block
other_explicit_sensitivity_or_ablation_coordinates
```

Inapplicable coordinates are omitted or explicit `null` according to schema.

UUIDs, timestamps, attempt numbers, random identifiers, hashes, and incremental run IDs are excluded from scientific identity.

Each semantic cell has exactly one canonical active location.

## 14.1 Execution dependency chain

```text
inputs
  -> preprocessing
  -> training
  -> scoring
  -> calibration/thresholding
  -> evaluation
  -> analysis
  -> reporting
```

TrajCert applicability:

| Pipeline step            | TrajCert meaning                                                                                                           | Reusable authoritative artifacts                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| inputs                   | configuration, synthetic-law parameters, external-source inventory if ever eligible, partition definitions, seed manifests | configuration snapshot, dataset/law manifests, partition manifests, seed manifests                |
| preprocessing            | synthetic law construction/validation, finest-to-coarse mappings, deterministic hand/count construction                    | prepared laws, observable/full-law tables, partition maps, deterministic count sequences          |
| training                 | **not applicable**                                                                                                         | none                                                                                              |
| scoring                  | population solver/oracle/comparator calculations and sequential confidence/envelope/projection calculations                | population summaries, profiles, comparator fits, streams, CS trajectories, envelopes, projections |
| calibration/thresholding | no learned calibration; $\rho,\beta,\delta$, materiality thresholds, and multiplicity rules are prespecified               | no fitted calibration artifact                                                                    |
| evaluation               | theorem/oracle checks, state assignment, stream metrics, runtime measurements                                              | validated results, stream metrics, validation records, runtime records                            |
| analysis                 | paired comparisons, bootstrap CIs, sign-flip tests, Holm adjustment, materiality and claim synthesis                       | statistical artifacts, claim-state artifacts, source-data Parquet                                 |
| reporting                | deterministic rendering/export only                                                                                        | CSV/TeX/SVG/PNG and report summaries                                                              |

No predictive training, score generation, train/validation/test split, learned threshold selection, or post-hoc calibration may be introduced.

## 14.2 Canonical reusable artifact layers

1. Prepared law and partition artifacts.
2. Stochastic event streams and validated prefixes.
3. Deterministic coarsenings/count prefixes.
4. Population sufficient summaries.
5. Population solver and oracle results.
6. Comparator fits and reference calculations.
7. Sequential confidence artifacts.
8. Sequential projection artifacts.
9. Evaluation and statistical artifacts.
10. Source-data and display artifacts.

A shorter stochastic consumer may use a validated prefix of a longer compatible stream.

A longer consumer may extend an existing stream only when the generator/seed identity proves that the extension is exactly the same semantic stream.

Runtime benchmark target computations are never satisfied by cached target outputs inside the timed region.

## 14.3 Explicit producer dependency contracts

The implementation-component digest for a producer is SHA-256 over the sorted set of registered source files:

```text
relative_path + NUL + file_sha256 + LF
```

The following component registrations are authoritative minimum sets. Imports from another scientific component add that imported component transitively.

| Producer/artifact class       | Scientific clauses | Implementation components                                                                    | Material runtime dependencies      | Required parents               |
| ----------------------------- | ------------------ | -------------------------------------------------------------------------------------------- | ---------------------------------- | ------------------------------ |
| configuration snapshot        | §4                 | `configuration/models.py`, `loading.py`, `validation.py`, `protocol.py`                      | PyYAML                             | `configs/trajcert.yaml`        |
| law manifest/full law         | §§5.1–5.4          | `data/synthetic/laws.py`, `generator.py`                                                     | NumPy                              | configuration snapshot         |
| partition manifest/coarsening | §§3, 5.1, 5.8      | `data/partitions.py`                                                                         | NumPy                              | configuration snapshot         |
| prepared synthetic input      | §§5.5–5.8          | `data/synthetic/preprocessing.py`, `ledger.py`, `data/integrity.py`, `data/apportionment.py` | NumPy, Pandas, PyArrow             | law + partition manifests      |
| event stream                  | §§5.5–5.6, 9.11    | `data/synthetic/generator.py`, `ledger.py`                                                   | NumPy                              | law manifest, seed manifest    |
| population summary/profile    | §§3.3–3.7          | `math/entropy.py`, `information_profile.py`                                                  | NumPy, SciPy                       | prepared law/partition         |
| population risk set           | §§3.6, 3.10        | `math/risk_set.py`, `solver.py`                                                              | NumPy, SciPy                       | population summary             |
| refinement/safety             | §§3.7–3.8          | `math/refinement.py`, `safety.py`                                                            | NumPy, SciPy                       | population summary/risk set    |
| legacy comparator             | §7.4               | `baselines/legacy_odds.py`                                                                   | NumPy                              | population summary             |
| callbacks                     | §§7.5–7.6          | `baselines/callbacks.py`                                                                     | mpmath                             | population summary             |
| pattern mixture               | §7.7               | `baselines/pattern_mixture.py`                                                               | NumPy, SciPy                       | population summary             |
| information oracle            | §7.8               | `baselines/information_oracle.py`                                                            | mpmath                             | prepared law/partition         |
| categorical CS                | §9.2               | `inference/confidence_sequence.py`                                                           | NumPy, SciPy                       | count trajectory               |
| summary envelope              | §9.3               | `inference/envelope.py`                                                                      | NumPy                              | CS artifact                    |
| outer projection              | §9.4               | `inference/projection.py`                                                                    | python-flint                       | envelope                       |
| finite-sample compatibility   | §§9.5–9.6          | `inference/compatibility.py`                                                                 | python-flint                       | envelope                       |
| operational states            | §9.7               | `inference/states.py`                                                                        | none beyond parents                | projection + compatibility     |
| metrics                       | §8                 | `analysis/metrics.py`                                                                        | NumPy, Pandas                      | result records                 |
| statistical inference         | §9.9               | `analysis/statistics.py`                                                                     | NumPy, SciPy                       | paired metrics                 |
| materiality                   | §§21.8–21.9        | `analysis/materiality.py`                                                                    | NumPy, Pandas                      | metrics/statistics             |
| claims                        | §21                | `analysis/claims.py`, `synthesis.py`                                                         | Pandas                             | required evidence artifacts    |
| benchmark                     | §18.12             | `evaluation/benchmarking.py`                                                                 | Python stdlib, target dependencies | prepared target inputs         |
| tables                        | §19                | `reporting/tables.py`                                                                        | Pandas, PyArrow                    | declared aggregate source data |
| figures                       | §20                | `reporting/figures.py`                                                                       | Matplotlib, Pandas, PyArrow        | declared figure source data    |

`scientific_dependency_digest` is computed from the exact named roadmap subsection text plus applicable configuration fragments.

Changing an unrelated subsection does not invalidate an artifact.

## 14.4 Selective invalidation boundaries

| Artifact boundary          | Must be recomputed when                                                                              | Must not be recomputed solely because                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| dataset/source preparation | source checksum, eligibility semantics, generator parameters/component, event/label semantics change | solver/statistics/plot/report/test changes                       |
| preprocessing/partitioning | prepared input, partition map, terminal horizon, preprocessing component changes                     | rho/beta/statistics/report changes                               |
| event streams              | law, generator, seed namespace/index, stream identity changes                                        | solver/statistics/report changes                                 |
| population summaries       | observable law, partition, profile code/numerics change                                              | beta/sequential/statistics/report changes                        |
| comparator fits            | input, fit definition/settings/component changes                                                     | downstream sensitivity value when fit-independent                |
| solver/oracle outputs      | parent summary, applicable sensitivity coordinate, solver/oracle implementation/tolerance changes    | downstream beta when bound is beta-independent                   |
| categorical CS/envelopes   | stream/count, partition, delta, CS/envelope implementation changes                                   | rho/beta/metric/report changes                                   |
| outer projection           | envelope, rho, projection implementation/numerics changes                                            | beta/statistics/rendering changes                                |
| operational states         | projection, beta, evidence gate, state-precedence rule changes                                       | statistical/rendering changes                                    |
| statistical analysis       | metric input or statistical contract changes                                                         | upstream code changes leaving consumed metric artifact unchanged |
| source-data tables         | consumed scientific/statistical artifact or source transformation changes                            | renderer-only changes                                            |
| figures/tables/report      | source data or renderer contract changes                                                             | unrelated scientific code/tests/docs                             |
| runtime measurements       | target computation, benchmark inputs/configuration, runtime environment changes                      | renderer/test/doc changes                                        |

## 14.5 Validation, stale-descendant handling, and atomic replacement

Before scientific work:

```text
validate existing artifacts
-> reuse compatible artifacts
-> identify stale descendants
-> remove stale active descendants
-> recompute only missing or invalid roots
-> continue execution
```

Artifact validation outcomes:

```text
VALID
PARTIAL
STALE
CORRUPT
INCOMPATIBLE
MISSING
```

Only `VALID` artifacts may be consumed as authoritative inputs.

If regenerated canonical scientific content and dependency identity are unchanged, descendants remain valid even if provenance bytes differ.

## 14.6 Idempotent execution and overwrite

A complete active cell is reused when every required artifact and completion marker validate against current dependency fingerprints.

`--overwrite` forces recomputation only of the selected command's owned output roots.

Valid upstream shared artifacts are retained.

Descendants are invalidated only when replacement changes parent scientific-content/dependency identity.

## 14.7 Checkpoint recovery

Coverage recovery uses the configured coverage seed interval and batch size.

Utility recovery uses the configured utility interval and batch size.

The current contracts yield:

```text
coverage batches = 50
utility batches = 10
```

Each checkpoint records:

```text
semantic_cell_key
artifact_key
dependency_fingerprint
provenance_fingerprint
cell_plan_digest
batch_index
seed_index_start
seed_index_stop_exclusive
input_artifact_keys
input_artifact_digests
result_file_sha256
completed
```

Recovery:

1. validates semantic coordinates;
2. validates dependency fingerprint;
3. validates parent digests;
4. validates checkpoint checksum;
5. runs only missing seed ranges;
6. concatenates by seed index;
7. recomputes aggregates/statistics from the complete set;
8. writes completion last.

# 15. Logging and Provenance

Read-only commands (`doctor`, `plan`, `status`) do not mutate active scientific artifacts.

The reusable provenance envelope records:

```text
Git commit
dirty-tree flag
dependency-lock SHA-256
container image digest
Python implementation/version
OS/kernel
CPU model
package versions
arithmetic/threading environment variables
input checksums
semantic coordinates
scientific specification digest
scientific dependency digest
implementation component digest
environment dependency digest
dependency fingerprint
partition/law/dataset checksums
seed-manifest checksums
execution timestamps
```

Authoritative claim-bearing `trajcert run` execution requires a clean source tree:

```text
git status --porcelain=v1 --untracked-files=all
```

must return no entries.

The source commit is obtained by:

```text
git rev-parse HEAD
```

If Git metadata is unavailable, claim-bearing `run` is blocked with `environment_or_prerequisite_block`.

The container image digest is supplied to the running container as:

```text
TRAJCERT_CONTAINER_IMAGE_DIGEST
```

and must be populated by the launcher from the OCI/Docker image inspection result. Authoritative claim-bearing execution is blocked when this value is absent.

The environment manifest records the value verbatim and validates that it is a nonempty OCI/Docker digest or immutable image identifier.

`runtime_environment.authoritative_execution` fixes authoritative execution to CPU. GPU acceleration may not substitute for that environment.

Provenance establishes audit lineage. Reuse compatibility is established by dependency fingerprints.

# 16. Public CLI

Executable:

```text
trajcert
```

Public commands:

```text
trajcert doctor
trajcert preprocess ["<descriptive dataset name>"] [--overwrite]
trajcert plan
trajcert smoke [--overwrite]
trajcert run "<descriptive experiment name>" [--overwrite]
trajcert status ["<descriptive experiment name>"]
trajcert report ["<descriptive experiment name>"] [--overwrite]
```

No public flag exposes:

```text
execution group
seed
rho
beta
delta
partition
baseline
method
variant
scientific configuration file
cache/checkpoint mode
internal semantic cell
```

Exit codes:

```text
success_or_scientific_noop            = 0
usage_or_unknown_name                 = 2
environment_or_prerequisite_block     = 10
technical_execution_failure           = 20
completion_or_evidence_failure        = 30
```

Command contract:

* `doctor`: read-only workspace/environment/dataset/experiment/artifact-DAG integrity and next-valid-action view.
* `preprocess`: validates and deterministically materializes current-plan datasets, laws, manifests, mappings, checksums, and observed structure.
* `plan`: read-only registry expansion/dependency view. It must reproduce the exact total in Section 17.
* `smoke`: executes the exact smoke fixtures below.
* `run`: executes one authoritative registry experiment, reusing compatible artifacts and recovering compatible checkpoints.
* `status`: read-only lifecycle/progress/blocking/export-state inspection.
* `report`: performs no new science; exports only verified completed evidence.

`preprocess "<descriptive dataset name>"` accepts:

* an exact configured synthetic law name;
* a future exact external dataset manifest name.

Unknown names return exit code `2`.

Bare `preprocess` processes all current-plan sources.

## 16.1 Exact smoke fixtures

The configured smoke counts resolve to:

### Compatible population case

```text
law = Timing and terminal: harmful outcomes resolve late
partition = 8-band partition
rho = tau + 0.01
expected = compatible nonempty risk set
```

### Incompatible population case

```text
law = Timing only: harmful outcomes resolve late
partition = 8-band partition
rho = tau / 2
expected = MODEL_INCOMPATIBLE
```

### Endpoint-only case

```text
law = Timing and terminal: harmful outcomes resolve late
partition = Endpoint-only partition
rho = budgets.information_nats
expected tau = 0
```

### Refinement case

```text
law = Timing and terminal: harmful outcomes resolve late
fine = 8-band partition
coarse = 4-band partition
rho = tau_fine + 0.025
expected fine risk set subset of coarse
```

### Deterministic CS case

```text
law = Timing and terminal: harmful outcomes resolve late
partition = 2-band partition
events = smoke.deterministic_cs_event_count
construction = balanced-prefix
expected = valid nonempty running CS/simplex at every prefix
```

### Low-dimensional outer-optimizer case

Use the exact population observable law for:

```text
law = Timing and terminal: harmful outcomes resolve late
partition = 2-band partition
```

as a singleton envelope:

```text
A_L=A_U=A
G_L=G_U=G
c_L=c_U=c
C_L=C_U=C
rho=tau+0.01
```

The certified outer projection must agree with the population upper endpoint within `numerics.identity_atol`.

# 17. Authoritative Experiment Registry

This table is the authoritative experiment registry. Experiment names, execution groups, evidence classes, expansions, counts, and row order are fixed here.

| Execution group                         | Experiment                                 | Class            | Expansion                              |     Cells |
| --------------------------------------- | ------------------------------------------ | ---------------- | -------------------------------------- | --------: |
| Inventory validation                    | Scientific and Data Inventory              | VALIDATION       | one protocol/inventory gate            |         1 |
| Formal mathematics validation           | Legacy Partition Incoherence Check         | VALIDATION       | 3 Gamma × 2 q                          |         6 |
| Formal mathematics validation           | Path Information Decomposition             | VALIDATION       | 12 laws × 4 partitions                 |        48 |
| Formal mathematics validation           | Information Profile Convexity              | VALIDATION       | 12 laws × 4 partitions                 |        48 |
| Formal mathematics validation           | Minimum Compatibility Identity             | VALIDATION       | 12 laws × 4 partitions                 |        48 |
| Formal mathematics validation           | Sharp-Set Constructive Identity            | VALIDATION       | 12 laws × 4 partitions × 4 rho offsets |       192 |
| Formal mathematics validation           | Refinement Dominance Identity              | VALIDATION       | 12 laws × 3 adjacent pairs             |        36 |
| Formal mathematics validation           | Strict Timing-Gain Identity                | VALIDATION       | 6 cases × 3 offsets                    |        18 |
| Formal mathematics validation           | Safety-Boundary Identity                   | VALIDATION       | 12 laws × 5 safety-budget cases        |        60 |
| Formal mathematics validation           | Endpoint Special-Case Identity             | VALIDATION       | 12 laws                                |        12 |
| Formal mathematics validation           | Anytime Projection Proof Check             | VALIDATION       | one proof/dependency record            |         1 |
| Formal mathematics validation           | Population Complexity Proof Check          | VALIDATION       | one operation-count record             |         1 |
| Solver validation                       | Production Solver vs Independent Oracle    | VALIDATION       | 12 laws × 4 partitions × 5 offsets     |       240 |
| Comparator reduction                    | Callback-Model Reduction Falsification     | CONFIRMATORY     | 12 finest-partition laws               |        12 |
| Comparator reduction                    | Generic Information-Optimization Reduction | CONFIRMATORY     | 12 finest-partition laws               |        12 |
| Partition and timing mechanism          | Partition Coherence                        | CONFIRMATORY     | 6 laws × 3 pairs × 3 offsets           |        54 |
| Partition and timing mechanism          | Same Endpoint, Different Timing            | ABLATION         | 4 partitions × 5 rho paired-law cells  |        20 |
| Partition and timing mechanism          | Strict Timing Gain                         | CONFIRMATORY     | 6 cases × 3 offsets                    |        18 |
| Compatibility, sharpness, and safety    | Compatibility Floor Behavior               | CONFIRMATORY     | 12 laws × 2 partitions                 |        24 |
| Compatibility, sharpness, and safety    | Sharpness Against Generic Oracle           | CONFIRMATORY     | 10 laws × 4 partitions                 |        40 |
| Compatibility, sharpness, and safety    | Safety and Intrinsic Impossibility         | CONFIRMATORY     | 8 laws × 5 safety-budget cases         |        40 |
| Finite-sample implementation validation | Anytime Implementation Hand Cases          | VALIDATION       | 10 hand cases × 3 partitions           |        30 |
| Anytime coverage validation             | Anytime Coverage Stress                    | CONFIRMATORY     | 12 stress cases                        |        12 |
| Utility analysis                        | Population Sensitivity Utility             | ROBUSTNESS       | 6 laws × 4 partitions × 15 rho         |       360 |
| Utility analysis                        | Sequential Sensitivity Utility             | ROBUSTNESS       | 6 laws × 3 rho                         |        18 |
| Failure-boundary analysis               | Failure Boundary Atlas                     | FAILURE_BOUNDARY | 9 axes × 7 levels                      |        63 |
| Real-trajectory generalization          | Real-Trajectory Validation                 | GENERALIZATION   | absent                                 |         0 |
| Foreign-information diagnostic          | Foreign-Information Negative Control       | DIAGNOSTIC       | absent                                 |         0 |
| Computational scaling                   | Computational Scaling                      | VALIDATION       | 8 K values                             |         8 |
| Statistical synthesis                   | Statistical Synthesis                      | VALIDATION       | deterministic synthesis                |         1 |
| **TOTAL**                               |                                            |                  |                                        | **1,423** |

No experiment exists outside this registry.

# 18. Experiment-Specific Contracts

## 18.0 Experiment dependency and required-output map

Where two cells request the same intermediate calculation with identical dependency fingerprints, compute it once and reference it from both.

Each deterministic cell requires one schema-valid primary result record unless otherwise stated.

| Experiment                                 | Required/reusable inputs                                               | Required authoritative cell outputs                                                      |
| ------------------------------------------ | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Scientific and Data Inventory              | configuration snapshot, prepared laws, partition/seed manifests, smoke | validation record                                                                        |
| Legacy Partition Incoherence Check         | §7.4.1 construction                                                    | counterexample result                                                                    |
| Path Information Decomposition             | population summaries                                                   | theorem result                                                                           |
| Information Profile Convexity              | population profiles                                                    | theorem result                                                                           |
| Minimum Compatibility Identity             | population summaries                                                   | theorem result                                                                           |
| Sharp-Set Constructive Identity            | solver/oracle                                                          | theorem result                                                                           |
| Refinement Dominance Identity              | fine/coarse profiles                                                   | theorem result                                                                           |
| Strict Timing-Gain Identity                | fine/coarse bounds                                                     | theorem result                                                                           |
| Safety-Boundary Identity                   | safety quantities                                                      | theorem result                                                                           |
| Endpoint Special-Case Identity             | endpoint summary                                                       | theorem result                                                                           |
| Anytime Projection Proof Check             | proof/dependency specification                                         | proof validation result                                                                  |
| Population Complexity Proof Check          | implementation/component definition                                    | operation-count result                                                                   |
| Production Solver vs Independent Oracle    | solver + oracle                                                        | comparison result                                                                        |
| Callback-Model Reduction Falsification     | comparator artifacts                                                   | comparator-reduction result                                                              |
| Generic Information-Optimization Reduction | generic information oracle                                             | reduction result                                                                         |
| Partition Coherence                        | fine/coarse population results                                         | coherence result                                                                         |
| Same Endpoint, Different Timing            | paired two-law results                                                 | paired ablation result                                                                   |
| Strict Timing Gain                         | fine/coarse results                                                    | timing-gain result                                                                       |
| Compatibility Floor Behavior               | population summaries/bounds                                            | phase result                                                                             |
| Sharpness Against Generic Oracle           | production + oracle                                                    | sharpness result                                                                         |
| Safety and Intrinsic Impossibility         | safety results                                                         | safety result                                                                            |
| Anytime Implementation Hand Cases          | exact hand fixtures                                                    | hand validation result                                                                   |
| Anytime Coverage Stress                    | streams, CS, projection                                                | per-update parquet + per-stream parquet + aggregate validation record                    |
| Population Sensitivity Utility             | population bounds                                                      | utility result                                                                           |
| Sequential Sensitivity Utility             | shared streams/projections                                             | paired per-stream parquet + per-condition aggregate                                      |
| Failure Boundary Atlas                     | axis-specific inputs                                                   | boundary result                                                                          |
| Computational Scaling                      | benchmark inputs                                                       | repetition parquet + summary result                                                      |
| Statistical Synthesis                      | all required completed evidence                                        | synthesis record + cross-experiment source data + claim registry + hostile-review record |

Experiment overall state becomes `COMPLETED` only when:

* all executable cells are `COMPLETED`;
* all experiment-level required aggregates/statistics/source-data products validate;
* planned invalid/nonapplicable combinations are accounted for;
* no required artifact is stale or missing.

## 18.1 Inventory validation — Scientific and Data Inventory

Requires:

```text
environment interpretable
synthetic preprocessing pass
smoke pass
registry total = 1423
semantic-cell uniqueness pass
```

It checks all configured constants, twelve generated laws, partition/seed manifests, schemas, real-data status, nonnegative masses, law sums, source/component registrations, and registry counts.

## 18.2 Formal mathematics validation

### Rho-offset resolution

The offset semantics are fixed:

`Sharp-Set Constructive Identity`:

$$
\rho=\tau_\Pi+d,
\qquad
d\in\texttt{sensitivity.theorem＿rho＿offsets.sharp＿set}.
$$

`Production Solver vs Independent Oracle`:

$$
\rho=\tau_\Pi+d,
\qquad
d\in\texttt{sensitivity.theorem＿rho＿offsets.oracle＿validation}.
$$

`Partition Coherence`, `Strict Timing-Gain Identity`, and `Strict Timing Gain`:

$$
\rho=\tau_{\text{fine}}+d,
\qquad
d\in\texttt{sensitivity.theorem＿rho＿offsets.refinement＿above＿fine＿tau}.
$$

No offset is interpreted relative to a coarse $\tau$ unless explicitly stated elsewhere.

`Information Profile Convexity` evaluates exactly `numerics.convexity_profile_grid_points` equally spaced $u$ points in `[0,c]` per law/partition.

Second derivatives are evaluated only in the interior and checked by symbolic/high-precision direct differentiation, not finite differences.

`Sharp-Set Constructive Identity` uses exact production endpoints, independent oracle endpoints, and exactly `numerics.constructive_profile_grid_points` diagnostic grid points.

The grid never defines roots.

## 18.3 Solver validation — Production Solver vs Independent Oracle

Across all cells:

```text
state mismatches = 0
endpoint absolute error <= numerics.identity_atol
root bracket width <= numerics.root_atol
returned-root residual <= numerics.identity_atol
```

Static architecture validation must verify oracle independence.

For Table 6 `rho_star` validation, use:

```text
beta = budgets.risk
```

For each law/partition, compute $\rho^\star$ only when the Section 3.8 interior safety-frontier regime applies.

Production:

$$
\rho^\star_{\text{prod}}=\mathcal S_\Pi(\beta-A).
$$

Oracle:

construct the full table at hidden mass

$$
u=\beta-A
$$

and compute direct-table mutual information.

If the interior regime does not apply:

```text
rho_star_error = null
rho_star_status = NOT_APPLICABLE
```

Table 6 aggregates `max_abs_rho_star_error` over applicable rows only.

## 18.4 Comparator reduction

For every 8-band law, execute all internal comparator evaluations inside the one law-level registry cell.

Evaluate:

```text
ALHO common-slope callback
Stable-resistance callback
Repeated-attempt pattern mixture
Legacy bandwise odds-ratio sensitivity
Generic MI-constrained oracle
```

Internal grids:

```text
legacy Gamma = comparators.legacy_gamma
pattern-mixture C = comparators.pattern_mixture.c
generic MI rho = grids.rho plus exact log(2)
```

No $\Gamma\leftrightarrow\rho$ or $C\leftrightarrow\rho$ calibration is inferred.

Each comparator result records:

```text
observation access
assumptions
sensitivity parameter
feasible risk set or point estimate
applicability status
numeric status
exact-equality-to-TrajCert flag where same sensitivity semantics exist
```

These experiments are prior-method reduction/falsification diagnostics. They do not create a separate Section 21 claim state.

If an existing comparator is found to reproduce a TrajCert result at a tested setting, that equality is retained and reported; it does not justify a universal equivalence claim.

## 18.5 Partition and timing mechanism

`Partition Coherence` uses:

```text
6 utility_and_coherence_laws
8->4
4->2
2->Endpoint
3 refinement offsets
```

`Same Endpoint, Different Timing` consists of **20 paired-law semantic cells**, not 40 separate law cells.

Each cell coordinate is:

```text
experiment_name = Same Endpoint, Different Timing
comparison_pair_name =
  "Same endpoint without timing information|Same endpoint with timing information"
partition_name = one primary partition
rho = one same_endpoint_rho_grid value
```

Within one paired cell, compute both laws and report their separate $\tau$, risk intervals, and their difference.

`Strict Timing Gain` uses the six configured timing cases and:

$$
\rho=\tau_{\text{fine}}+d.
$$

Required:

```text
fine sharp set subset of coarse
profile difference = Delta tau
zero-information gain <= numerics.identity_atol
positive-information gain > numerics.identity_atol
  when theorem conditions hold
```

## 18.6 Compatibility, sharpness, and safety

`Compatibility Floor Behavior` uses 8-band and endpoint-only partitions and internally checks:

$$
\rho=\tau-d,\quad\tau,\quad\tau+d
$$

where

$$
d=
\texttt{sensitivity.theorem＿rho＿offsets.refinement＿above＿fine＿tau[0]}.
$$

For endpoint-only partition:

```text
tau = 0
below-floor case = NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET
```

without adding a separate registry cell.

`Sharpness Against Generic Oracle` uses:

$$
\rho=
\tau+
\texttt{sensitivity.confirmatory＿sharpness＿oracle＿offset＿above＿tau}.
$$

`Safety and Intrinsic Impossibility` uses the five deterministic beta regimes.

## 18.7 Finite-sample implementation validation — Anytime Implementation Hand Cases

The ten hand cases are run independently on:

```text
2-band partition
4-band partition
8-band partition
```

giving 30 cells.

### 1. Insufficient matured events

```text
law = Timing and terminal: harmful outcomes resolve late
construction = balanced-prefix
n_matured = 199
expected = INSUFFICIENT_EVIDENCE
```

### 2. Insufficient resolved events

At $n=200$:

```text
n_resolved = 49
n_unresolved = 151
```

Allocate the 49 finite observations across finite categories in proportion to the principal law's conditional finite-category probabilities using Hamilton apportionment.

Define the final 200-category empirical probability vector from those exact counts and construct the sequence by balanced-prefix.

Expected:

```text
INSUFFICIENT_EVIDENCE
```

### 3. Model-incompatible singleton

Use:

```text
law = Timing only: harmful outcomes resolve late
confidence envelope = exact singleton population observable law
```

Define:

$$
d=\min(0.005,\tau/2)
$$

and

$$
\rho=\tau-d.
$$

For every 2-, 4-, and 8-band cell, $\tau\gt 0$, hence $d\gt 0$ and $\rho\lt \tau$.

Expected:

```text
MODEL_INCOMPATIBLE
```

### 4. Intrinsic-impossibility singleton

```text
law = Intrinsic safety impossibility
confidence envelope = exact singleton
rho = tau + 0.01
beta = budgets.risk
expected = INTRINSICALLY_UNCERTIFIABLE
```

### 5. Certified singleton

```text
law = Timing and terminal: harmful outcomes resolve late
confidence envelope = exact singleton
rho = tau + 0.01
beta = min(1, theta_U(rho) + 0.005)
expected = CERTIFIED
```

### 6. Uncertified singleton

```text
law = Timing and terminal: harmful outcomes resolve late
confidence envelope = exact singleton
rho = tau + 0.01
beta = theta_dagger
expected = UNCERTIFIED
```

### 7. Zero resolved mass remains plausible

This is an internal optimizer/state fixture, not a claim that such an envelope arose from a particular observed CS.

Use:

```text
n_matured = 200
n_resolved = 50
evidence-count gate = PASS
```

and construct a valid envelope whose feasible $(A,G)$ domain includes:

```text
(A,G) = (0,0)
```

and at least one point satisfying:

```text
A+G > 0
```

with a nonempty compatible subset.

Expected:

```text
INTRINSICALLY_UNCERTIFIABLE forbidden
operational state = UNCERTIFIED unless MODEL_INCOMPATIBLE is independently proven
zero_resolved_mass_plausible = true
```

This case validates Section 9.6 state logic only.

### 8. No unresolved mass

Use exact singleton:

```text
c = 0
beta = A
rho = budgets.information_nats
expected = CERTIFIED
risk upper = A
```

### 9. Simplex boundary

For each $K$, construct observable masses:

$$
c=0.20,
\qquad
A=0.10,
\qquad
G=0.70.
$$

Set:

```text
a_1 = 0
a_k = A/(K-1) for k=2..K
b_k = G/K for every k
```

for $K\ge2$.

Use exact singleton envelope.

Set hidden terminal harmful mass for the independent full-law fixture:

$$
u=0.05.
$$

Set:

$$
\rho=I_{\text{true}}+0.01,
\qquad
\beta=0.50.
$$

Expected projection is the independent projection-oracle result.

### 10. Optimizer conservative fallback

```text
law = Timing and terminal: harmful outcomes resolve late
construction = balanced-prefix
n = 500
rho = I_true + 0.01
diagnostic node cap = 1
```

Required:

```text
return proven conservative upper or 1.0
never return feasible incumbent as certified upper
anti-conservatism <= numerics.identity_atol
```

### Hand-case applicability

Count-sequence cases validate CS inversion/running intersections.

Singleton-envelope cases validate projection and state logic and do not pretend to validate CS construction from an artificial singleton.

Every applicable component must pass.

### Independent projection oracle

`evaluation/projection_oracle.py` is independent of `inference/projection.py`.

For singleton envelopes, compute the exact population solution using direct high-precision full-table mutual information as in Section 7.8.

For non-singleton hand fixtures, the oracle is a deterministic feasible-point lower-bound search:

1. enumerate a $1001\times1001$ grid over the feasible $A,G$ rectangle;
2. reject points violating simplex/terminal constraints;
3. for every retained $(A,G)$, solve the maximal feasible $u$ with 100-decimal-digit direct-table arithmetic;
4. retain the largest verified feasible $A+u$;
5. locally refine the best 20 grid points using deterministic bounded optimization;
6. accept only directly verified feasible points.

Because this oracle produces verified feasible lower bounds, a production certified upper smaller than its best feasible value by more than `numerics.identity_atol` is an anti-conservative implementation failure.

## 18.8 Anytime coverage validation — Anytime Coverage Stress

Run every configured stress case.

For cases with `rho_offset_above_true_information`:

$$
\rho=I_{\text{true}}+\text{offset}.
$$

For minimum-information completion:

$$
\rho=\tau+\texttt{rho＿offset＿above＿compatibility＿floor}.
$$

All stress cases except near-certification use:

$$
\beta=\texttt{budgets.primary＿risk}.
$$

Near-certification uses:

$$
\beta=\theta_U(\rho)+
\texttt{beta＿offset＿above＿true＿upper＿bound}.
$$

If derived $\beta\gt 1$:

```text
planned case = INVALID
```

and it is not clipped.

The four configured method labels are executed exactly.

`TrajCert` and `Time-uniform observable-law projection` share the same valid $U_n(\rho)$ artifact but expose different reporting semantics under Section 7.9.

The ignorable-delay reference is valid only for `Independent resolution control`.

Each stress cell contains exactly 5,000 independent streams, each through 500 matured events.

Every primary TrajCert stress cell must pass Section 9.8.

## 18.9 Utility analysis

`Population Sensitivity Utility` uses:

```text
6 laws
4 partitions
14 numeric primary_rho_grid values
+ exact log(2)
= 15 rho values
```

giving:

$$
6\times4\times15=360
$$

cells.

Every cell is retained, including incompatible points.

### Population materiality

Population claim qualification is evaluated only on the primary 8-band partition.

For one compatible 8-band cell:

$$
\text{absolute tightening} =
(A+c)-\theta_U(\rho).
$$

When $c\gt 0$,

$$
\text{relative unresolved gain} =
\frac{(A+c)-\theta_U(\rho)}{c}.
$$

A compatible rho value is materially nonvacuous iff:

```text
absolute tightening >= materiality.population.absolute_tightening
AND
relative unresolved gain >= materiality.population.relative_unresolved_gain
```

A law qualifies iff at least:

```text
materiality.population.compatible_rho_values
```

prespecified rho values qualify.

The Practical Synthetic Nonvacuity claim is supported iff at least:

```text
materiality.population.qualifying_laws
```

laws qualify.

Incompatible rho values remain visible but cannot count as materiality successes.

### Sequential utility

For each law/rho condition, 8-band and endpoint-only methods use the same underlying finest-path streams.

Exactly 500 streams are used.

All three practical metrics generate paired inference and remain in the 54-test Holm family.

For the **claim-level qualifying-law vote**, the materiality metric is specifically:

```text
Certified update fraction
```

A law qualifies iff at least one of its three prespecified rho conditions satisfies all of:

```text
mean favorable certified-update-fraction difference
  >= materiality.sequential.certified_fraction_gain

bootstrap lower bound
  > materiality.sequential.paired_bootstrap_lower_bound_must_exceed

Holm-adjusted p-value
  < confidence.alpha
```

The other two practical metrics remain mandatory reported secondary evidence but do not independently create a law-level materiality vote because no separate materiality threshold is configured for them.

## 18.10 Failure-boundary analysis — Failure Boundary Atlas

Use the nine one-at-a-time axes.

The base law is `failure_boundary.base_law`.

Unless an axis changes them:

```text
K = method.finest_bands
rho = budgets.information_nats
beta = budgets.risk
```

Axis derivations:

* **Terminal unresolved severity:** $q_1=q_0$ at configured levels.
* **Timing contrast:** $\lambda_1=d/2,\lambda_0=-d/2$.
* **Harmful prevalence:** set $\theta$.
* **Path resolution:** set $K$.
* **Sensitivity margin above compatibility:** $\rho=\tau+d$.
* **Risk-budget offset from intrinsic boundary:** $\beta=\mathrm{clip}(\theta^\dagger+d,0,1)$.
* **Matured sample size:** use balanced-prefix at configured $n$.
* **Terminal-selection asymmetry:** use configured $(q_1,q_0)$.
* **Optimizer-node budget:** use configured diagnostic node cap and deterministic $n=500$.

Population-valued axes use exact population calculations.

Sample-size and optimizer-node axes use deterministic finite-sample inputs.

For Table 11:

* population-valued axes use population scientific state in `operational_state`;
* `optimizer_gap=null` for population-valued axes;
* `runtime_ms=null` unless the axis actually executes the finite-sample optimizer;
* finite-sample axes populate optimizer/runtime values when available.

## 18.11 Planned nonapplicabilities

`Real-Trajectory Validation` and `Foreign-Information Negative Control` have zero executable cells.

No current real-trajectory command or foreign-information mechanism exists.

## 18.12 Computational scaling

Use all configured $K$ values.

Population solver:

```text
rho = budgets.information_nats
```

Outer projection:

```text
n = runtime_benchmark.outer_projection_input.n
construction = balanced-prefix
rho = I_true + runtime_benchmark.outer_projection_rho_offset_above_true_information
beta = budgets.risk
```

Population and outer-projection targets are timed separately.

Each target executes:

```text
5 warmups
30 measured repetitions
```

Every measured repetition executes fresh in an isolated single-thread Linux process.

Use:

```text
time.perf_counter_ns
resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
```

Linux `ru_maxrss` is KiB and is divided by 1024 for MiB.

Report per target:

```text
median runtime
IQR runtime
mean runtime
sample SD runtime
peak RSS
```

For population root iterations, one repetition's count is:

```text
lower-branch iterations + upper-branch iterations
```

with zero iterations for analytically resolved boundary/incompatible branches.

Table 12:

```text
peak_memory_mib =
  max(population peak RSS across measured repetitions,
      outer-projection peak RSS across measured repetitions)
```

`median_root_iterations` is the median of total branch iterations across the 30 population measured repetitions.

`median_outer_nodes` is the median outer-node count across the 30 projection measured repetitions.

Empirical slopes are descriptive only.

## 18.13 Statistical synthesis

`Statistical Synthesis` executes once after all required upstream experiments are complete.

It:

1. validates all required semantic-cell completion markers;
2. validates schemas/checksums/dependency fingerprints;
3. recomputes no scientific cell;
4. computes cross-experiment deterministic aggregates;
5. verifies the complete 54-test Holm family;
6. applies materiality;
7. mechanically assigns claim states;
8. produces Tables 5, 7, 8, 10, and 13 source data;
9. produces cross-experiment Figure 1 source data;
10. performs the local-validity audits in Section 21.11;
11. performs Section 27 hostile-review checks;
12. constructs the project evidence manifest in `outputs/experiments/statistical-synthesis/provenance/dependencies/`.

A scientific falsification or null does not block synthesis when execution is valid; it changes the relevant claim state.

Missing, stale, invalid, or technically failed mandatory evidence blocks synthesis.

# 19. Required Tables

All manuscript tables are deterministic renders of authoritative Parquet.

Experiment-owned CSV and TeX filenames are exactly the source basename with:

```text
.csv
.tex
```

extensions.

For example:

```text
solver_oracle_validation.parquet
solver_oracle_validation.csv
solver_oracle_validation.tex
```

Median/IQR quantiles use linear interpolation at index:

$$
(n-1)q.
$$

Display rounding never feeds scientific comparison.

P-values below `display.pvalue_display_below` are rendered as:

```text
<0.0001
```

at current configuration.

## Table 1 — Scientific constants and numerical protocol

```text
outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/protocol_constants.parquet
```

Columns:

```text
quantity
value
unit
value_class
fixed_or_swept
scientific_role
```

## Table 2 — Synthetic laws

```text
outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/synthetic_laws.parquet
```

Columns:

```text
law_name
theta
q1
q0
lambda1
lambda0
K
A
G
c
tau_at_8_band_partition
true_mutual_information_at_8_band_partition
scientific_role
```

## Table 3 — Baseline assumptions

```text
outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/baselines.parquet
```

Columns:

```text
baseline_name
purpose
observation_access
assumption
numerical_contract
sensitivity_grid
seed_pairing
metrics
valid_scope
forbidden_interpretation
```

## Table 4 — Experiment matrix

```text
outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/experiment_matrix.parquet
```

Columns:

```text
execution_group
experiment_name
classification
purpose
cell_expansion
cell_count
primary_metrics
claim_ids
```

## Table 5 — Theorem validation

```text
outputs/experiments/statistical-synthesis/evaluations/aggregates/theorem_validation_summary.parquet
```

Columns:

```text
theorem_name
case_count
maximum_absolute_error
minimum_inequality_margin
all_cases_pass
primary_artifact
scientific_consequence
```

## Table 6 — Production/oracle validation

```text
outputs/experiments/production-solver-vs-independent-oracle/evaluations/aggregates/solver_oracle_validation.parquet
```

Columns:

```text
partition_name
rho_offset_mode
cell_count
max_abs_u_lower_error
max_abs_u_upper_error
max_abs_risk_upper_error
max_abs_rho_star_error
rho_star_applicable_cell_count
state_mismatch_count
pass
```

## Table 7 — Partition coherence and timing

```text
outputs/experiments/statistical-synthesis/evaluations/aggregates/partition_timing_results.parquet
```

Columns:

```text
law_name
coarse_partition
fine_partition
rho
tau_coarse
tau_fine
delta_tau
coarse_risk_upper
fine_risk_upper
bound_gain
fine_subset_coarse
theorem_condition
pass
```

## Table 8 — Compatibility, sharpness, safety

```text
outputs/experiments/statistical-synthesis/evaluations/aggregates/compatibility_safety.parquet
```

Columns:

```text
law_name
partition_name
rho
beta
tau
theta_dagger
risk_lower
risk_upper
rho_star
expected_regime
observed_regime
oracle_error
pass
```

## Table 9 — Anytime validity

```text
outputs/experiments/anytime-coverage-stress/evaluations/aggregates/anytime_coverage.parquet
```

Columns:

```text
stress_cell
method_name
K
true_theta
true_mutual_information
rho
beta
delta
independent_streams
ever_violations
violation_rate
clopper_pearson_upper_95
criterion_pass
median_first_certified_n
median_certified_update_fraction
```

Invalid-by-design controls appear in a separately labeled block.

## Table 10 — Sensitivity and utility

```text
outputs/experiments/statistical-synthesis/evaluations/aggregates/rho_utility.parquet
```

Population rows:

```text
analysis_type = POPULATION
law_name
rho
partition_name
metric_name
metric_value
compatibility_state
tau
risk_upper
identified_width
worst_case_upper
absolute_tightening
relative_unresolved_gain
materiality_pass
```

Sequential rows are long-form by practical metric:

```text
analysis_type = SEQUENTIAL
law_name
rho
partition_name = 8-band partition
baseline_partition_name = Endpoint-only partition
metric_name
method_mean
baseline_mean
mean_paired_difference
bootstrap_lower_95
bootstrap_upper_95
holm_adjusted_p
materiality_pass
never_certified_fraction_method
never_certified_fraction_baseline
```

The never-certified columns are populated only where relevant to `Time to first certification`; otherwise they are null.

## Table 11 — Failure boundaries

```text
outputs/experiments/failure-boundary-atlas/evaluations/aggregates/failure_boundaries.parquet
```

Columns:

```text
axis
level
controlled_value_json
rho
beta
tau
risk_upper
operational_state
optimizer_gap
runtime_ms
scientific_interpretation
```

## Table 12 — Computational scaling

```text
outputs/experiments/computational-scaling/evaluations/aggregates/computational_scaling.parquet
```

Columns:

```text
K
population_median_runtime_ms
population_iqr_runtime_ms
outer_median_runtime_ms
outer_iqr_runtime_ms
peak_memory_mib
median_root_iterations
median_outer_nodes
max_oracle_error
```

## Table 13 — Claim registry

```text
outputs/experiments/statistical-synthesis/evaluations/aggregates/claim_registry.parquet
```

Columns:

```text
claim_name
claim
required_experiments
primary_metric
minimum_support_condition
final_state
supporting_table
supporting_figure
scope
forbidden_extrapolation
```

# 20. Required Figures

SVG and PNG filenames are the source basename with:

```text
.svg
.png
```

extensions.

No smoothing, favorable post-selection, seed filtering, or hidden removal of incompatible points is allowed.

## Figure 1 — Partition coherence at fixed sensitivity

Owner:

```text
Statistical Synthesis
```

Source:

```text
outputs/experiments/statistical-synthesis/evaluations/aggregates/figure_partition_coherence.parquet
```

The source combines exact $\rho=0.10$ population outputs from:

* `Population Sensitivity Utility` for:

  ```text
  Timing only: harmful outcomes resolve late
  Terminal only: harmful outcomes remain unresolved
  Timing and terminal: harmful outcomes resolve late
  ```
* `Same Endpoint, Different Timing` for:

  ```text
  Same endpoint with timing information
  ```

Partitions:

```text
Endpoint-only partition
2-band partition
4-band partition
8-band partition
```

Plot:

```text
x = latent risk interval
y = partition K
facet = law
annotation = tau
```

## Figure 2 — Exact timing value

```text
outputs/experiments/strict-timing-gain/evaluations/aggregates/figure_timing_value.parquet
```

```text
x = Delta tau
y = coarse risk upper - fine risk upper
group = semantic timing case
facet = configured rho offset
vertical reference = Delta tau = 0
```

## Figure 3 — Information profile and safety corridor

```text
outputs/experiments/safety-and-intrinsic-impossibility/evaluations/aggregates/figure_information_profile.parquet
```

```text
law = Timing and terminal: harmful outcomes resolve late
K = method.finest_bands
beta = budgets.risk
rho = budgets.information_nats
grid = numerics.information_profile_figure_grid_points
```

Show exact landmarks:

```text
u_dagger
tau
rho
u_beta when in domain
rho_star
exact feasible interval
```

## Figure 4 — Representative anytime certificates

```text
outputs/experiments/anytime-coverage-stress/evaluations/aggregates/figure_anytime_paths.parquet
```

```text
seed indices = [0,1,2,3]
law = Timing and terminal: harmful outcomes resolve late
K = 8
rho = I_true + 0.01
beta = budgets.risk
x = matured event count
y = U_n(rho)
```

Include true $\theta$, $\beta$, evidence-gate region, and state changes.

## Figure 5 — Anytime stress validity

```text
outputs/experiments/anytime-coverage-stress/evaluations/aggregates/figure_anytime_coverage.parquet
```

Show one-sided exact upper confidence limits and references:

```text
confidence.anytime_delta
sequential.coverage.acceptance_upper_limit
```

## Figure 6 — Full rho sensitivity

```text
outputs/experiments/population-sensitivity-utility/evaluations/aggregates/figure_rho_sensitivity.parquet
```

```text
x = rho
y = risk upper
line = partition
facet = utility law
```

Plot all 15 sensitivity values, including exact $\log2$.

Show incompatible points explicitly.

## Figure 7 — Failure-boundary atlas

```text
outputs/experiments/failure-boundary-atlas/evaluations/aggregates/figure_failure_boundaries.parquet
```

One panel per configured axis.

No interpolated heatmap may imply untested configurations.

## Figure 8 — Computational scaling

```text
outputs/experiments/computational-scaling/evaluations/aggregates/figure_computational_scaling.parquet
```

Panels:

```text
population solver runtime vs K
outer projection runtime/node count vs K
```

Use log2 $K$.

Runtime may use a log scale only if every recorded runtime is strictly positive.

# 21. Claim Registry and Mechanical Support Rules

## 21.1 Partition Coherence

Claim:

> Under fixed PIS $\rho$ and a common terminal horizon, deterministic refinement cannot widen the sharp population risk set.

Required:

* all legacy partition-incoherence cells;
* all refinement identities;
* all 54 confirmatory Partition Coherence cells.

Support:

```text
zero PIS nesting violations beyond numerics.identity_atol
all six legacy counterexamples demonstrate non-invariance of the legacy feasible set
```

A valid PIS nesting counterexample yields:

```text
NOT_SUPPORTED
```

## 21.2 Observable Timing Decomposition

Claim:

$$
I(L;J_\Pi)=\tau_\Pi+I(L;R).
$$

Required:

* all decomposition identities;
* same-endpoint timing ablation.

Support requires residual no greater than `numerics.identity_atol`.

## 21.3 Exact Compatibility Floor

Claim:

$$
\rho_{\min}=\tau.
$$

Required:

* minimum-compatibility identities;
* compatibility-floor behavior experiment.

All below/at/above regimes must match.

## 21.4 Sharp Latent-Risk Set

Claim:

> Under the specified binary observation law and PIS budget, the reported population interval is sharp.

Required:

* constructive identity cells;
* all 240 Production Solver vs Independent Oracle cells;
* all 40 Sharpness Against Generic Oracle cells.

Support:

```text
zero state mismatches
max endpoint error <= numerics.identity_atol
```

No finite-sample optimality claim follows.

## 21.5 Strict Timing Value

Claim:

> Under compatibility and interior-upper-root conditions, finer timing strictly improves the upper endpoint iff its conditional outcome information is positive.

Support:

```text
zero-information absolute gain <= numerics.identity_atol
positive-information gain > numerics.identity_atol
profile-difference residual <= numerics.identity_atol
```

No claim that additional bins always strictly help is permitted.

## 21.6 Intrinsic Certification Impossibility

Claim:

> The geometry distinguishes sensitivity-dependent uncertainty from cases in which no compatible information budget can certify the requested beta.

Required:

* safety identities;
* all 40 Safety and Intrinsic Impossibility cells.

Support requires all five deterministic beta regimes and all applicable $\rho^\star$ identities to pass.

## 21.7 Anytime-Valid Local Certificate

Claim:

> Projecting the simultaneous observable-law confidence sequence through the conservative PIS map yields an anytime-valid local upper-risk certificate under the declared assumptions.

Required:

* projection proof check;
* all 30 hand cases;
* twelve coverage stress cells.

Support:

```text
all hand cases pass
all primary TrajCert stress cases satisfy CP acceptance
no anti-conservative optimizer failure
```

Any primary stress failure yields:

```text
NOT_SUPPORTED
```

## 21.8 Practical Synthetic Nonvacuity

Claim:

> On the prespecified synthetic benchmark, the method gives materially nonvacuous upper-risk bounds over predeclared sensitivity regimes.

Required:

```text
all 360 Population Sensitivity Utility cells
```

Qualification follows Section 18.9 exactly.

Support:

```text
number of qualifying laws
>= materiality.population.qualifying_laws
```

Failure:

```text
NULL_RESULT
```

Scope:

```text
synthetic benchmark only
```

## 21.9 Trajectory Operational Gain

Claim:

> On the prespecified sequential synthetic benchmark, 8-band partition improves operational certification relative to the endpoint-only partition in prespecified regimes.

Required:

```text
all 18 Sequential Sensitivity Utility conditions
all 54 Holm-family tests
```

A law qualifies only by the certified-update-fraction rule in Section 18.9.

Support:

```text
qualifying laws >= materiality.sequential.qualifying_laws
```

Partial support:

```text
exactly 1 or 2 laws qualify
```

Null:

```text
0 laws qualify
```

## 21.10 Computational Tractability

Claim:

> Population computation uses O$K$ sufficient-statistic construction plus scalar branch root solving and maintains numerical accuracy over the tested K range.

Required:

* operation-count proof;
* oracle validation;
* all eight scaling cells.

Support:

```text
all population oracle errors <= numerics.identity_atol
all K cells complete
```

Runtime and memory are descriptive.

## 21.11 Local Validity Without Federation

Claim:

> Core statistical validity uses no foreign-client information.

Support requires two machine-readable audits.

### Static dependency audit

Inspect the registered parent DAG for the bound-producing components:

```text
inference/confidence_sequence.py
inference/envelope.py
inference/projection.py
inference/compatibility.py
inference/states.py
```

Allowed scientific input classes are only:

```text
target-stream event/count artifacts
target epoch manifest
target partition manifest
configuration/protocol values
local numerical dependencies
```

A parent scientific artifact carrying a different `client_id` than the target cell is forbidden.

### Runtime input-lineage audit

For every TrajCert local bound artifact, recursively traverse `parent_artifact_keys`.

Every operational parent containing local-unit fields must satisfy exactly:

```text
client_id = target client_id
action_channel_id = target action_channel_id
epoch_id = target epoch_id
```

The lineage must contain no:

```text
foreign_client_ids
foreign_client_statistics
foreign_model_updates
cross_client_aggregate
```

unless such a field is purely provenance text and is not a scientific parent input.

Audit output:

```text
static_dependency_pass
runtime_lineage_pass
foreign_scientific_parent_count
violating_artifact_keys
pass
```

Any foreign scientific input reaching the local bound computation yields:

```text
NOT_SUPPORTED
```

## 21.12 Real-Trajectory Value

Current state:

```text
NOT_TESTED
```

Allowed manuscript statement:

> TrajCert is theoretically and synthetically evaluated for the adjudication-trajectory setting; value on a genuine operational action-to-adjudication ledger remains to be established.

Real operational validation may not be implied.

# 22. Claim-State Semantics

| State                 | Meaning                                                                                   |
| --------------------- | ----------------------------------------------------------------------------------------- |
| `SUPPORTED`           | Every mandatory support condition passes.                                                 |
| `PARTIALLY_SUPPORTED` | Used only where the claim explicitly defines partial support.                             |
| `MECHANISM_ONLY`      | The theorem/mechanism is supported but a required broader empirical layer is unavailable. |
| `CONDITIONAL`         | Support is confined to enumerated tested regimes.                                         |
| `NULL_RESULT`         | Execution is valid but a predeclared empirical effect/materiality condition is not met.   |
| `NOT_SUPPORTED`       | Valid evidence contradicts a mandatory claim criterion.                                   |
| `NOT_TESTED`          | The authoritative plan deliberately contains no valid test.                               |

No claim is removed or hidden because its result is unfavorable.

# 23. Evidence Completion and Reproducibility Closure

There is one scientific execution regime.

No second execution phase is required.

A registry cell reaches `COMPLETED` when its required artifacts and completion marker satisfy Sections 13–18.

An experiment reaches `COMPLETED` when all executable cells and required experiment-level aggregates/statistics/source data validate.

`Statistical Synthesis` is executed after all required upstream experiments complete.

It may complete when valid evidence includes:

```text
scientific nulls
wide intervals
model incompatibility
intrinsic impossibility
theorem falsification
unfavorable materiality results
```

Those outcomes change claim states but are not technical failures.

`Statistical Synthesis` is blocked by:

```text
missing mandatory evidence
FAILED mandatory cell
INVALID mandatory cell
stale mandatory artifact
corrupt mandatory artifact
schema failure
dependency/provenance failure
missing multiplicity-family member
anti-conservative numerical failure
failed mandatory hostile-review check
```

On successful synthesis, construct:

```text
outputs/experiments/statistical-synthesis/provenance/dependencies/evidence_manifest.json
```

The evidence manifest contains:

```text
roadmap digest
configuration digest
source commit
dirty-tree flag
requirements.lock digest
container image digest
environment digest
registry plan digest
dataset/law/partition manifest digests
seed-set digests
producer component digests
all completed semantic-cell keys
all completion-marker digests
cross-experiment aggregate digests
claim-registry digest
hostile-review record digest
```

The evidence manifest is a reproducibility summary, not a cache key.

If any material dependency later changes, normal Section 14 dependency invalidation applies only to affected artifacts and descendants.

After affected artifacts are recomputed, Statistical Synthesis and the evidence manifest are regenerated.

`report` is permitted only when Statistical Synthesis is `COMPLETED` and its current evidence manifest validates against active artifacts.

# 24. Reproducibility and Manuscript Export

A complete reproduction requires:

```text
source commit
requirements.lock
container image digest
this roadmap
configs/trajcert.yaml
deterministic synthetic generator
deterministic seed derivation
registered producer-component dependency map
public CLI
```

Every manuscript-bearing number must trace:

```text
results artifact
-> authoritative source data under outputs/
-> metric/statistical artifact
-> semantic experiment cell
-> dependency fingerprint
-> parent artifact identities/digests
-> scientific dependency/configuration fragments
-> law/partition/dataset checksum
-> seed manifest when stochastic
-> producer implementation component digest
-> relevant environment dependency digest
-> source commit provenance
-> project evidence manifest
```

Hashes provide integrity and lineage only.

Semantic coordinates identify the scientific experiment.

Dependency fingerprints determine reuse compatibility.

## 24.1 Normative canonicalization reference

Digest-bearing JSON uses RFC 8785 JCS semantics because that specification explicitly defines canonical JSON for repeatable cryptographic hashing, including deterministic object-property ordering and UTF-8 generation.

# 25. Failure Semantics

| Class                                  | Meaning                                                                                                                               | Execution/evidence consequence                                                       |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Technical failure                      | crash, arithmetic exception, corrupt artifact, checksum/serialization failure, unexpected empty CS region, or unresolved prerequisite | `FAILED`; no scientific conclusion; recover from nearest valid dependency/checkpoint |
| Stale/dependency-incompatible artifact | previously valid artifact no longer matches material dependency identity                                                              | not scientific evidence; remove from active use and recompute affected descendants   |
| Data/validation failure                | invalid probabilities/partition, duplicate identity, invalid ledger/manifests, unrecoverable seed/dependency mismatch                 | `INVALID`; affected downstream evidence blocked                                      |
| Scientific falsification               | valid evidence contradicts theorem/mandatory relation under its conditions                                                            | execution remains `COMPLETED`; affected claim `NOT_SUPPORTED`                        |
| Scientific null/boundary               | wide interval, no gain, compatible-but-uncertified, predicted intrinsic impossibility, boundary result                                | completed scientific evidence                                                        |
| Planned nonapplicability               | registry intentionally contains no executable cells                                                                                   | zero-cell experiments remain nonapplicable                                           |

`TECHNICAL_FAIL` is an internal result code within a `FAILED` execution, not a scientific state.

`INSUFFICIENT_EVIDENCE` is a valid scientific monitoring state arising only from evidence-count insufficiency after data/technical validity has passed.

# 26. Test Contract

Required deterministic/unit coverage includes:

* entropy and exact boundary extensions;
* empty bands;
* information profile and derivatives;
* population root branches;
* root bracket and residual rules;
* `c=0`;
* `A+G=0`;
* compatibility/singleton cases;
* partition maps;
* semantic identity;
* RFC-8785 canonicalization test vectors;
* numeric path rendering;
* seed derivation and namespace construction;
* dependency-fingerprint construction;
* component-digest isolation;
* balanced-prefix construction;
* Hamilton apportionment;
* CS endpoint outward inversion;
* running intersections;
* state precedence;
* finite-sample compatibility lower bound;
* intrinsic-impossibility lower bound;
* Clopper-Pearson edge cases;
* bootstrap deterministic resampling;
* sign-flip statistic;
* Holm ordering/ties;
* deterministic quantiles;
* completion/dependency/provenance validation.

Required property checks, with deterministic Hypothesis settings:

* generated laws stay on the simplex;
* $$
  \mathcal S(u)\ge\tau-
  \texttt{numerics.deterministic＿identity＿tolerance};
$$
* convexity for nondegenerate laws;
* $u^\dagger\in[0,c]$;
* refinement does not reduce $\mathcal S$;
* PIS feasible set is an interval;
* independent oracle agrees on random low-dimensional cases;
* cache/no-cache calculations agree;
* semantic identity is serialization-order invariant;
* semantic identity is unchanged by overwrite;
* unrelated file changes leave unaffected dependency fingerprints unchanged;
* changing a registered material parent changes descendant fingerprint;
* changing one parent does not change an unrelated sibling fingerprint.

Hypothesis-generated cases are test evidence only.

Integration/regression coverage verifies:

* Scientific and Data Inventory through at least one population cell;
* idempotent rerun performs no scientific recomputation;
* one failed later cell leaves earlier/sibling valid cells reusable;
* overwrite recomputes only selected roots and true descendants;
* content-identical parent regeneration preserves descendants;
* scientifically changed parent invalidates all and only true descendants;
* partial output is never active evidence;
* interrupted Monte Carlo recovery;
* deterministic checkpoint recovery;
* checkpoint rejection under material mismatch;
* checkpoint acceptance across unrelated source changes;
* global plan changes elsewhere do not invalidate unchanged cell rows;
* rendering-only changes do not invalidate scientific source data;
* completion marker is written last;
* evidence manifest rejects missing/stale evidence;
* report reads only verified source data;
* `results/` excludes non-evidence artifacts;
* every discovered scientific/numerical bug receives an independently justified regression test.

# 27. Hostile Reviewer Verification

Statistical Synthesis must produce machine-readable evidence pointers verifying:

* **Target/scope:** binary estimand justification; common terminal horizon across refinement; no post-outcome partition choice; $\rho$ described as sensitivity assumption; $\beta$ only in its configured benchmark role; absence of real operational validation stated; prohibited novelty/privacy/federation claims absent.
* **Comparators:** assumptions explicit; generic oracle structurally independent; observation access fair; paired stochastic streams shared; no comparator receives hidden extra information.
* **Sequential/statistical validity:** deployed sequential construction is time-uniform; independent stream is the Monte Carlo unit; Monte Carlo counts/tests/multiplicity/materiality are prespecified before claim evaluation; incompatible cells remain visible; undefined values are null; failed seeds are retained.
* **Identity/recovery:** no duplicate active semantic result; each reusable artifact has one producer; partial outputs never become active evidence; checkpoints never cross dependency incompatibility; stale descendants are removed; caches never become evidence.
* **Evidence lineage:** every table/figure has stable machine-readable source data; every manuscript claim has a registry state; exports use completed verified evidence only; `results/` contains no caches/debug/failures/invalid/stale/partial/checkpoint artifacts.
* **Local validity:** static dependency and runtime lineage audits in Section 21.11 pass.
* **Execution completeness:** all 1,423 planned registry cells are accounted for as executable-completed, planned-invalid, or zero-cell nonapplicable according to their contracts; no mandatory executable cell is missing.

Any failed mandatory check blocks Statistical Synthesis.

# 28. Normal Operator Workflow

The operator workflow is registry-driven:

```text
trajcert doctor
trajcert preprocess
trajcert smoke
trajcert plan

trajcert run "Scientific and Data Inventory"

trajcert run <each remaining experiment with nonzero cells,
             in authoritative registry dependency order>

trajcert run "Statistical Synthesis"

trajcert doctor
trajcert report
```

`Statistical Synthesis` is run after all other required nonzero experiment families.

Every executing command automatically performs:

```text
validate existing artifacts
-> reuse compatible artifacts
-> invalidate/remove stale descendants
-> recover from nearest valid checkpoint/artifact
-> recompute only necessary work
-> continue
```

The operator does not restart the project after a later failure.

Reissuing the failed or downstream experiment command resumes from the nearest valid artifact.

Successful earlier and unrelated experiment results remain active unless one of their material dependencies changed.

`Real-Trajectory Validation` and `Foreign-Information Negative Control` have no executable cells.

At no point does the operator choose:

```text
seed
law
partition
method
baseline
rho
beta
delta
execution group
cache mode
checkpoint mode
scientific configuration
```

The operator selects only an experiment family.

The authoritative registry and configuration determine all cells and dependencies.
