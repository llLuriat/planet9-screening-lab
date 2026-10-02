import json
from pathlib import Path

import planet9lab.run as run_module
from planet9lab.audit import audit_run
from planet9lab.run import ROOT_COPY_MAP, run_screen

PROJECT_RUNS = run_module.ROOT / "runs"


def test_root_copies_match_canonical_locations():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    for canonical, root_copy in ROOT_COPY_MAP.items():
        assert (run_dir / canonical).read_bytes() == (run_dir / root_copy).read_bytes(), (
            f"root copy {root_copy} diverged from {canonical}"
        )


def test_root_copies_stay_in_sync_after_refresh(tmp_path):
    from planet9lab.robustness import refresh_v2_report

    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    refresh_v2_report(run_dir)
    for canonical, root_copy in ROOT_COPY_MAP.items():
        assert (run_dir / canonical).read_bytes() == (run_dir / root_copy).read_bytes(), (
            f"root copy {root_copy} diverged from {canonical} after refresh"
        )


def test_data_manifest_records_the_candidate_catalog_actually_used(tmp_path):
    """`data_manifest.json` must record the candidate catalog the run REALLY used.

    Regression: `run_screen` applied the `--candidates` override to its own local
    copy of `default_paths()` and then handed the already-loaded candidates to
    `execute_run`, which called `default_paths()` again and never received the
    override. `data_manifest["input_files"]` is built from that second dict, so
    every run launched with `--candidates` recorded the DEFAULT
    `data/candidates_example.csv` instead of the file it actually read.

    This is a provenance-only defect - `candidates_hash` in `hashes.json` is
    computed from the loaded candidate objects and was always correct - but it
    makes the recorded input path wrong, which is exactly the kind of trail the
    audit chain depends on. Observed on the 4 Gyr run
    `screen_20260925T174027769815Z`, whose `replay_command.txt` says
    `--candidates data/candidates_quadro2.csv` while its `data_manifest.json`
    said `data/candidates_example.csv`.
    """
    candidates_path = tmp_path / "candidates_provenance.csv"
    candidates_path.write_text(
        "candidate_id,mass_earth,a_au,e,i_deg,omega_deg,Omega_deg,mean_anomaly_deg\n"
        "p9_provenance_marker,6.0,500,0.25,20,200,270,180\n",
        encoding="utf-8",
    )
    run_dir = run_screen(
        "configs/budgets/low.yaml",
        12345,
        candidate_catalog=str(candidates_path),
        run_root=tmp_path / "runs",
    )

    manifest = json.loads((run_dir / "data_manifest.json").read_text(encoding="utf-8"))
    recorded = Path(manifest["input_files"]["candidate_catalog"])
    assert recorded.resolve() == candidates_path.resolve(), (
        "data_manifest.json recorded "
        f"{recorded} but the run read {candidates_path}"
    )

    # The replay line must name the same file, so the recorded trail is replayable.
    replay = (run_dir / "replay_command.txt").read_text(encoding="utf-8")
    assert str(candidates_path) in replay

    # And the run really did use this catalog: its candidate is the one integrated.
    assert "p9_provenance_marker" in (run_dir / "candidates_input.csv").read_text(encoding="utf-8")


def test_candidate_failure_writes_crash_log_in_parallel_worker(tmp_path, monkeypatch):
    """Verify that a real failure inside a parallel worker (not via
    monkeypatch that doesn't cross process boundaries) still produces
    audit/crash_log.jsonl. We trigger the failure inside the worker via
    the PLANET9_FAIL_CANDIDATE env var, which the worker reads in its
    own process (so it crosses the ProcessPoolExecutor boundary naturally
    without relying on monkeypatch propagation)."""
    candidates_path = tmp_path / "candidates_fail.csv"
    candidates_path.write_text(
        "candidate_id,mass_earth,a_au,e,i_deg,omega_deg,Omega_deg,mean_anomaly_deg\n"
        "p9_fail_marker_xyz,6.0,500,0.25,20,200,270,180\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLANET9_FAIL_CANDIDATE", "p9_fail_marker_xyz")
    run_dir = run_screen(
        "configs/budgets/low.yaml",
        12345,
        candidate_catalog=str(candidates_path),
        max_workers=2,
    )
    crash = (run_dir / "audit" / "crash_log.jsonl").read_text(encoding="utf-8")
    assert "p9_fail_marker_xyz" in crash
    assert "PLANET9_FAIL_CANDIDATE" in crash
    assert "Traceback" in crash


