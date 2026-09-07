"""Etapa 4: MEGNO is an EXPERIMENTAL, uncalibrated chaos indicator.

These tests only assert that the isolated indicator is reproducible with a
fixed seed, produces a finite value, and is NOT wired into the screening
funnel. They never treat MEGNO as a Gyr-stability argument.
"""

import math

import pytest

rebound = pytest.importorskip("rebound")

from planet9lab.engine import ReboundEngine  # noqa: E402
from planet9lab.loaders import (  # noqa: E402
    included_etnos,
    load_budget,
    load_candidates,
    load_etnos,
    load_giants,
)
from planet9lab.megno import run_megno  # noqa: E402

FIXED_SEED = 42


def _engine_and_inputs():
    budget = load_budget("configs/budgets/low.yaml")
    engine = ReboundEngine(budget, 12345, load_giants("data/solar_system/giants_epoch.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    return engine, candidate, etnos


def test_run_megno_returns_finite_indicator_with_fixed_seed():
    engine, candidate, etnos = _engine_and_inputs()
    result = run_megno(engine, etnos, candidate, engine.budget.integration_years, seed=FIXED_SEED)
    assert result["status"] == "ok"
    assert result["candidate_id"] == candidate.candidate_id
    assert result["seed"] == FIXED_SEED
    assert isinstance(result["megno"], float) and math.isfinite(result["megno"])
    assert 0.0 < result["megno"] < 50.0


def test_run_megno_is_reproducible_for_same_seed():
    engine, candidate, etnos = _engine_and_inputs()
    first = run_megno(engine, etnos, candidate, engine.budget.integration_years, seed=FIXED_SEED)
    second = run_megno(engine, etnos, candidate, engine.budget.integration_years, seed=FIXED_SEED)
    assert first["megno"] == second["megno"]


def test_run_megno_sensitive_to_seed():
    engine, candidate, etnos = _engine_and_inputs()
    with_seed_a = run_megno(engine, etnos, candidate, engine.budget.integration_years, seed=FIXED_SEED)
    with_seed_b = run_megno(engine, etnos, candidate, engine.budget.integration_years, seed=FIXED_SEED + 1)
    assert with_seed_a["megno"] != with_seed_b["megno"]


def test_regular_two_body_system_yields_megno_near_two():
    sim = rebound.Simulation()
    sim.units = ("yr", "AU", "Msun")
    sim.G = 4 * math.pi**2
    sim.add(m=1.0)
    sim.add(m=3.003e-6, a=1.0, e=0.01)
    sim.move_to_com()
    sim.integrator = "whfast"
    sim.dt = 0.01
    sim.init_megno(seed=FIXED_SEED)
    sim.integrate(500.0)
    assert 1.5 < sim.megno() < 2.5


def test_megno_not_wired_into_funnel_modules():
    import pathlib

    funnel = [
        "planet9lab/run.py",
        "planet9lab/engine.py",
        "planet9lab/montecarlo.py",
        "planet9lab/robustness.py",
        "planet9lab/parallel.py",
    ]
    root = pathlib.Path(__file__).resolve().parent.parent
    for rel in funnel:
        text = (root / rel).read_text(encoding="utf-8")
        assert "megno" not in text, f"{rel} must not reference MEGNO (Etapa 4 isolation)"
