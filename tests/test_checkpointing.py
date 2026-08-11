"""Tests for the checkpoint/resume control flow in ReboundEngine.

IMPORTANT: these tests do NOT validate any physics. Real REBOUND is not
installable in this environment (no network access to fetch the C extension),
so a minimal fake stub reproducing only the small slice of the REBOUND API
the engine uses is installed into sys.modules for the duration of each test.
The fake's "integration" just advances a clock and applies a tiny deterministic
drift so drift-series rows are non-trivial; it proves nothing about numerical
accuracy. What it does prove: checkpoints are written to disk incrementally,
and resuming from a partial checkpoint continues from the last saved time
instead of silently restarting and duplicating work.
"""

from __future__ import annotations

import importlib.machinery
import json
import sys
import types
from pathlib import Path

import pytest

from planet9lab.artifacts import read_csv_dicts
from planet9lab.loaders import included_etnos, load_candidates, load_etnos, load_giants
from planet9lab.schemas import BudgetConfig


class _FakeVec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _FakeOrbit:
    def __init__(self, a, e, inc, omega, Omega, M):
        self.a, self.e, self.inc = a, e, inc
        self.omega, self.Omega, self.M = omega, Omega, M


class _FakeParticle:
    def __init__(self, m, a, e, inc=0.0, omega=0.0, Omega=0.0, M=0.0):
        self.m, self.a, self.e, self.inc = m, a, e, inc
        self.omega, self.Omega, self.M = omega, Omega, M
        self.x, self.y, self.z = 1.0, 0.0, 0.0
        self.vx, self.vy, self.vz = 0.0, 1.0, 0.0

    def orbit(self, primary=None):
        return _FakeOrbit(self.a, self.e, self.inc, self.omega % 360.0, self.Omega, self.M)


class _FakeSimulation:
    def __init__(self, path: str | None = None):
        self.t = 0.0
        self.particles: list[_FakeParticle] = []
        self.units = None
        self.G = None
        self.integrator = "whfast"
        self.dt = 1.0
        if path is not None and Path(path).exists():
            snapshots = json.loads(Path(path).read_text())
            last = snapshots[-1]
            self.t = last["t"]
            self.particles = [_FakeParticle(**p) for p in last["particles"]]

    def add(self, m=0.0, a=1.0, e=0.0, inc=0.0, omega=0.0, Omega=0.0, M=0.0):
        self.particles.append(_FakeParticle(m, a, e, inc, omega, Omega, M))

    def move_to_com(self):
        pass

    def energy(self):
        return -1.0 - 1e-9 * self.t

    def angular_momentum(self):
        return _FakeVec(0.0, 0.0, 1.0 + 1e-10 * self.t)

    def integrate(self, target_t, exact_finish_time=1):
        # Deterministic, non-physical: precess each particle's argument of
        # perihelion slightly so Delta_pomega series are non-constant. This is
        # ONLY meant to exercise the checkpoint/resume plumbing.
        for particle in self.particles:
            particle.omega = (particle.omega + 0.5 * (target_t - self.t)) % 360.0
        self.t = target_t

    def save_to_file(self, path):
        snapshot = {
            "t": self.t,
            "particles": [
                {
                    "m": p.m,
                    "a": p.a,
                    "e": p.e,
                    "inc": p.inc,
                    "omega": p.omega,
                    "Omega": p.Omega,
                    "M": p.M,
                }
                for p in self.particles
            ],
        }
        existing = []
        if Path(path).exists():
            existing = json.loads(Path(path).read_text())
        existing.append(snapshot)
        Path(path).write_text(json.dumps(existing))


@pytest.fixture
def fake_rebound(monkeypatch):
    module = types.ModuleType("rebound")
    module.__spec__ = importlib.machinery.ModuleSpec("rebound", loader=None)
    module.__version__ = "fake-test-stub"
    module.Simulation = _FakeSimulation
    monkeypatch.setitem(sys.modules, "rebound", module)
    yield module


