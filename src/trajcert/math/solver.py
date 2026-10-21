from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isclose, isfinite, ldexp, log, log2

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvariantViolationError, RootSolveError, TrajCertError
from trajcert.math.compatibility import CompatibilityAssessment, assess_compatibility
from trajcert.math.information import (
    information_profile_residual,
    resolved_timing_entropy,
)
from trajcert.types import (
    CompatibilityRegime,
    EntropyValue,
    HiddenMassInterval,
    InformationResidual,
    IterationCount,
    Mass,
    RootBracket,
    RootBranch,
    RootStatus,
    SensitivityBudget,
    ToleranceName,
    ToleranceValue,
)


@dataclass(frozen=True, slots=True)
class _SolveContext:
    summary: ObservableSummary
    rho: SensitivityBudget
    resolved_entropy: EntropyValue
    root_atol: ToleranceValue
    identity_atol: ToleranceValue


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
    root_tolerance = _positive_tolerance(root_atol, ToleranceName.ROOT_ABSOLUTE)
    identity_tolerance = _positive_tolerance(identity_atol, ToleranceName.IDENTITY_ABSOLUTE)
    timing_entropy = resolved_timing_entropy(summary) if summary.resolved_mass > 0.0 else None
    compatibility = assess_compatibility(summary, sensitivity_budget, timing_entropy)
    rho = sensitivity_budget
    unresolved = summary.unresolved_mass
    if compatibility.regime is CompatibilityRegime.MODEL_INCOMPATIBLE:
        return HiddenMassSolveResult(
            compatibility=compatibility, interval=None, lower_root=None, upper_root=None
        )
    if compatibility.regime is CompatibilityRegime.NO_RESOLVED_MASS:
        return HiddenMassSolveResult(
            compatibility=compatibility,
            interval=HiddenMassInterval(lower=0.0, upper=unresolved),
            lower_root=None,
            upper_root=None,
        )
    minimum = compatibility.minimum_information_point
    if minimum is None:
        raise InvariantViolationError(
            "compatible nondegenerate case is missing its information minimum"
        )
    u_dagger = minimum.hidden_terminal_harmful_mass
    context = _SolveContext(
        summary=summary,
        rho=rho,
        resolved_entropy=(
            resolved_timing_entropy(summary) if timing_entropy is None else timing_entropy
        ),
        root_atol=root_tolerance,
        identity_atol=identity_tolerance,
    )
    if compatibility.regime is CompatibilityRegime.NO_UNRESOLVED_MASS:
        lower = _exact_root(
            context=context,
            branch=RootBranch.LOWER,
            hidden_mass=0.0,
            status=RootStatus.EXACT_BOUNDARY,
        )
        upper = _exact_root(
            context=context,
            branch=RootBranch.UPPER,
            hidden_mass=0.0,
            status=RootStatus.EXACT_BOUNDARY,
        )
        return HiddenMassSolveResult(
            compatibility=compatibility,
            interval=HiddenMassInterval(lower=0.0, upper=0.0),
            lower_root=lower,
            upper_root=upper,
        )
    if _is_minimum_singleton(compatibility.regime, context, u_dagger):
        lower = _exact_root(
            context=context,
            branch=RootBranch.LOWER,
            hidden_mass=u_dagger,
            status=RootStatus.MINIMUM_SINGLETON,
        )
        upper = _exact_root(
            context=context,
            branch=RootBranch.UPPER,
            hidden_mass=u_dagger,
            status=RootStatus.MINIMUM_SINGLETON,
        )
        _require_residual(lower, identity_tolerance)
        _require_residual(upper, identity_tolerance)
        return HiddenMassSolveResult(
            compatibility=compatibility,
            interval=HiddenMassInterval(lower=u_dagger, upper=u_dagger),
            lower_root=lower,
            upper_root=upper,
        )
    lower_root = _solve_lower_branch(context=context, u_dagger=u_dagger)
    upper_root = _solve_upper_branch(context=context, u_dagger=u_dagger, unresolved=unresolved)
    return HiddenMassSolveResult(
        compatibility=compatibility,
        interval=HiddenMassInterval(lower=lower_root.root, upper=upper_root.root),
        lower_root=lower_root,
        upper_root=upper_root,
    )


