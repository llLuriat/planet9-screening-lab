"""Regression tests for the Delta_pomega series when an ETNO is ejected.

Bug history (run `screen_20260924T174217246692Z`, 2026-09-25): the series
fieldnames were recomputed from each checkpoint's instantaneous keys, so a
checkpoint at which an ETNO had been ejected wrote a NARROWER row than the file
header. On the way back in, `csv.DictReader` maps cells positionally, so it not
only returned `None` for the missing columns (`float(None)` raised) - it also
attributed the surviving values to the WRONG ETNO names. 4 of the 5 candidates of
a 12h49m secular run were discarded as "failed" for that bookkeeping reason,
exactly the candidates whose ETNOs get ejected.

These tests reuse the fake REBOUND stub of tests/test_checkpointing.py (no
physics is validated here) and cover the three things the recovery depends on:
1. the series stays fixed-width when an ETNO is lost (empty cell, not a missing
   column), so the file is always re-readable;
2. a legacy ragged file no longer crashes a branch, and a branch resumed with its
   snapshot already at the target still reports the drift state from disk;
3. the series can be rebuilt from the SimulationArchive, reproducing the live
   computation for runs whose CSV was damaged by the old writer.
"""

from __future__ import annotations

import csv
import importlib.machinery
import json
import sys
import types
from pathlib import Path

import pytest

from planet9lab.artifacts import read_csv_dicts
from planet9lab.engine import ReboundEngine, _optional_float
from planet9lab.loaders import included_etnos, load_candidates, load_etnos, load_giants
from tests.test_checkpointing import _FakeParticle, _FakeSimulation, _small_budget


class _EjectingFakeSimulation(_FakeSimulation):
    """Fake REBOUND where the last ETNO is ejected (|a| > 5000 AU) from the
    second checkpoint onwards, i.e. after the series header is already written."""

    ejection_time: float = 6.0

    def integrate(self, target_t, exact_finish_time=1):
        super().integrate(target_t, exact_finish_time=exact_finish_time)
        if self.t >= self.ejection_time:
            self.particles[-1].a = 1.0e5


class _EjectingFakeArchive:
    """Minimal stand-in for `rebound.Simulationarchive`: exposes the snapshots
    that `_FakeSimulation.save_to_file` appended to a checkpoint file."""

    def __init__(self, path):
        self.path = Path(path)
        self.snapshots = json.loads(self.path.read_text())

    def __len__(self):
        return len(self.snapshots)

    def __getitem__(self, index):
        sim = _EjectingFakeSimulation()
        snapshot = self.snapshots[index]
        sim.t = snapshot["t"]
        sim.particles = [_FakeParticle(**particle) for particle in snapshot["particles"]]
        return sim


@pytest.fixture
def fake_rebound(monkeypatch):
    module = types.ModuleType("rebound")
    module.__spec__ = importlib.machinery.ModuleSpec("rebound", loader=None)
    module.__version__ = "fake-test-stub"
    module.Simulation = _EjectingFakeSimulation
    module.Simulationarchive = _EjectingFakeArchive
    monkeypatch.setitem(sys.modules, "rebound", module)
    yield module


def _engine(budget):
    giants = load_giants("data/solar_system/giants_epoch.csv")
    return ReboundEngine(budget, seed=1, giants=giants, allow_analytical_fallback=False)


def test_optional_float_treats_absent_cells_as_no_data():
    assert _optional_float(None) is None
    assert _optional_float("") is None
    assert _optional_float(["extra", "cells"]) is None
    assert _optional_float("not-a-number") is None
