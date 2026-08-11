"""Monte Carlo / quasi-Monte Carlo scan over the Planet 9 parameter space
[M9, a9, e9, i9] (item 2 of the V1->V2 plan).

Design note on the filter funnel
---------------------------------
Running a full REBOUND N-body integration (let alone a Gyr-scale one) on
every sampled point is not computationally feasible on modest hardware once
n_points reaches 1e4-1e5 (see scripts/benchmark_integration_cost.py for why).
This module therefore implements a STAGED funnel, matching how this kind of
screening is actually done in the literature (e.g. Brown & Batygin run coarse
grids before refining):

  Stage 0 (all N points, free):      analytic physical-bounds sanity checks.
  Stage 1 (all N points, cheap):     analytic Hill-separation stability proxy.
  Stage 2 (<= max_stage2_samples):   short REBOUND integration, gross
                                      instability/ejection screen only.
  Stage 3 (<= max_stage3_samples):   full secular-budget REBOUND integration
                                      against the real ETNO catalog, apsidal
                                      alignment (Delta_pomega stability).
  Stage 4 (secular Hamiltonian):     NOT IMPLEMENTED - see below.
  Stage 5 (IR/optical detectability): NOT IMPLEMENTED - see below.

Stages 4 and 5 are explicitly marked "not_implemented" in the funnel summary
rather than silently omitted or faked with prose, per the project's own
V1->V2 requirement: "Se algum dos quatro filtros ainda não puder ser
computado numericamente, marcar explicitamente esse filtro como
not_implemented no relatório, em vez de embuti-lo apenas em prosa."
A secular-Hamiltonian filter would need a resonant-angle model (e.g.
Batygin & Morbidelli 2017's secular Hamiltonian formalism) that is not
implemented in this codebase; an IR/optical detectability filter would need a
photometric model (assumed albedo/radius -> apparent magnitude) plus real
survey depth/footprint data, neither of which exists here yet (this is the
same gap tracked as `detectability_status` in item 5 of the plan).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .artifacts import ensure_dir, write_csv, write_json
from .config import load_yaml
from .engine import ReboundEngine
from .loaders import load_budget
from .metrics import DELTA_POMEGA_LIBRATION_R_THRESHOLD
from .schemas import P9Candidate

_PRIMES = [2, 3, 5, 7]

FILTER_COLUMNS = [
    "stage0_physical_bounds",
    "stage1_hill_separation_proxy",
    "stage2_gross_stability",
    "stage3_apsidal_alignment",
    "stage4_secular_hamiltonian",
    "stage5_detectability_ir_optical",
]

NOT_IMPLEMENTED = "not_implemented"


def _van_der_corput(index: int, base: int) -> float:
    result = 0.0
    fraction = 1.0 / base
    i = index
    while i > 0:
        result += (i % base) * fraction
        i //= base
        fraction /= base
    return result


def halton_points(n_points: int, n_dims: int, start_index: int = 1) -> np.ndarray:
    """Deterministic low-discrepancy sequence in [0,1)^n_dims. `start_index`
    skips the degenerate index 0 (which is always the origin for every base)."""
    bases = _PRIMES[:n_dims]
    if len(bases) < n_dims:
        raise ValueError(f"only {len(_PRIMES)} prime bases configured, need {n_dims}")
    points = np.zeros((n_points, n_dims))
    for row, index in enumerate(range(start_index, start_index + n_points)):
        for col, base in enumerate(bases):
            points[row, col] = _van_der_corput(index, base)
    return points


def sample_parameter_space(config: dict) -> list[dict]:
    """Returns a list of dicts with mass_earth/a_au/e/i_deg, plus a
    deterministic sample_id, for every sampled point (before any filtering)."""
    bounds = config["bounds"]
    n_points = int(config["n_points"])
    dims = ["mass_earth", "a_au", "e", "i_deg"]
    if config.get("method", "qmc_halton") == "uniform_random":
        rng = np.random.default_rng(config.get("seed", 0))
        unit = rng.random((n_points, len(dims)))
    else:
        unit = halton_points(n_points, len(dims))
    samples = []
    for row_index in range(n_points):
        point = {"sample_id": row_index}
        for col_index, dim in enumerate(dims):
            lo, hi = bounds[dim]
            point[dim] = lo + unit[row_index, col_index] * (hi - lo)
        samples.append(point)
    return samples


def stage0_physical_bounds(point: dict) -> dict:
    """Free sanity checks: valid orbit, positive mass. Also records perihelion
    distance and whether it falls in the Brown & Batygin (2016) 150-350 AU
    preferred band, as a diagnostic (not a hard filter)."""
    a, e, mass = point["a_au"], point["e"], point["mass_earth"]
    valid = math.isfinite(a) and a > 0 and math.isfinite(e) and 0 <= e < 1 and math.isfinite(mass) and mass > 0
    q = a * (1 - e) if valid else None
    within_band = valid and 150.0 <= q <= 350.0
    return {"pass": valid, "perihelion_au": q, "within_literature_perihelion_band": within_band}


def stage1_hill_separation_proxy(point: dict, neptune_a_au: float = 30.1104, k_hill: float = 3.0) -> dict:
    """Cheap analytic proxy: is the candidate's orbit separated from Neptune's
    by at least k_hill mutual Hill radii? This is the same style of criterion
    used for two-body long-term-stability screening (Gladman 1993 uses
    2*sqrt(3) for the co-orbital/adjacent-planet case; we use a slightly more
    conservative k_hill=3 as a documented default, configurable). At the huge
    separations relevant to Planet Nine candidates (hundreds of AU vs
    Neptune's 30 AU) this filter is expected to pass for nearly all points -
    it exists to catch the pathological low-a/high-e corner of the sampled
    box where perihelion could dip close to Neptune's orbit, not to be a
    strong discriminator on its own."""
    a = point["a_au"]
    q = a * (1 - point["e"])
    # Mutual Hill radius using the candidate's mass only (Neptune's mass is
    # negligible in comparison for M9 in the sampled 5-20 Mearth range).
    m9_solar = point["mass_earth"] * 3.003e-6
    r_hill = ((m9_solar / 3.0) ** (1.0 / 3.0)) * ((a + neptune_a_au) / 2.0)
    separation = q - neptune_a_au
    passed = r_hill > 0 and separation >= k_hill * r_hill
    return {"pass": bool(passed), "hill_radii_separation": separation / r_hill if r_hill > 0 else None}


def run_stage2_gross_stability(point: dict, engine: ReboundEngine) -> dict:
    """Short integration (engine.budget = montecarlo_stage2.yaml), checking
    only for ejection / NaN / hyperbolic escape - not apsidal alignment."""
    candidate = P9Candidate(
        candidate_id=f"mc_{point['sample_id']}",
        mass_earth=point["mass_earth"],
        a_au=point["a_au"],
        e=point["e"],
        i_deg=point["i_deg"],
        omega_deg=150.0,  # fixed fiducial angle; stage 2 only screens a/e/i/mass stability
        Omega_deg=50.0,
        mean_anomaly_deg=180.0,
    )
    branch = engine.run_branch([], candidate, include_p9=True)
    result = branch["result"]
    passed = result["operational_status"] == "completed" and not result["numerical_failures"]
    return {"pass": bool(passed), "numerical_health_score": result["numerical_health_score"]}


def run_stage3_apsidal_alignment(
    point: dict,
    etnos: list,
    engine: ReboundEngine,
    checkpoint_dir: Path,
    threshold: float = DELTA_POMEGA_LIBRATION_R_THRESHOLD,
) -> dict:
    """Full secular-budget integration against the real ETNO catalog."""
    candidate = P9Candidate(
        candidate_id=f"mc_{point['sample_id']}",
        mass_earth=point["mass_earth"],
        a_au=point["a_au"],
        e=point["e"],
        i_deg=point["i_deg"],
        omega_deg=150.0,
        Omega_deg=50.0,
        mean_anomaly_deg=180.0,
    )
    branch = engine.run_branch(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)
    fraction = branch["result"].get("delta_pomega_stable_fraction")
    passed = fraction is not None and fraction >= 0.5
    return {"pass": bool(passed), "delta_pomega_stable_fraction": fraction}


def run_scan(
    config_path: str | Path,
    etnos: list,
    giants: list,
    seed: int,
    run_dir: str | Path,
) -> dict:
    """Drives the full staged funnel and writes results/parameter_space_scan.csv
    and results/reduction_funnel_summary.json under run_dir."""
    config = load_yaml(config_path)
    run_dir = Path(run_dir)
    ensure_dir(run_dir / "results")

    samples = sample_parameter_space(config)
    rows = []
    counts = {"total_sampled": len(samples)}

    stage1_survivors = []
    for point in samples:
        row = {"sample_id": point["sample_id"], **point}
        s0 = stage0_physical_bounds(point)
        row["stage0_physical_bounds"] = s0["pass"]
        row["perihelion_au"] = s0["perihelion_au"]
        row["within_literature_perihelion_band"] = s0["within_literature_perihelion_band"]
        if not s0["pass"]:
            row["stage1_hill_separation_proxy"] = None
            row["stage2_gross_stability"] = None
            row["stage3_apsidal_alignment"] = None
            row["stage4_secular_hamiltonian"] = NOT_IMPLEMENTED
            row["stage5_detectability_ir_optical"] = NOT_IMPLEMENTED
            rows.append(row)
            continue
        s1 = stage1_hill_separation_proxy(point)
        row["stage1_hill_separation_proxy"] = s1["pass"]
        row["hill_radii_separation"] = s1["hill_radii_separation"]
        row["stage2_gross_stability"] = None
        row["stage3_apsidal_alignment"] = None
        row["stage4_secular_hamiltonian"] = NOT_IMPLEMENTED
        row["stage5_detectability_ir_optical"] = NOT_IMPLEMENTED
        rows.append(row)
        if s1["pass"]:
            stage1_survivors.append((point, row))

    counts["stage0_survivors"] = sum(1 for r in rows if r["stage0_physical_bounds"])
    counts["stage1_survivors"] = len(stage1_survivors)

    max_stage2 = int(config.get("max_stage2_samples", 200))
    stage2_pool = stage1_survivors[:max_stage2]
    stage2_skipped = stage1_survivors[max_stage2:]
    for _point, row in stage2_skipped:
        row["stage2_gross_stability"] = "not_evaluated_capacity_limit"

    stage2_budget_path = config.get("stage2_budget", "configs/budgets/montecarlo_stage2.yaml")
    stage2_budget = load_budget(stage2_budget_path)
    stage2_engine = ReboundEngine(stage2_budget, seed, giants, allow_analytical_fallback=False)

    stage2_survivors = []
    for point, row in stage2_pool:
        outcome = run_stage2_gross_stability(point, stage2_engine)
        row["stage2_gross_stability"] = outcome["pass"]
        row["stage2_numerical_health_score"] = outcome["numerical_health_score"]
        if outcome["pass"]:
            stage2_survivors.append((point, row))
    counts["stage2_evaluated"] = len(stage2_pool)
    counts["stage2_survivors"] = len(stage2_survivors)
    counts["stage2_skipped_capacity_limit"] = len(stage2_skipped)

    max_stage3 = int(config.get("max_stage3_samples", 60))
    stage3_pool = stage2_survivors[:max_stage3]
    stage3_skipped = stage2_survivors[max_stage3:]
    for _point, row in stage3_skipped:
        row["stage3_apsidal_alignment"] = "not_evaluated_capacity_limit"

    secular_budget = load_budget("configs/budgets/secular.yaml")
    secular_engine = ReboundEngine(secular_budget, seed, giants, allow_analytical_fallback=False)
    checkpoint_dir = ensure_dir(run_dir / "montecarlo_checkpoints")

    stage3_survivors = []
    for point, row in stage3_pool:
        outcome = run_stage3_apsidal_alignment(point, etnos, secular_engine, checkpoint_dir)
        row["stage3_apsidal_alignment"] = outcome["pass"]
        row["stage3_delta_pomega_stable_fraction"] = outcome["delta_pomega_stable_fraction"]
        if outcome["pass"]:
            stage3_survivors.append((point, row))
    counts["stage3_evaluated"] = len(stage3_pool)
    counts["stage3_survivors"] = len(stage3_survivors)
    counts["stage3_skipped_capacity_limit"] = len(stage3_skipped)

    write_csv(run_dir / "results" / "parameter_space_scan.csv", rows)

    total = counts["total_sampled"] or 1
    funnel = {
        "n_points_sampled": counts["total_sampled"],
        "method": config.get("method", "qmc_halton"),
        "seed": config.get("seed"),
        "stages": {
            "stage0_physical_bounds": {
                "survivors": counts["stage0_survivors"],
                "pct_of_total": round(100 * counts["stage0_survivors"] / total, 4),
            },
            "stage1_hill_separation_proxy": {
                "survivors": counts["stage1_survivors"],
                "pct_of_total": round(100 * counts["stage1_survivors"] / total, 4),
            },
            "stage2_gross_stability": {
                "evaluated": counts["stage2_evaluated"],
                "survivors": counts["stage2_survivors"],
                "skipped_capacity_limit": counts["stage2_skipped_capacity_limit"],
                "pct_of_total": round(100 * counts["stage2_survivors"] / total, 4),
                "pct_of_evaluated": round(100 * counts["stage2_survivors"] / counts["stage2_evaluated"], 4)
                if counts["stage2_evaluated"]
                else None,
            },
            "stage3_apsidal_alignment": {
                "evaluated": counts["stage3_evaluated"],
                "survivors": counts["stage3_survivors"],
                "skipped_capacity_limit": counts["stage3_skipped_capacity_limit"],
                "pct_of_total": round(100 * counts["stage3_survivors"] / total, 4),
                "pct_of_evaluated": round(100 * counts["stage3_survivors"] / counts["stage3_evaluated"], 4)
                if counts["stage3_evaluated"]
                else None,
            },
            "stage4_secular_hamiltonian": {"status": NOT_IMPLEMENTED},
            "stage5_detectability_ir_optical": {"status": NOT_IMPLEMENTED},
        },
        "final_remaining_volume_pct_of_total": round(100 * counts["stage3_survivors"] / total, 4),
        "methodology_note": (
            "Stages 2 and 3 are capacity-limited (max_stage2_samples / "
            "max_stage3_samples in configs/montecarlo/parameter_space.yaml) "
            "because full REBOUND integration of every sampled point is not "
            "computationally feasible; percentages for those stages are "
            "computed only over the points actually evaluated where noted, "
            "and skipped points are recorded explicitly rather than silently "
            "dropped. Stages 4-5 are not implemented (see module docstring)."
        ),
    }
    write_json(run_dir / "results" / "reduction_funnel_summary.json", funnel)
    return funnel