def _is_minimum_singleton(
    regime: CompatibilityRegime, context: _SolveContext, u_dagger: Mass
) -> bool:
    if regime is CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON:
        return True
    residual = _profile_residual(context, u_dagger)
    return 0.0 <= residual <= context.identity_atol


def _solve_lower_branch(*, context: _SolveContext, u_dagger: Mass) -> RootBracket:
    boundary_value = _profile_residual(context, 0.0)
    if boundary_value <= 0.0:
        return _exact_root(
            context=context,
            branch=RootBranch.LOWER,
            hidden_mass=0.0,
            status=RootStatus.EXACT_BOUNDARY,
        )
    minimum_value = _profile_residual(context, u_dagger)
    if minimum_value >= 0.0:
        raise RootSolveError("lower branch does not contain a strict sign-changing root")
    return _bisect(
        context=context,
        branch=RootBranch.LOWER,
        lower=0.0,
        upper=u_dagger,
        lower_residual=boundary_value,
        upper_residual=minimum_value,
    )


def _solve_upper_branch(*, context: _SolveContext, u_dagger: Mass, unresolved: Mass) -> RootBracket:
    boundary_value = _profile_residual(context, unresolved)
    if boundary_value <= 0.0:
        return _exact_root(
            context=context,
            branch=RootBranch.UPPER,
            hidden_mass=unresolved,
            status=RootStatus.EXACT_BOUNDARY,
        )
    minimum_value = _profile_residual(context, u_dagger)
    if minimum_value >= 0.0:
        raise RootSolveError("upper branch does not contain a strict sign-changing root")
    return _bisect(
        context=context,
        branch=RootBranch.UPPER,
        lower=u_dagger,
        upper=unresolved,
        lower_residual=minimum_value,
        upper_residual=boundary_value,
    )


def _bisect(
    *,
    context: _SolveContext,
    branch: RootBranch,
    lower: Mass,
    upper: Mass,
    lower_residual: InformationResidual,
    upper_residual: InformationResidual,
) -> RootBracket:
    validate_initial_signs(branch, lower_residual, upper_residual)
    initial_width = upper - lower
    iteration_cap = compute_iteration_cap(initial_width, context.root_atol)
    iterations = 0
    bracket = _residual_bracket(context, branch, lower, upper)
    while upper - lower > context.root_atol:
        if iterations >= iteration_cap:
            raise RootSolveError("derived bisection iteration cap exhausted")
        midpoint = (lower + upper) / 2.0
        residual = _bracketed_residual(context, midpoint, bracket)
        if isclose(residual, 0.0, rel_tol=0.0, abs_tol=0.0):
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
        elif residual < 0.0:
            lower = midpoint
            lower_residual = residual
        else:
            upper = midpoint
            upper_residual = residual
        iterations += 1
    validate_final_signs(branch, lower_residual, upper_residual)
    root = (lower + upper) / 2.0
    residual = abs(_profile_residual(context, root))
    result = RootBracket(
        branch=branch,
        status=RootStatus.BISECTION,
        lower=lower,
        upper=upper,
        width=upper - lower,
        root=root,
        residual=residual,
        iterations=iterations,
    )
    if result.width > context.root_atol:
        raise RootSolveError("root bracket exceeds root_atol")
    _require_residual(result, context.identity_atol)
    return result


@dataclass(frozen=True, slots=True)
class _ResidualBracket:
    below: Mass
    above: Mass
    below_residual: InformationResidual


