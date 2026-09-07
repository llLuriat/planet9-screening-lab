"""EXPERIMENTAL MEGNO chaos indicator.

NOT part of the screening funnel and NOT a stability claim.

MEGNO (Mean Exponential Growth factor of Nearby Orbits) is a fast chaos
indicator provided by REBOUND through ``Simulation.init_megno``. Values near
2.0 indicate regular/quasi-periodic motion; values that keep growing indicate
chaos.

IMPORTANT LIMITATIONS
---------------------
- Uncalibrated: the indicator has NOT been calibrated against any long (Gyr)
  real integration in this project. It must NEVER be cited in the article as
  evidence of Gyr-scale stability. Using MEGNO as a Gyr-stability argument is
  a separate scientific decision (Categoria B) requiring explicit
  authorization; do not implement it silently.
- Seed-fixed on purpose: ``init_megno(seed=...)`` keeps the measurement
  reproducible, but different seeds sample slightly different variational
  initializations, so treat the value as an auxiliary diagnostic only.
"""

from __future__ import annotations

from .engine import ReboundEngine
from .schemas import ETNORecord, P9Candidate


def run_megno(
    engine: ReboundEngine,
    etnos: list[ETNORecord],
    candidate: P9Candidate,
    integration_years: float,
    seed: int = 42,
    include_p9: bool = True,
) -> dict:
    """Compute the MEGNO indicator for one candidate with a fixed seed.

    Reuses ``ReboundEngine._configure_sim`` so the initial conditions and
    integrator settings are identical to the funnel branches.
    """
    sim = engine._configure_sim(etnos, candidate, include_p9=include_p9)
    sim.init_megno(seed=seed)
    sim.integrate(integration_years, exact_finish_time=0)
    return {
        "candidate_id": candidate.candidate_id,
        "seed": seed,
        "integration_years": integration_years,
        "timestep_years": engine.budget.timestep_years,
        "megno": float(sim.megno()),
        "interpretation_hint": (
            "~2.0 suggests regular motion; clearly larger suggests chaos. "
            "Uncalibrated auxiliary indicator only, not a stability proof."
        ),
        "status": "ok",
    }