def test_candidate_failure_writes_crash_log(tmp_path, monkeypatch):
    from planet9lab.engine import ReboundEngine

    def boom(self, *args, **kwargs):
        raise RuntimeError("simulated candidate failure")

    monkeypatch.setattr(ReboundEngine, "run_control_pair", boom)
    # The monkeypatch is lost in parallel workers (spawned processes),
    # so we must force sequential execution to ensure the exception
    # is raised in the same process where it's caught and logged.
    monkeypatch.setenv("PLANET9_MAX_WORKERS", "1")
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    crash = (run_dir / "audit" / "crash_log.jsonl").read_text(encoding="utf-8")
    assert "simulated candidate failure" in crash
    assert "RuntimeError" in crash
    assert "Traceback" in crash


def test_high_inclination_registers_consultative_blocker_without_invalidating(tmp_path):
    candidates_path = tmp_path / "candidates_high_i.csv"
    candidates_path.write_text(
        """candidate_id,mass_earth,a_au,e,i_deg,omega_deg,Omega_deg,mean_anomaly_deg
p9_prograde,6.0,500,0.35,20,200,270,180
p9_retrograde,6.0,500,0.35,100,200,270,180
""",
        encoding="utf-8",
    )
    run_dir = run_screen(
        "configs/budgets/low.yaml",
        12345,
        candidate_catalog=str(candidates_path),
    )
    ranking = run_module.read_csv_dicts(run_dir / "results" / "ranking.csv")
    by_id = {row["candidate_id"]: row for row in ranking}
    assert "p9_prograde" in by_id and "p9_retrograde" in by_id
    prograde_blockers = by_id["p9_prograde"].get("blockers", "")
    retrograde_blockers = by_id["p9_retrograde"].get("blockers", "")
    assert "inclination_out_of_model_regime" not in prograde_blockers
    assert "inclination_out_of_model_regime" in retrograde_blockers
    assert by_id["p9_retrograde"]["operational_status"] in {"completed", "invalid"}
    blockers = json.loads((run_dir / "audit" / "blockers.json").read_text(encoding="utf-8"))["blockers"]
    regime_blockers = [b for b in blockers if b.get("blocker_id") == "inclination_out_of_model_regime"]
    assert any(b.get("candidate_id") == "p9_retrograde" for b in regime_blockers)
    status = run_module.read_csv_dicts(run_dir / "candidates_status.csv")
    status_by_id = {row["candidate_id"]: row for row in status}
    assert "inclination_out_of_model_regime" in status_by_id["p9_retrograde"].get("blockers", "")


def test_run_compare_honors_explicit_run_root(tmp_path):
    from planet9lab.run import run_compare

    explicit = tmp_path / "explicit_compare_root"
    run_dir = run_compare("configs/candidates/mid_mass.yaml", "configs/budgets/low.yaml", 12345, run_root=explicit)
    assert explicit in run_dir.parents
    assert (explicit / "latest_run.txt").read_text(encoding="utf-8").strip() == str(run_dir)


def test_montecarlo_scan_honors_explicit_run_root(tmp_path, monkeypatch):
    from planet9lab import montecarlo as montecarlo_module
    from planet9lab.run import run_montecarlo_scan

    explicit = tmp_path / "explicit_mc_root"

    def fake_run_scan(config_path, etnos, giants, seed, run_dir, max_workers=None):
        return {"n_points_sampled": 0, "status": "stubbed"}

    monkeypatch.setattr(montecarlo_module, "run_scan", fake_run_scan)
    run_dir = run_montecarlo_scan(
        config_path="configs/montecarlo/parameter_space.yaml", seed=0, run_root=explicit
    )
    assert explicit in run_dir.parents
    assert (explicit / "latest_run.txt").read_text(encoding="utf-8").strip() == str(run_dir)


def test_run_generates_status_json():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    assert (run_dir / "status.json").exists()


def test_run_generates_report_in_reports_dir():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    assert (run_dir / "reports" / "report.md").exists()


def test_run_generates_hashes():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    assert (run_dir / "audit" / "hashes.json").exists()


def test_audit_run_fails_if_required_artifact_deleted(tmp_path):
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    target = run_dir / "status.json"
    backup = tmp_path / "status.json"
    backup.write_bytes(target.read_bytes())
    target.unlink()
    ok, issues = audit_run(run_dir)
    assert ok is False
    assert any("status.json" in issue for issue in issues)
    target.write_bytes(backup.read_bytes())


def test_runs_are_isolated_from_project_runs_dir(tmp_path):
    before = set(PROJECT_RUNS.iterdir()) if PROJECT_RUNS.exists() else set()
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    assert tmp_path in run_dir.parents
    assert (tmp_path / "latest_run.txt").exists()
    after = set(PROJECT_RUNS.iterdir())
    assert after == before


def test_latest_run_pointer_written_to_isolated_dir(tmp_path):
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    pointer = tmp_path / "latest_run.txt"
    assert pointer.read_text(encoding="utf-8").strip() == str(run_dir)