def _bracketed_residual(
    context: _SolveContext, midpoint: Mass, bracket: _ResidualBracket | None
) -> InformationResidual:
    if bracket is not None:
        if midpoint <= bracket.below:
            return bracket.below_residual
        if midpoint >= bracket.above:
            return -bracket.below_residual
    return _profile_residual(context, midpoint)


def _residual_bracket(
    context: _SolveContext, branch: RootBranch, lower: Mass, upper: Mass
) -> _ResidualBracket | None:
    below_residual = 1.0 if branch is RootBranch.LOWER else -1.0
    try:
        estimate = _residual_root_estimate(context, lower, upper, below_residual)
        margin = ldexp(1.0, -43)
        width = ldexp(upper - lower, -40)
        for _ in range(8):
            below = estimate - width
            above = estimate + width
            if not lower < below < above < upper:
                return None
            below_value = _profile_residual(context, below) * below_residual
            above_value = _profile_residual(context, above) * below_residual
            if below_value > margin and above_value < -margin:
                return _ResidualBracket(below=below, above=above, below_residual=below_residual)
            width *= 16.0
    except (ArithmeticError, ValueError, TrajCertError):
        return None
    return None


def _residual_root_estimate(
    context: _SolveContext, lower: Mass, upper: Mass, below_residual: InformationResidual
) -> Mass:
    harmful = context.summary.resolved_harmful_mass
    unresolved = context.summary.unresolved_mass
    estimate = (lower + upper) / 2.0
    resolution = ldexp(upper - lower, -44)
    for _ in range(64):
        value = _profile_residual(context, estimate) * below_residual
        if value > 0.0:
            lower = estimate
        else:
            upper = estimate
        theta = harmful + estimate
        slope = (
            log((1.0 - theta) / theta) - log((unresolved - estimate) / estimate)
        ) * below_residual
        step = estimate - value / slope if slope != 0.0 else estimate
        candidate = step if lower < step < upper else (lower + upper) / 2.0
        if abs(candidate - estimate) <= resolution:
            return candidate
        estimate = candidate
    return estimate


def _profile_residual(context: _SolveContext, hidden_mass: Mass) -> InformationResidual:
    return information_profile_residual(
        context.summary, hidden_mass, context.resolved_entropy, context.rho
    )


def _exact_root(
    *,
    context: _SolveContext,
    branch: RootBranch,
    hidden_mass: Mass,
    status: RootStatus,
) -> RootBracket:
    residual = abs(_profile_residual(context, hidden_mass))
    return RootBracket(
        branch=branch,
        status=status,
        lower=hidden_mass,
        upper=hidden_mass,
        width=0.0,
        root=hidden_mass,
        residual=residual,
        iterations=0,
    )


def _require_residual(root: RootBracket, identity_atol: ToleranceValue) -> None:
    if root.residual > identity_atol:
        raise RootSolveError("returned root residual exceeds identity_atol")


def compute_iteration_cap(initial_width: Mass, root_atol: ToleranceValue) -> IterationCount:
    if initial_width <= 0.0:
        return 0
    if initial_width <= root_atol:
        return 2
    return ceil(log2(initial_width / root_atol)) + 2


def validate_initial_signs(
    branch: RootBranch, lower: InformationResidual, upper: InformationResidual
) -> None:
    if branch is RootBranch.LOWER:
        if lower <= 0.0 or upper >= 0.0:
            raise RootSolveError("lower branch initial bracket is not sign-valid")
    elif lower >= 0.0 or upper <= 0.0:
        raise RootSolveError("upper branch initial bracket is not sign-valid")


def validate_final_signs(
    branch: RootBranch, lower: InformationResidual, upper: InformationResidual
) -> None:
    if not lower or not upper:
        return
    validate_initial_signs(branch, lower, upper)


def _positive_tolerance(value: ToleranceValue, name: ToleranceName) -> ToleranceValue:
    if not isfinite(value) or value <= 0.0:
        raise RootSolveError(f"{name} must be finite and positive")
    return value