def test_series_stays_fixed_width_when_an_etno_is_ejected(tmp_path, fake_rebound):
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    engine = _engine(_small_budget(tmp_path))
    checkpoint_dir = tmp_path / "checkpoints"

    result = engine.run_branch_checkpointed(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)

    # The candidate must survive an ejection instead of being discarded before
    # the metrics exist. A lost ETNO is (by existing project policy) recorded as
    # a numerical failure, so the branch reports "failed" - the regression was
    # that it could not even produce a result.
    assert result["result"]["operational_status"] == "failed"
    assert result["result"]["lost_etnos"] == [etnos[-1].name]
    assert result["delta_pomega_stability"] is not None

    series_path = checkpoint_dir / f"{candidate.candidate_id}_with_p9_delta_pomega_series.csv"
    with series_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    widths = {len(row) for row in rows}
    assert len(widths) == 1, f"ragged series (this was the bug): widths={sorted(widths)}"
    assert len(rows[0]) == 1 + len(etnos)
    # The ejected ETNO keeps an empty cell in the checkpoints where it is gone...
    assert rows[-1][rows[0].index(etnos[-1].name)] == ""
    # ...and its short series is classified as insufficient_data, not a crash.
    per_etno = result["delta_pomega_stability"]["per_etno"]
    assert per_etno[etnos[-1].name]["classification"] == "insufficient_data"


def test_legacy_ragged_series_no_longer_crashes_and_drift_comes_from_disk(tmp_path, fake_rebound):
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    engine = _engine(_small_budget(tmp_path))
    checkpoint_dir = tmp_path / "checkpoints"
    series_path = checkpoint_dir / f"{candidate.candidate_id}_with_p9_delta_pomega_series.csv"

    # First pass: a complete integration, exactly as a real run would leave it.
    engine.run_branch_checkpointed(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)

    # Reproduce the legacy artifact: rows that omit the ejected ETNO's cell.
    rows = read_csv_dicts(series_path)
    header = list(rows[0].keys())
    ejected = etnos[-1].name
    with series_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows[1:]:
            writer.writerow([row[key] for key in header if not (key == ejected and row[key] == "")])
    with series_path.open(encoding="utf-8", newline="") as handle:
        assert len({len(row) for row in csv.reader(handle)}) > 1, "fixture must be ragged"

    # Resume with the same target: the snapshot already sits at t=10, so the
    # integration loop is skipped and every metric has to come from disk.
    resumed = engine.run_branch_checkpointed(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)

    assert resumed["result"]["operational_status"] == "failed"  # the ejected ETNO is reported as a loss
    assert ejected in resumed["result"]["lost_etnos"]
    assert resumed["result"]["energy_drift_rel"] is not None
    assert resumed["result"]["angular_momentum_drift_rel"] is not None
    assert resumed["delta_pomega_stability"] is not None


def test_rebuild_series_from_archive_reproduces_the_live_computation(tmp_path, fake_rebound):
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    engine = _engine(_small_budget(tmp_path))
    checkpoint_dir = tmp_path / "checkpoints"
    series_path = checkpoint_dir / f"{candidate.candidate_id}_with_p9_delta_pomega_series.csv"

    engine.run_branch_checkpointed(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)
    trusted = read_csv_dicts(series_path)
    assert len(trusted) > 1, "fixture needs at least two checkpoints"

    # Simulate the artifact of the old writer: destroy the CSV (the damage is not
    # recoverable from the file) and rebuild it from the archive alone.
    series_path.write_text("dano irreparavel no arquivo\n", encoding="utf-8")
    rebuilt_path = engine.rebuild_delta_pomega_series(etnos, candidate, checkpoint_dir)

    assert rebuilt_path == series_path
    rebuilt = read_csv_dicts(rebuilt_path)
    assert len(rebuilt) == len(trusted)
    assert set(rebuilt[0]) == set(trusted[0])
    for before, after in zip(trusted, rebuilt, strict=True):
        for key, value in before.items():
            if value == "" or after[key] == "":
                assert value == after[key] == "", f"{key}: {value!r} vs {after[key]!r}"
            else:
                assert float(after[key]) == pytest.approx(float(value), abs=1e-9)


def test_rebuild_series_returns_none_without_archive(tmp_path, fake_rebound):
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    engine = _engine(_small_budget(tmp_path))
    assert engine.rebuild_delta_pomega_series(etnos, candidate, tmp_path / "checkpoints") is None

