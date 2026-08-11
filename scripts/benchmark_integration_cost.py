"""Benchmark real REBOUND integration throughput on THIS machine and use it to
give an honest recommendation for `integration_years` in configs/budgets/secular.yaml.

Why this script exists
-----------------------
The article-support plan (item 1) requires: "Avaliar e documentar o custo
computacional real (tempo de parede por candidato) antes de rodar em escala".
Guessing a wall-clock cost from memory would violate the project's own
"no invented results" rule just as much as inventing a physics result would.
This script measures it directly, on the machine that will actually run the
full screen, using the real system size (giants + a P9 candidate + the full
ETNO catalog) and the real timestep from configs/budgets/secular.yaml.

Usage
-----
    python scripts/benchmark_integration_cost.py

Requires `rebound` to be installed (`pip install rebound`) and a working
compiler toolchain for the REBOUND C extension, which this sandbox does not
have (no network access to fetch the package). Run this on the target
machine, e.g. the Xeon E3-1230 v2 mentioned in project discussion.

Output
------
Writes results/hardware_benchmark.json with:
  - measured steps/second for the actual candidate system size
  - projected wall-clock time for 1e8, 1e9, and 4e9 year integrations,
    per branch (with_p9/without_p9) and for the full candidate set
  - a recommended integration_years that fits inside a configurable
    wall-clock budget (default: 48 hours), so the maintainer can make an
    informed, honest decision about configs/budgets/secular.yaml instead of
    guessing.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Wall-clock budget you are willing to dedicate to ONE candidate's control
# pair (with_p9 + without_p9) before you consider integration_years too
# expensive for this hardware. Adjust to your real constraints; 48h is a
# reasonable "runs over a weekend" default for a single old desktop CPU.
WALL_CLOCK_BUDGET_HOURS = 48.0
CALIBRATION_YEARS = 2_000.0  # short enough to measure quickly, long enough to be representative
CANDIDATE_HORIZONS_YEARS = [1e8, 5e8, 1e9, 2e9, 4e9]


def main() -> None:
    try:
        import rebound
    except ImportError:
        print(
            "rebound is not installed in this Python environment.\n"
            "This script must be run on the machine that will actually execute\n"
            "the screening run (pip install rebound), not in a network-isolated\n"
            "sandbox. Aborting without writing a benchmark result, so no\n"
            "invented number ends up in results/hardware_benchmark.json.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    from planet9lab.loaders import (
        included_etnos,
        load_budget,
        load_candidates,
        load_etnos,
        load_giants,
    )
    from planet9lab.physics import recommended_timestep_years

    giants = load_giants(ROOT / "data" / "solar_system" / "giants_epoch.csv")
    etnos = included_etnos(load_etnos(ROOT / "data" / "etnos" / "catalog.csv"))
    budget = load_budget(ROOT / "configs" / "budgets" / "secular.yaml")
    candidates = load_candidates(ROOT / "data" / "candidates_example.csv")

    timestep_info = recommended_timestep_years(giants)
    if abs(timestep_info["recommended_timestep_years"] - budget.timestep_years) > 1e-4:
        print(
            "WARNING: configs/budgets/secular.yaml timestep_years "
            f"({budget.timestep_years}) does not match the value derived from the "
            f"current giants catalog ({timestep_info['recommended_timestep_years']}). "
            "The catalog may have changed; re-derive the timestep before trusting "
            "this benchmark.",
            file=sys.stderr,
        )

    n_particles = 1 + len(giants) + 1 + len(etnos)  # sun + giants + P9 + ETNOs
    print(f"System size: {n_particles} particles ({len(giants)} giants, {len(etnos)} ETNOs, 1 P9 candidate)")
    print(f"Timestep: {budget.timestep_years} yr (from secular.yaml)")

    sim = rebound.Simulation()
    sim.units = ("yr", "AU", "Msun")
    import math

    sim.G = 4 * math.pi**2
    sim.add(m=1.0)
    for giant in giants:
        sim.add(m=giant.mass_solar, a=giant.a_au, e=giant.e)
    sample_candidate = candidates[0]
    sim.add(m=sample_candidate.mass_earth * 3.003e-6, a=sample_candidate.a_au, e=sample_candidate.e)
    for etno in etnos:
        sim.add(m=0.0, a=etno.a_au, e=etno.e)
    sim.move_to_com()
    sim.integrator = "whfast"
    sim.dt = budget.timestep_years

    start = time.perf_counter()
    sim.integrate(CALIBRATION_YEARS, exact_finish_time=0)
    elapsed = time.perf_counter() - start

    steps_taken = CALIBRATION_YEARS / budget.timestep_years
    steps_per_second = steps_taken / elapsed if elapsed > 0 else float("inf")
    years_per_second = CALIBRATION_YEARS / elapsed if elapsed > 0 else float("inf")

    print(f"Calibration: {CALIBRATION_YEARS} yr integrated in {elapsed:.3f} s")
    print(f"-> {steps_per_second:,.0f} timesteps/s, {years_per_second:,.1f} simulated yr/s (single branch, single core)")

    projections = {}
    for horizon in CANDIDATE_HORIZONS_YEARS:
        seconds_per_branch = horizon / years_per_second if years_per_second > 0 else float("inf")
        seconds_per_candidate_pair = seconds_per_branch * 2  # with_p9 + without_p9
        seconds_full_screen = seconds_per_candidate_pair * len(candidates)
        projections[str(horizon)] = {
            "hours_per_branch": round(seconds_per_branch / 3600, 3),
            "hours_per_candidate_control_pair": round(seconds_per_candidate_pair / 3600, 3),
            "hours_for_full_candidate_set": round(seconds_full_screen / 3600, 3),
            "days_for_full_candidate_set": round(seconds_full_screen / 86400, 3),
        }

    recommended_years = None
    for horizon in sorted(CANDIDATE_HORIZONS_YEARS):
        hours_pair = projections[str(horizon)]["hours_per_candidate_control_pair"]
        if hours_pair <= WALL_CLOCK_BUDGET_HOURS:
            recommended_years = horizon
    result = {
        "measured_on": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rebound_version": getattr(rebound, "__version__", "unknown"),
        "n_particles": n_particles,
        "timestep_years": budget.timestep_years,
        "calibration_years": CALIBRATION_YEARS,
        "calibration_wall_seconds": round(elapsed, 4),
        "steps_per_second": round(steps_per_second, 2),
        "simulated_years_per_second": round(years_per_second, 4),
        "wall_clock_budget_hours_per_candidate_pair": WALL_CLOCK_BUDGET_HOURS,
        "projections_by_horizon_years": projections,
        "recommended_integration_years": recommended_years,
        "recommendation_note": (
            "recommended_integration_years is the largest tested horizon whose "
            "projected with_p9+without_p9 wall-clock time for ONE candidate stays "
            "within wall_clock_budget_hours_per_candidate_pair. This is a single-"
            "core, single-candidate estimate; running multiple candidates "
            "sequentially multiplies this linearly (see hours_for_full_candidate_set)."
            if recommended_years is not None
            else "No tested horizon fits inside the configured wall-clock budget on "
            "this machine. Either raise WALL_CLOCK_BUDGET_HOURS (accept a longer "
            "run), reduce integration_years below 1e8, or reduce ETNO/candidate "
            "count. Do not silently keep 4e9 yr in secular.yaml if it is not "
            "actually reachable here."
        ),
    }

    out_path = ROOT / "results" / "hardware_benchmark.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(json.dumps(result["projections_by_horizon_years"], indent=2))
    if recommended_years is not None:
        print(f"\nRecommended integration_years for this machine: {recommended_years:.0f}")
    else:
        print("\nNo horizon fits the configured wall-clock budget; see recommendation_note above.")


if __name__ == "__main__":
    main()
