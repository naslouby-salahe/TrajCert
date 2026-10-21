import json
from fractions import Fraction
from pathlib import Path
from math import nextafter, inf
from mpmath import mp
from flint import ctx
from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH, TESTS_CONFIG_OVERRIDES_PATH
from trajcert.math.enclosure import sum_lower, sum_upper
from trajcert.inference.envelope import singleton_summary_envelope
from trajcert.inference.projection import project_upper_risk
from trajcert.inference.confidence import raw_confidence_region
from tests.unit.conftest import summary, categorical_state

mp.dps = 110
cfg = TrajCertConfig.from_yaml_with_overrides(PRODUCTION_CONFIG_PATH, TESTS_CONFIG_OVERRIDES_PATH)
active_config.set(cfg)


def h(p):
    return mp.mpf(0) if p == 0 or p == 1 else -p * mp.log(p) - (1 - p) * mp.log1p(-p)


def endpoint(a, g, c, rho, t):
    if a + g == 0:
        return mp.mpf(1)
    if c == 0:
        return a

    def f(u):
        return h(a + u) - t - c * h(u / c)

    if f(c) <= rho:
        return a + c
    lo = a * c / (a + g)
    hi = c
    for _ in range(370):
        mid = (lo + hi) / 2
        if f(mid) > rho:
            hi = mid
        else:
            lo = mid
    return a + (lo + hi) / 2


cases = []
for af in (0.0, 2**-40, 0.0625, 0.125, 0.5, 0.75):
    for gf in (0.0, 0.0625, 0.25, 0.625):
        if af + gf > 1:
            continue
        cf = 1 - af - gf
        for rho in (0.0, 2**-40, 0.002, 0.1, 1.0):
            env = singleton_summary_envelope(summary([af], [gf], cf))
            result = project_upper_risk(env, rho, 1e-12, 1e-10, 1e-12, 128, 1e-6, 2)
            a, g, c, r = map(mp.mpf, (af, gf, cf, rho))
            t = mp.mpf(0) if a + g == 0 else (a + g) * h(a / (a + g))
            original = endpoint(a, g, c, r, t)
            relaxed = endpoint(a, g, c, r, mp.mpf(env.resolved_entropy.upper))
            assert mp.mpf(result.proven_upper) >= original, (af, gf, cf, rho, "original")
            assert mp.mpf(result.proven_upper) >= relaxed, (af, gf, cf, rho, "relaxed")
            if result.feasible_incumbent is not None:
                assert mp.mpf(result.feasible_incumbent) <= original
            cases.append(
                {
                    "a": af,
                    "g": gf,
                    "c": cf,
                    "rho": rho,
                    "upper": result.proven_upper,
                    "reference": str(original),
                    "relaxed_reference": str(relaxed),
                    "incumbent": result.feasible_incumbent,
                }
            )
for case_index in range(1500):
    vals = [
        (((case_index + 1) * (column + 17) * 104729) % 2147483647) / 1073741824 - 1
        for column in range(1 + case_index % 19)
    ] + [nextafter(0.0, inf)]
    exact = sum(map(Fraction, vals), Fraction())
    assert Fraction(sum_lower(vals)) <= exact <= Fraction(sum_upper(vals))
for vals in (
    [nextafter(0.0, inf)] * 3,
    [1.0, -nextafter(1.0, 0.0)],
    [0.01, 0.1],
    [1.0, -1.0, nextafter(0.0, inf)],
):
    exact = sum(map(Fraction, vals), Fraction())
    assert Fraction(sum_lower(vals)) <= exact <= Fraction(sum_upper(vals))
signs = []
for bits in (80, 128, 160):
    active_config.set(
        cfg.model_copy(
            update={"numerics": cfg.numerics.model_copy(update={"arbitrary_precision_bits": bits})}
        )
    )
    for counts in ((0, 10, 0), (1, 8, 1), (1, 98, 1), (500, 499, 1)):
        previous = ctx.prec
        region = raw_confidence_region(categorical_state(counts, 1), 0.05, 1e-12)
        assert ctx.prec == previous
        n = sum(counts)
        threshold = mp.log(mp.mpf(3) / mp.mpf(0.05))
        for k, interval in zip(counts, region.intervals, strict=True):
            beta = (
                mp.loggamma(k + mp.mpf(".5"))
                + mp.loggamma(n - k + mp.mpf(".5"))
                - mp.loggamma(n + 1)
                - 2 * mp.loggamma(mp.mpf(".5"))
            )
            for x in (interval.lower, interval.upper):
                if 0 < x < 1:
                    xx = mp.mpf(x)
                    value = beta - k * mp.log(xx) - (n - k) * mp.log1p(-xx)
                    assert value >= threshold
                    signs.append(
                        {
                            "bits": bits,
                            "counts": counts,
                            "endpoint": x,
                            "margin": str(value - threshold),
                        }
                    )
Path(__file__).resolve().with_name("independent-numerics.json").write_text(
    json.dumps(
        {
            "precision_digits": 110,
            "singleton_checks": cases,
            "exact_sum_cases": 1504,
            "root_sign_checks": signs,
            "status": "PASS",
        },
        indent=2,
    )
)
print(len(cases), "singleton cases;", 1504, "exact sums;", len(signs), "root signs: PASS")
