from dataclasses import dataclass

from trajcert.domain.enums import EvidenceClass

FRAMEWORK_NAME = (
    "TrajCert — Trajectory-Aware Partial-Identification and Sensitivity-Certification Framework"
)
RESEARCH_OBJECT = "Latent Operational Error Risk"
VERIFICATION_SETTING = (
    "Delayed, selective/outcome-dependent, and potentially unresolved outcome verification"
)
THEORETICAL_PRINCIPLE = "Path-Information Sensitivity (PIS)"
AUTHORITATIVE_ROADMAP_PATH = "docs/TrajCert_Roadmap.md"
LEGACY_COMPARATOR_NAME = "Legacy bandwise odds-ratio sensitivity"
RESEARCH_QUESTIONS = (
    "Does one fixed path-information sensitivity budget retain its meaning under deterministic "
    "trajectory coarsening and generate nested sharp risk sets?",
    "Is resolved timing information identifiable, and when does finer timing strictly improve "
    "the upper risk bound?",
    "Does the one-dimensional information profile generate the exact compatible latent-risk set?",
    "Can the method distinguish model contradiction, sensitivity-driven non-certification, "
    "and intrinsic impossibility?",
    "Does projection of a simultaneous observable-law confidence sequence through the "
    "conservative sharp-map envelope provide the declared time-uniform upper-risk guarantee?",
    "Over a predeclared rho domain, when is the certificate informative, incompatible, "
    "or practically vacuous?",
    "If a future eligible action/adjudication ledger exists, does real resolved timing "
    "materially improve certification?",
    "Does local validity remain independent of foreign-client information?",
)

PROHIBITED_CLAIM_TERMS = frozenset(
    {
        "active querying/abstention/selective acting",
        "active-adjudication optimality",
        "callback/repeated-attempt data",
        "constrained-device deployment feasibility",
        "continuous-time or unrestricted serial-drift validity",
        "confidence sequences/e-processes",
        "covariate-conditional validity",
        "data processing",
        "delayed-outcome inference generally",
        "detector evasion",
        "detector-training superiority",
        "entropy/divergence sensitivity generally",
        "finite-sample minimax optimality",
        "falsification/breakdown frontiers generally",
        "federated evidence borrowing",
        "malicious adjudicators/clients",
        "mutual information",
        "ood/zero-day superiority",
        "outcome-dependent timing as missing-data information",
        "partial identification",
        "poisoning/byzantine robustness",
        "privacy protection",
        "privacy leakage",
        "real-trajectory validation",
        "secure aggregation",
        "sharp bounds generally",
        "tampering",
        "universal odds-ratio-to-rho conversion",
        "universal rho calibration",
    }
)


@dataclass(frozen=True, slots=True)
class ClaimText:
    value: str


@dataclass(frozen=True, slots=True)
class ClaimScopeGuard:
    def validate(self, claim_text: ClaimText) -> None:
        normalized = claim_text.value.casefold()
        violations = tuple(term for term in PROHIBITED_CLAIM_TERMS if term in normalized)
        if violations:
            raise ValueError(f"claim exceeds TrajCert scope: {', '.join(sorted(violations))}")

    def validate_evidence_class(self, evidence_class: EvidenceClass) -> None:
        if evidence_class is EvidenceClass.EXPLORATORY:
            raise ValueError("exploratory evidence cannot be promoted to confirmatory evidence")
