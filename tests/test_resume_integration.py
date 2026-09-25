"""Integration-level test: a run interrupted mid-way (some candidates cached,
some still pending, RUNNING.lock left behind exactly as a real crash would
leave it) must be finishable by `resume_run` without recomputing the
candidates that already finished.

Uses the same fake REBOUND stub as tests/test_checkpointing.py; this proves
the run.py orchestration + caching logic, not any physics.
"""

from __future__ import annotations

import importlib.machinery
import json
import sys
import types
from pathlib import Path

import pytest

from planet9lab.artifacts import read_csv_dicts
from planet9lab.loaders import load_budget, load_candidates
from tests.test_checkpointing import _FakeSimulation  # reuse the same stub


@pytest.fixture
def fake_rebound(monkeypatch):
    module = types.ModuleType("rebound")
    module.__spec__ = importlib.machinery.ModuleSpec("rebound", loader=None)
    module.__version__ = "fake-test-stub"
    module.Simulation = _FakeSimulation
    monkeypatch.setitem(sys.modules, "rebound", module)
    yield module


def test_resume_finishes_run_without_recomputing_cached_candidates(tmp_path, fake_rebound):
    import shutil

    from planet9lab import run as run_module

    budget_path = Path("configs/budgets/low.yaml")
    budget = load_budget(budget_path)
    candidates = load_candidates("data/candidates_example.csv", budget.max_candidates)
    assert len(candidates) >= 3, "fixture assumes at least 3 example candidates"

    run_dir = run_module.execute_run(
        candidates=candidates,
        budget_path=budget_path,
        seed=42,
        command_name="screen",
        replay_args=["screen", "--budget", str(budget_path), "--seed", "42"],
        allow_analytical_fallback=False,
    )
    try:
        _resume_test_body(run_module, run_dir, candidates)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def _resume_test_body(run_module, run_dir, candidates):

    # Sanity: a normal (uninterrupted) run finishes cleanly and caches everyone.
    cache = json.loads((run_dir / "candidates_results_cache.json").read_text())
    assert set(cache.keys()) == {c.candidate_id for c in candidates}
    assert (run_dir / "SUCCESS.marker").exists() or (run_dir / "INVALID.marker").exists()

    # Now simulate an interruption: drop the cache entries and status for the
    # last candidate, put its status back to "pending", and leave RUNNING.lock
    # as a crash would (execute_run already removed it on success, so recreate it).
    interrupted_candidate = candidates[-1].candidate_id
    cache.pop(interrupted_candidate)
    (run_dir / "candidates_results_cache.json").write_text(json.dumps(cache))
    status_rows = read_csv_dicts(run_dir / "candidates_status.csv")
    for row in status_rows:
        if row["candidate_id"] == interrupted_candidate:
            row["operational_status"] = "pending"
            row["scientific_status"] = "pending"
    from planet9lab.artifacts import write_csv

    write_csv(run_dir / "candidates_status.csv", status_rows)
    (run_dir / "RUNNING.lock").write_text("simulated-crash\n")
    (run_dir / "SUCCESS.marker").unlink(missing_ok=True)
    (run_dir / "INVALID.marker").unlink(missing_ok=True)

    events_before = (run_dir / "events.log").read_text()

    result = run_module.resume_run(run_dir)

    assert result["pending"] == []
    assert interrupted_candidate in result["completed"]

    events_after = (run_dir / "events.log").read_text()
    new_events = events_after[len(events_before):]
    # The candidates that were never touched by the interruption must not
    # have been started again during resume.
    for candidate in candidates[:-1]:
        assert f'"candidate_id": "{candidate.candidate_id}", "event": "candidate_started"' not in new_events

    assert (run_dir / "SUCCESS.marker").exists() or (run_dir / "INVALID.marker").exists()
    assert not (run_dir / "RUNNING.lock").exists()


def test_resume_reconstructs_manifest_for_interrupted_run(tmp_path, fake_rebound):
    """B3: `resume` de run interrompida SEM audit/run_manifest.json.

    O manifesto só era gravado na finalização, então uma run que caiu no meio
    não podia ser retomada (o portão do `resume` abortava antes de chegar nos
    checkpoints). Agora o `resume` reconstrói o manifesto a partir dos
    artefatos do início da run (data_manifest.json, replay_command.txt,
    events.log, config.resolved.yaml) e a finalização o sobrescreve com o
    completo — os 6 hashes exigidos pelo audit-run precisam sobreviver.
    """
    import shutil

    from planet9lab import run as run_module

    budget_path = Path("configs/budgets/low.yaml")
    budget = load_budget(budget_path)
    candidates = load_candidates("data/candidates_example.csv", budget.max_candidates)
    assert len(candidates) >= 3, "fixture assumes at least 3 example candidates"

    run_dir = run_module.execute_run(
        candidates=candidates,
        budget_path=budget_path,
        seed=42,
        command_name="screen",
        replay_args=["screen", "--budget", str(budget_path), "--seed", "42"],
        allow_analytical_fallback=False,
    )
    try:
        # Interrupção realista do B3: run nunca finalizou -> sem manifesto;
        # último candidato sem cache e pendente; RUNNING.lock como um crash
        # deixaria (execute_run já o removeu no sucesso, então recriamos).
        (run_dir / "audit" / "run_manifest.json").unlink(missing_ok=True)
        assert not (run_dir / "audit" / "run_manifest.json").exists()

        interrupted_candidate = candidates[-1].candidate_id
        cache = json.loads((run_dir / "candidates_results_cache.json").read_text())
        cache.pop(interrupted_candidate)
        (run_dir / "candidates_results_cache.json").write_text(json.dumps(cache))
        status_rows = read_csv_dicts(run_dir / "candidates_status.csv")
        for row in status_rows:
            if row["candidate_id"] == interrupted_candidate:
                row["operational_status"] = "pending"
                row["scientific_status"] = "pending"
        from planet9lab.artifacts import write_csv

        write_csv(run_dir / "candidates_status.csv", status_rows)
        (run_dir / "RUNNING.lock").write_text("simulated-crash\n")
        (run_dir / "SUCCESS.marker").unlink(missing_ok=True)
        (run_dir / "INVALID.marker").unlink(missing_ok=True)

        events_before = (run_dir / "events.log").read_text()
        result = run_module.resume_run(run_dir)

        assert result["pending"] == []
        assert interrupted_candidate in result["completed"]

        # A reconstrução aconteceu e ficou registrada em events.log...
        events_after = (run_dir / "events.log").read_text()
        assert '"event": "manifest_reconstructed"' in events_after[len(events_before):]

        # ...e a finalização regravou o manifesto completo, com o seed
        # original da run (vindo do replay_command.txt) e os 6 hashes do
        # início da run em audit/hashes.json (exigidos pelo audit-run).
        manifest = json.loads((run_dir / "audit" / "run_manifest.json").read_text())
        assert manifest["run_id"] == run_dir.name
        assert manifest["seed"] == 42
        assert manifest["command"] == "screen"
        hashes = json.loads((run_dir / "audit" / "hashes.json").read_text())
        for key in (
            "config_hash",
            "catalog_hash",
            "giants_hash",
            "candidate_region_hash",
            "scoring_hash",
            "protocol_hash",
        ):
            assert hashes.get(key), f"missing hash after resume: {key}"

        assert (run_dir / "SUCCESS.marker").exists() or (run_dir / "INVALID.marker").exists()
        assert not (run_dir / "RUNNING.lock").exists()
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
