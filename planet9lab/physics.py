from __future__ import annotations

import importlib.util
import math

from .constants import (
    au_to_m,
    deg_to_rad,
    m_to_au,
    normalize_degrees,
    orbital_period_years,
    rad_to_deg,
)
from .engine import vec_norm


def p9_perihelion_aphelion(candidate: dict) -> tuple[float, float]:
    q = candidate["a_au"] * (1.0 - candidate["e"])
    q_big = candidate["a_au"] * (1.0 + candidate["e"])
    return q, q_big


def recommended_timestep_years(giants: list, steps_per_shortest_period: float = 20.0) -> dict:
    """Derive a WHFast timestep from the shortest orbital period actually present
    in the integrated system, instead of hardcoding a round number.

    Rationale (documented, not arbitrary): WHFast is a symplectic Wisdom-Holman
    mapper. Its long-term energy conservation depends on resolving the fastest
    orbital frequency in the simulation with enough steps per orbit; the standard
    rule of thumb used across the REBOUND literature and tutorials is
    dt <= P_shortest / 20 (a slightly conservative choice; some long-term secular
    studies of the outer solar system use dt <= P_shortest / 10 as a looser upper
    bound). In this system the fastest body is whichever giant planet has the
    smallest semi-major axis (normally Jupiter, a ~ 5.20 AU, P ~ 11.86 yr), NOT
    the P9 candidate or the ETNOs, which orbit far more slowly and do not set the
    timestep requirement.
    """
    periods = {giant.name: orbital_period_years(giant.a_au) for giant in giants}
    if not periods:
        raise ValueError("cannot derive a timestep without at least one giant planet record")
    shortest_name = min(periods, key=periods.get)
    shortest_period = periods[shortest_name]
    dt = shortest_period / steps_per_shortest_period
    return {
        "shortest_period_body": shortest_name,
        "shortest_period_years": round(shortest_period, 6),
        "steps_per_shortest_period": steps_per_shortest_period,
        "recommended_timestep_years": round(dt, 6),
        "all_periods_years": {name: round(value, 6) for name, value in periods.items()},
    }


def run_physics_checks() -> dict:
    candidate = {
        "candidate_id": "physics_check_p9",
        "a_au": 500.0,
        "e": 0.25,
        "mass_earth": 5.0,
        "i_deg": 20.0,
        "omega_deg": 150.0,
        "Omega_deg": 80.0,
        "mean_anomaly_deg": 0.0,
    }
    rebound_ok = importlib.util.find_spec("rebound") is not None
    q, q_big = p9_perihelion_aphelion(candidate)
    checks = {
        "rebound_available": rebound_ok,
        "unit_conversion_au_round_trip": abs(m_to_au(au_to_m(1.0)) - 1.0) < 1e-12,
        "angular_round_trip": abs(rad_to_deg(deg_to_rad(123.456)) - 123.456) < 1e-12,
        "normalized_angle_example_deg": normalize_degrees(-30.0),
        "p9_perihelion_au": q,
        "p9_aphelion_au": q_big,
        "p9_perihelion_aphelion_coherent": 0 < q < q_big,
        "integrator_configured": False,
        "sun_test_particle_orbit_simple_ok": False,
        "energy_drift_rel": None,
        "angular_momentum_drift_rel": None,
        "angular_momentum_available": False,
        "rebound_version": "unavailable",
    }
    if rebound_ok:
        import rebound

        checks["rebound_version"] = getattr(rebound, "__version__", "unknown")
        sim = rebound.Simulation()
        sim.units = ("yr", "AU", "Msun")
        sim.G = 4 * math.pi**2
        sim.add(m=1.0)
        sim.add(m=3.003e-6, a=1.0, e=0.01)
        sim.move_to_com()
        sim.integrator = "whfast"
        sim.dt = 0.01
        checks["integrator_configured"] = sim.integrator == "whfast"
        e0 = sim.energy()
        h0 = vec_norm(sim.angular_momentum())
        sim.integrate(1.0)
        e1 = sim.energy()
        h1 = vec_norm(sim.angular_momentum())
        checks["energy_drift_rel"] = abs((e1 - e0) / e0) if abs(e0) > 0 else None
        checks["angular_momentum_available"] = h0 > 0
        checks["angular_momentum_drift_rel"] = abs((h1 - h0) / h0) if h0 > 0 else None
        checks["sun_test_particle_orbit_simple_ok"] = (
            checks["energy_drift_rel"] is not None
            and checks["energy_drift_rel"] < 1e-8
            and checks["angular_momentum_drift_rel"] is not None
            and checks["angular_momentum_drift_rel"] < 1e-8
        )
    checks["overall_ok"] = all(
        bool(checks[key])
        for key in [
            "rebound_available",
            "unit_conversion_au_round_trip",
            "angular_round_trip",
            "p9_perihelion_aphelion_coherent",
            "integrator_configured",
            "sun_test_particle_orbit_simple_ok",
        ]
    )
    return checks