def _small_budget(tmp_path, integration_years=10.0, checkpoint_interval_years=3.0):
    return BudgetConfig(
        integration_years=integration_years,
        timestep_years=1.0,
        seeds=[1],
        integrator="whfast",
        max_candidates=1,
        checkpoint_interval_years=checkpoint_interval_years,
    )


def test_checkpointed_run_writes_drift_series_and_archive(tmp_path, fake_rebound):
    from planet9lab.engine import ReboundEngine

    giants = load_giants("data/solar_system/giants_epoch.csv")
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    budget = _small_budget(tmp_path)
    engine = ReboundEngine(budget, seed=1, giants=giants, allow_analytical_fallback=False)

    checkpoint_dir = tmp_path / "checkpoints"
    result = engine.run_branch_checkpointed(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)

    archive = checkpoint_dir / f"{candidate.candidate_id}_with_p9.bin"
    drift_series = checkpoint_dir / f"{candidate.candidate_id}_with_p9_drift_series.csv"
    assert archive.exists()
    assert drift_series.exists()

    rows = read_csv_dicts(drift_series)
    # t=0 initial row + ceil(10/3)=4 checkpoint rows = 5
    assert len(rows) == 5
    assert float(rows[-1]["t_years"]) == pytest.approx(10.0)
    assert result["result"]["operational_status"] == "completed"


def test_resume_continues_from_last_checkpoint_without_duplicating_work(tmp_path, fake_rebound):
    from planet9lab.engine import ReboundEngine

    giants = load_giants("data/solar_system/giants_epoch.csv")
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    checkpoint_dir = tmp_path / "checkpoints"

    # First "run": interrupted budget only reaches t=4.
    partial_budget = _small_budget(tmp_path, integration_years=4.0, checkpoint_interval_years=3.0)
    engine_partial = ReboundEngine(partial_budget, seed=1, giants=giants, allow_analytical_fallback=False)
    engine_partial.run_branch_checkpointed(etnos, candidate, include_p9=False, checkpoint_dir=checkpoint_dir)

    drift_series = checkpoint_dir / f"{candidate.candidate_id}_without_p9_drift_series.csv"
    rows_after_partial = read_csv_dicts(drift_series)
    assert float(rows_after_partial[-1]["t_years"]) == pytest.approx(4.0)

    # "Resume": same checkpoint dir, full budget target of t=10. Must continue
    # from t=4, not restart from t=0 (which would duplicate the first rows).
    full_budget = _small_budget(tmp_path, integration_years=10.0, checkpoint_interval_years=3.0)
    engine_full = ReboundEngine(full_budget, seed=1, giants=giants, allow_analytical_fallback=False)
    engine_full.run_branch_checkpointed(etnos, candidate, include_p9=False, checkpoint_dir=checkpoint_dir)

    rows_after_resume = read_csv_dicts(drift_series)
    times = [float(row["t_years"]) for row in rows_after_resume]
    assert times[-1] == pytest.approx(10.0)
    # Strictly increasing: no duplicated/rewound checkpoints from a restart.
    assert times == sorted(times)
    assert len(times) == len(set(times))


def test_delta_pomega_series_only_written_with_p9(tmp_path, fake_rebound):
    from planet9lab.engine import ReboundEngine

    giants = load_giants("data/solar_system/giants_epoch.csv")
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    budget = _small_budget(tmp_path)
    engine = ReboundEngine(budget, seed=1, giants=giants, allow_analytical_fallback=False)
    checkpoint_dir = tmp_path / "checkpoints"

    engine.run_branch_checkpointed(etnos, candidate, include_p9=False, checkpoint_dir=checkpoint_dir)
    assert not (checkpoint_dir / f"{candidate.candidate_id}_without_p9_delta_pomega_series.csv").exists()

    result = engine.run_branch_checkpointed(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)
    assert (checkpoint_dir / f"{candidate.candidate_id}_with_p9_delta_pomega_series.csv").exists()
    assert result["delta_pomega_stability"] is not None
    assert result["result"]["delta_pomega_series_points"] > 0
