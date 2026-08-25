from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite, log2

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import (
    InvariantViolationError,
    RootSolveError,
)
from trajcert.math.compatibility import (
    CompatibilityAssessment,
    assess_compatibility,
)
from trajcert.math.information import information_profile
from trajcert.types import (
    CompatibilityRegime,
    HiddenMassInterval,
    InformationNats,
    IterationCount,
    Mass,
    RootBracket,
    RootBranch,
    RootStatus,
    SensitivityBudget,
    ToleranceValue,
)


@dataclass(frozen=True, slots=True)
class HiddenMassSolveResult:
    compatibility: CompatibilityAssessment
    interval: HiddenMassInterval | None
    lower_root: RootBracket | None
    upper_root: RootBracket | None


def solve_hidden_mass_interval(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
) -> HiddenMassSolveResult:
    root_tolerance = _positive_tolerance(
        root_atol,
        "root_atol",
    )
    identity_tolerance = _positive_tolerance(
        identity_atol,
        "identity_atol",
    )

    compatibility = assess_compatibility(
        summary,
        sensitivity_budget,
    )

    rho = float(sensitivity_budget)
    unresolved = float(summary.unresolved_mass)

    if compatibility.regime is CompatibilityRegime.MODEL_INCOMPATIBLE:
        return HiddenMassSolveResult(
            compatibility=compatibility,
            interval=None,
            lower_root=None,
            upper_root=None,
        )

    if compatibility.regime is CompatibilityRegime.NO_RESOLVED_MASS:
        return HiddenMassSolveResult(
            compatibility=compatibility,
            interval=HiddenMassInterval(
                Mass(0.0),
                Mass(unresolved),
            ),
            lower_root=None,
            upper_root=None,
        )

    minimum = compatibility.minimum_information_point

    if minimum is None:
        raise InvariantViolationError(
            "compatible nondegenerate case is missing its information minimum"
        )

    u_dagger = float(minimum.hidden_terminal_harmful_mass)

    if compatibility.regime is CompatibilityRegime.NO_UNRESOLVED_MASS:
        lower = _exact_root(
            RootBranch.LOWER,
            0.0,
            summary,
            rho,
            RootStatus.EXACT_BOUNDARY,
        )
        upper = _exact_root(
            RootBranch.UPPER,
            0.0,
            summary,
            rho,
            RootStatus.EXACT_BOUNDARY,
        )

        return HiddenMassSolveResult(
            compatibility=compatibility,
            interval=HiddenMassInterval(
                Mass(0.0),
                Mass(0.0),
            ),
            lower_root=lower,
            upper_root=upper,
        )

    if compatibility.regime is CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON:
        lower = _exact_root(
            RootBranch.LOWER,
            u_dagger,
            summary,
            rho,
            RootStatus.MINIMUM_SINGLETON,
        )
        upper = _exact_root(
            RootBranch.UPPER,
            u_dagger,
            summary,
            rho,
            RootStatus.MINIMUM_SINGLETON,
        )

        _require_residual(
            lower,
            identity_tolerance,
        )
        _require_residual(
            upper,
            identity_tolerance,
        )

        return HiddenMassSolveResult(
            compatibility=compatibility,
            interval=HiddenMassInterval(
                Mass(u_dagger),
                Mass(u_dagger),
            ),
            lower_root=lower,
            upper_root=upper,
        )

    lower_root = _solve_lower_branch(
        summary=summary,
        rho=rho,
        u_dagger=u_dagger,
        root_atol=root_tolerance,
        identity_atol=identity_tolerance,
    )
    upper_root = _solve_upper_branch(
        summary=summary,
        rho=rho,
        u_dagger=u_dagger,
        unresolved=unresolved,
        root_atol=root_tolerance,
        identity_atol=identity_tolerance,
    )

    return HiddenMassSolveResult(
        compatibility=compatibility,
        interval=HiddenMassInterval(
            lower_root.root,
            upper_root.root,
        ),
        lower_root=lower_root,
        upper_root=upper_root,
    )


def _solve_lower_branch(
    summary: ObservableSummary,
    rho: float,
    u_dagger: float,
    root_atol: float,
    identity_atol: float,
) -> RootBracket:
    boundary_value = _profile_residual(
        summary,
        0.0,
        rho,
    )

    if boundary_value <= 0.0:
        return _exact_root(
            RootBranch.LOWER,
            0.0,
            summary,
            rho,
            RootStatus.EXACT_BOUNDARY,
        )

    minimum_value = _profile_residual(
        summary,
        u_dagger,
        rho,
    )

    if minimum_value >= 0.0:
        raise RootSolveError("lower branch does not contain a strict sign-changing root")

    return _bisect(
        summary=summary,
        rho=rho,
        branch=RootBranch.LOWER,
        lower=0.0,
        upper=u_dagger,
        lower_residual=boundary_value,
        upper_residual=minimum_value,
        root_atol=root_atol,
        identity_atol=identity_atol,
    )


