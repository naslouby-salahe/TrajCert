from dataclasses import dataclass

FRAMEWORK_NAME = (
    "TrajCert — Trajectory-Aware Partial-Identification and Sensitivity-Certification Framework"
)
RESEARCH_OBJECT = "Latent Operational Error Risk"
VERIFICATION_SETTING = (
    "Delayed, selective/outcome-dependent, and potentially unresolved outcome verification"
)
THEORETICAL_PRINCIPLE = "Path-Information Sensitivity (PIS)"

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
class ClaimScopeGuard:
    def validate(self, claim_text: str) -> None:
        normalized = claim_text.casefold()
        violations = tuple(term for term in PROHIBITED_CLAIM_TERMS if term in normalized)
        if violations:
            raise ValueError(f"claim exceeds TrajCert scope: {', '.join(sorted(violations))}")

    def validate_evidence_class(self, evidence_class: str) -> None:
        if evidence_class == "EXPLORATORY":
            raise ValueError("exploratory evidence cannot be promoted to confirmatory evidence")
