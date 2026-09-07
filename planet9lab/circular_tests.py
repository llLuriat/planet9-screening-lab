"""Formal circular statistics (Rayleigh test, Kuiper test, power analysis).

Configurable OPTIONAL diagnostic, placed alongside the project's current
ad-hoc angular thresholds. It is NOT wired into the screening funnel and does
NOT change the classification of any candidate.

Why these tests
---------------
The funnel's `apsidal_clustering_R` (mean resultant length) and the
anti-alignment score are descriptive statistics combined into a weighted
score. The Rayleigh test turns the same resultant length into a formal
uniformity p-value (Z = n * R^2), and the Kuiper test gives a distribution-
free uniformity p-value that is sensitive to both clustering and gaps.
Power analysis answers "how many ETNOs would be needed to detect a given
concentration at a chosen significance/power?".

Limitations (documented, do not overstate)
------------------------------------------
- The Rayleigh p-value uses Zar (1999) finite-n correction and is only an
  approximation for small n; treat values near 0.05 with caution.
- The Kuiper p-value interpolates the Stephens (1970) critical-value table.
- The power approximation assumes the asymptotic result that n*R^2 under the
  alternative follows a noncentral chi-square with 2 d.o.f. and noncentrality
  n*rho^2 (Fisher); it is a planning tool, not an exact computation.
- None of these results is a physics claim and none may be promoted to the
  default screening criterion without an explicit scientific decision
  (Categoria B) and explicit authorization.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable

from .metrics import circular_resultant_length

# Stephens (1970) critical values of V* for the Kuiper test, with the
# corresponding one-sided significance levels.
KUIPER_CRITICAL_V_STAR = (
    (0.150, 1.537),
    (0.100, 1.620),
    (0.050, 1.747),
    (0.025, 1.862),
    (0.010, 2.001),
)


def rayleigh_from_resultant_length(resultant_length: float, n: int) -> dict:
    """Rayleigh test from the mean resultant length R and sample size n.

    Z = n * R^2. Under H0 (uniform) Z ~ Exp(1) asymptotically; the p-value
    uses the Zar (1999) small-n correction terms."""
    if n <= 0:
        return {"n": n, "R": 0.0, "Z": 0.0, "p": 1.0}
    z_value = max(0.0, n * resultant_length**2)
    if z_value == 0.0:
        p_value = 1.0
    else:
        p_value = math.exp(-z_value) * (
            1.0
            + (2.0 * z_value - z_value**2) / (4.0 * n)
            - (24.0 * z_value - 132.0 * z_value**2 + 76.0 * z_value**3 - 9.0 * z_value**4)
            / (288.0 * n**2)
        )
    return {
        "n": n,
        "R": round(resultant_length, 6),
        "Z": round(z_value, 6),
        "p": round(max(0.0, min(1.0, p_value)), 6),
    }


def rayleigh_z(angles: Iterable[float]) -> dict:
    """Rayleigh test on a set of angles (degrees)."""
    vals = [float(a) for a in angles]
    return rayleigh_from_resultant_length(circular_resultant_length(vals), len(vals))


def kuiper_v(angles: Iterable[float]) -> dict:
    """Kuiper's test for uniformity of circular data.

    Returns the V statistic, the size-adjusted V*, and a p-value interpolated
    from the Stephens (1970) critical table."""
    vals = sorted([(float(a) % 360.0) / 360.0 for a in angles])
    n = len(vals)
    if n == 0:
        return {"n": 0, "V": 0.0, "V_star": 0.0, "p": 1.0}
    d_plus = max((i + 1) / n - u for i, u in enumerate(vals))
    d_minus = max(u - i / n for i, u in enumerate(vals))
    v_stat = d_plus + d_minus
    v_star = v_stat * (math.sqrt(n) + 0.155 + 0.24 / math.sqrt(n))
    p_value = _kuiper_p_from_v_star(v_star)
    return {"n": n, "V": round(v_stat, 6), "V_star": round(v_star, 6), "p": round(p_value, 6)}


def _kuiper_p_from_v_star(v_star: float) -> float:
    if v_star <= KUIPER_CRITICAL_V_STAR[0][1]:
        return 1.0
    if v_star >= KUIPER_CRITICAL_V_STAR[-1][1]:
        return 0.001
    for (alpha_high, v_high), (alpha_low, v_low) in zip(
        KUIPER_CRITICAL_V_STAR[:-1], KUIPER_CRITICAL_V_STAR[1:]
    ):
        if v_high <= v_star <= v_low:
            fraction = (v_star - v_high) / (v_low - v_high)
            log_p = math.log(alpha_high) + fraction * (math.log(alpha_low) - math.log(alpha_high))
            return math.exp(log_p)
    return 1.0


def rayleigh_power(rho: float, n: int, alpha: float, seed: int, n_reps: int = 4000) -> float:
    """Estimated power of the Rayleigh test for population resultant length
    rho and sample size n.

    Under the alternative, n*R^2 is approximated by a noncentral chi-square
    with 2 d.o.f. and noncentrality n*rho^2 (Fisher's asymptotic result),
    sampled as the sum of squares of two shifted standard normals with a
    fixed seed, so the estimate is reproducible."""
    if n <= 0:
        return 0.0
    critical = -math.log(alpha)
    noncentrality = max(0.0, n * rho**2)
    rng = random.Random(seed)
    rejections = 0
    for _ in range(n_reps):
        shift = math.sqrt(noncentrality)
        x = rng.gauss(0.0, 1.0)
        y = rng.gauss(0.0, 1.0)
        noncentral_chi2 = (x + shift) ** 2 + y**2
        z_sample = noncentral_chi2 / 2.0
        if z_sample > critical:
            rejections += 1
    return rejections / n_reps


def required_n_for_rayleigh_power(
    rho: float,
    alpha: float,
    target_power: float,
    seed: int,
    max_n: int = 500,
    n_reps: int = 4000,
) -> dict:
    """Smallest sample size n whose estimated Rayleigh power reaches
    target_power, or a note if max_n is insufficient."""
    best: int | None = None
    best_power = 0.0
    for n in range(3, max_n + 1):
        power = rayleigh_power(rho, n, alpha, seed, n_reps)
        if power >= target_power:
            best = n
            best_power = power
            break
        best_power = power
    return {
        "rho": rho,
        "alpha": alpha,
        "target_power": target_power,
        "required_n": best,
        "power_at_required_n": round(best_power, 6) if best is not None else None,
        "note": (
            f"no n <= {max_n} reaches the target power"
            if best is None
            else "smallest n whose estimated power reaches the target"
        ),
    }