def _solve_upper_branch(
    summary: ObservableSummary,
    rho: float,
    u_dagger: float,
    unresolved: float,
    root_atol: float,
    identity_atol: float,
) -> RootBracket:
    boundary_value = _profile_residual(
        summary,
        unresolved,
        rho,
    )

    if boundary_value <= 0.0:
        return _exact_root(
            RootBranch.UPPER,
            unresolved,
            summary,
            rho,
            RootStatus.EXACT_BOUNDARY,
        )

    minimum_value = _profile_residual(
        summary,
        u_dagger,
        rho,
    )

    if minimum_value >= 0.0:
        raise RootSolveError("upper branch does not contain a strict sign-changing root")

    return _bisect(
        summary=summary,
        rho=rho,
        branch=RootBranch.UPPER,
        lower=u_dagger,
        upper=unresolved,
        lower_residual=minimum_value,
        upper_residual=boundary_value,
        root_atol=root_atol,
        identity_atol=identity_atol,
    )


def _bisect(
    *,
    summary: ObservableSummary,
    rho: float,
    branch: RootBranch,
    lower: float,
    upper: float,
    lower_residual: float,
    upper_residual: float,
    root_atol: float,
    identity_atol: float,
) -> RootBracket:
    _validate_initial_signs(
        branch,
        lower_residual,
        upper_residual,
    )

    initial_width = upper - lower

    iteration_cap = _iteration_cap(
        initial_width,
        root_atol,
    )

    iterations = 0

    while upper - lower > root_atol:
        if iterations >= iteration_cap:
            raise RootSolveError("derived bisection iteration cap exhausted")

        midpoint = (lower + upper) / 2.0

        residual = _profile_residual(
            summary,
            midpoint,
            rho,
        )

        if residual == 0.0:
            lower = midpoint
            upper = midpoint
            break

        if branch is RootBranch.LOWER:
            if residual > 0.0:
                lower = midpoint
                lower_residual = residual
            else:
                upper = midpoint
                upper_residual = residual
        else:
            if residual < 0.0:
                lower = midpoint
                lower_residual = residual
            else:
                upper = midpoint
                upper_residual = residual

        iterations += 1

    _validate_final_signs(
        branch,
        lower_residual,
        upper_residual,
    )

    root = (lower + upper) / 2.0

    residual = abs(
        _profile_residual(
            summary,
            root,
            rho,
        )
    )

    result = RootBracket(
        branch=branch,
        status=RootStatus.BISECTION,
        lower=Mass(lower),
        upper=Mass(upper),
        width=Mass(upper - lower),
        root=Mass(root),
        residual=InformationNats(residual),
        iterations=IterationCount(iterations),
    )

    if float(result.width) > root_atol:
        raise RootSolveError("root bracket exceeds root_atol")

    _require_residual(
        result,
        identity_atol,
    )

    return result


def _profile_residual(
    summary: ObservableSummary,
    hidden_mass: float,
    rho: float,
) -> float:
    return (
        float(
            information_profile(
                summary,
                Mass(hidden_mass),
            )
        )
        - rho
    )


def _exact_root(
    branch: RootBranch,
    hidden_mass: float,
    summary: ObservableSummary,
    rho: float,
    status: RootStatus,
) -> RootBracket:
    residual = abs(
        _profile_residual(
            summary,
            hidden_mass,
            rho,
        )
    )

    return RootBracket(
        branch=branch,
        status=status,
        lower=Mass(hidden_mass),
        upper=Mass(hidden_mass),
        width=Mass(0.0),
        root=Mass(hidden_mass),
        residual=InformationNats(residual),
        iterations=IterationCount(0),
    )


def _require_residual(
    root: RootBracket,
    identity_atol: float,
) -> None:
    if float(root.residual) > identity_atol:
        raise RootSolveError("returned root residual exceeds identity_atol")


def _iteration_cap(
    initial_width: float,
    root_atol: float,
) -> int:
    if initial_width <= 0.0:
        return 0

    if initial_width <= root_atol:
        return 2

    return ceil(log2(initial_width / root_atol)) + 2


def _validate_initial_signs(
    branch: RootBranch,
    lower: float,
    upper: float,
) -> None:
    if branch is RootBranch.LOWER:
        if lower <= 0.0 or upper >= 0.0:
            raise RootSolveError("lower branch initial bracket is not sign-valid")
    elif lower >= 0.0 or upper <= 0.0:
        raise RootSolveError("upper branch initial bracket is not sign-valid")


def _validate_final_signs(
    branch: RootBranch,
    lower: float,
    upper: float,
) -> None:
    if lower == 0.0 or upper == 0.0:
        return

    _validate_initial_signs(
        branch,
        lower,
        upper,
    )


def _positive_tolerance(
    value: ToleranceValue,
    name: str,
) -> float:
    numeric = float(value)

    if not isfinite(numeric) or numeric <= 0.0:
        raise RootSolveError(f"{name} must be finite and positive")

    return numeric
