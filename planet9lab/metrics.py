from __future__ import annotations

import math
import statistics
from collections.abc import Iterable

from .constants import normalize_degrees


def angular_distance_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def circular_mean_deg(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    sx = sum(math.cos(math.radians(v)) for v in vals)
    sy = sum(math.sin(math.radians(v)) for v in vals)
    return normalize_degrees(math.degrees(math.atan2(sy, sx)))


def circular_resultant_length(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    sx = sum(math.cos(math.radians(v)) for v in vals)
    sy = sum(math.sin(math.radians(v)) for v in vals)
    return max(0.0, min(1.0, math.hypot(sx, sy) / len(vals)))


def circular_dispersion_deg(values: Iterable[float]) -> float:
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    mean = circular_mean_deg(vals)
    distances = [angular_distance_deg(v, mean) for v in vals]
    return statistics.pstdev(distances)


def bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if not math.isfinite(value):
        return low
    return max(low, min(high, value))


def anti_alignment_score(etno_longitudes: Iterable[float], p9_longitude: float | None) -> float:
    vals = list(etno_longitudes)
    if not vals or p9_longitude is None:
        return 0.0
    target = normalize_degrees(p9_longitude + 180.0)
    distances = [angular_distance_deg(v, target) for v in vals]
    return bounded(1.0 - statistics.mean(distances) / 180.0)


def stability_score(survival_rate: float, energy_drift_rel: float | None, angular_drift_rel: float | None) -> float:
    energy_penalty = 0.0 if energy_drift_rel is None else min(1.0, abs(energy_drift_rel) / 1e-3)
    angular_penalty = 0.0 if angular_drift_rel is None else min(1.0, abs(angular_drift_rel) / 1e-3)
    return bounded(0.6 * survival_rate + 0.2 * (1 - energy_penalty) + 0.2 * (1 - angular_penalty))


def numerical_health_score(energy_drift_rel: float | None, angular_drift_rel: float | None, failures: list[str]) -> float:
    if failures:
        return 0.0
    energy_penalty = 0.0 if energy_drift_rel is None else min(1.0, abs(energy_drift_rel) / 1e-4)
    angular_penalty = 0.0 if angular_drift_rel is None else min(1.0, abs(angular_drift_rel) / 1e-4)
    return bounded(1.0 - 0.5 * energy_penalty - 0.5 * angular_penalty)


def compute_branch_metrics(
    etno_orbits: list[dict],
    candidate: dict | None,
    survival_rate: float,
    energy_drift_rel: float | None,
    angular_drift_rel: float | None,
    failures: list[str],
) -> dict:
    longitudes = [normalize_degrees(item["omega_deg"] + item["Omega_deg"]) for item in etno_orbits]
    p9_longitude = None
    if candidate is not None:
        p9_longitude = normalize_degrees(candidate["omega_deg"] + candidate["Omega_deg"])
    apsidal_r = circular_resultant_length(longitudes)
    anti = anti_alignment_score(longitudes, p9_longitude)
    stability = stability_score(survival_rate, energy_drift_rel, angular_drift_rel)
    numerical = numerical_health_score(energy_drift_rel, angular_drift_rel, failures)
    return {
        "apsidal_clustering_R": round(apsidal_r, 6),
        "anti_alignment_score": round(anti, 6),
        "survival_rate": round(survival_rate, 6),
        "stability_score": round(stability, 6),
        "numerical_health_score": round(numerical, 6),
    }


# Documented, non-arbitrary criterion for "Δϖ estável" (item 1 of the V1->V2 plan).
#
# Definition: for a given ETNO i, let Δϖ_i(t) = ϖ_etno_i(t) - ϖ_P9(t) (mod 360°),
# where ϖ = ω + Ω is the longitude of perihelion. Δϖ_i(t) is called "librating"
# (i.e. apsidally confined, the regime associated with a real secular/resonant
# coupling to a Planet Nine-like perturber in Batygin & Brown 2016 and follow-up
# literature) if it stays confined to a bounded range around some center over
# time, as opposed to "circulating" through the full 0-360° range.
#
# We measure this with circular statistics on the *second half* of the
# integration only (so any transient from the initial condition is excluded):
# the mean resultant length R of Δϖ_i(t) over that half. R = 1 means a single
# fixed angle (perfect libration around a point); R = 0 means uniform coverage
# of all angles (circulation). We call R >= DELTA_POMEGA_LIBRATION_R_THRESHOLD
# "stable" (librating), which corresponds to a circular standard deviation of
# roughly <= 90 degrees around the libration center - i.e. the angle spends most
# of its time within a half-circle centered on some fixed value, rather than
# visiting the full circle. This threshold is a documented modelling choice, not
# a value taken from a specific paper, and must be reported as such in the
# article; it is applied uniformly and is configurable via
# DELTA_POMEGA_LIBRATION_R_THRESHOLD so any change is visible in version control.
DELTA_POMEGA_LIBRATION_R_THRESHOLD = 0.5


def delta_pomega_instant(etno_orbits: list[dict], p9_orbit: dict | None) -> dict[str, float] | None:
    """Return {etno_name: Delta_pomega_deg} for one instant in time, or None if
    there is no P9 in this branch (without_p9 has no perihelion to compare to)."""
    if p9_orbit is None:
        return None
    p9_pomega = normalize_degrees(p9_orbit["omega_deg"] + p9_orbit["Omega_deg"])
    return {
        item["name"]: normalize_degrees(
            normalize_degrees(item["omega_deg"] + item["Omega_deg"]) - p9_pomega
        )
        for item in etno_orbits
    }


def delta_pomega_stability(
    series_by_etno: dict[str, list[float]],
    threshold: float = DELTA_POMEGA_LIBRATION_R_THRESHOLD,
) -> dict:
    """series_by_etno: {etno_name: [Delta_pomega_deg at each checkpoint, in time order]}.
    Uses only the second half of each series (steady-state, post-transient)."""
    per_etno: dict[str, dict] = {}
    stable_count = 0
    evaluated = 0
    for name, series in series_by_etno.items():
        n = len(series)
        if n < 4:
            per_etno[name] = {"resultant_R": None, "classification": "insufficient_data"}
            continue
        second_half = series[n // 2 :]
        resultant = circular_resultant_length(second_half)
        classification = "librating_stable" if resultant >= threshold else "circulating_unstable"
        per_etno[name] = {
            "resultant_R": round(resultant, 6),
            "circular_dispersion_deg": round(circular_dispersion_deg(second_half), 3),
            "classification": classification,
        }
        evaluated += 1
        if classification == "librating_stable":
            stable_count += 1
    fraction = round(stable_count / evaluated, 6) if evaluated else None
    return {
        "threshold_R": threshold,
        "per_etno": per_etno,
        "evaluated_count": evaluated,
        "stable_count": stable_count,
        "delta_pomega_stable_fraction": fraction,
    }


def dynamic_score(metrics: dict, weights: dict) -> float:
    value = (
        float(weights["apsidal_clustering"]) * float(metrics["apsidal_clustering_R"])
        + float(weights["anti_alignment"]) * float(metrics["anti_alignment_score"])
        + float(weights["survival_rate"]) * float(metrics["survival_rate"])
        + float(weights["stability"]) * float(metrics["stability_score"])
        + float(weights["numerical_health"]) * float(metrics["numerical_health_score"])
    )
    return round(bounded(value), 6)


def ranking_summary(rows: list[dict]) -> dict:
    deltas = [
        float(row["delta_dynamic_score"])
        for row in rows
        if row.get("operational_status") == "completed"
        and row.get("scientific_status") != "invalid"
    ]
    if not deltas:
        return {
            "delta_score_min": None,
            "delta_score_max": None,
            "delta_score_mean": None,
            "delta_score_median": None,
            "delta_score_std": None,
            "top1_delta_score": None,
            "top1_minus_median": None,
            "top1_minus_top10": None,
            "top1_percentile": None,
            "top1_distinctness": "not_computed",
        }
    ordered = sorted(deltas, reverse=True)
    top1 = ordered[0]
    median = statistics.median(deltas)
    top10_ref = ordered[min(9, len(ordered) - 1)]
    std = statistics.pstdev(deltas) if len(deltas) > 1 else 0.0
    percentile = 100.0 * sum(1 for value in deltas if value <= top1) / len(deltas)
    if top1 <= 0:
        distinctness = "least_bad_only"
    elif std == 0:
        distinctness = "flat_ranking"
    elif top1 - median >= std:
        distinctness = "top1_distinct"
    else:
        distinctness = "top1_not_strongly_distinct"
    return {
        "delta_score_min": round(min(deltas), 6),
        "delta_score_max": round(max(deltas), 6),
        "delta_score_mean": round(statistics.mean(deltas), 6),
        "delta_score_median": round(median, 6),
        "delta_score_std": round(std, 6),
        "top1_delta_score": round(top1, 6),
        "top1_minus_median": round(top1 - median, 6),
        "top1_minus_top10": round(top1 - top10_ref, 6),
        "top1_percentile": round(percentile, 3),
        "top1_distinctness": distinctness,
    }

