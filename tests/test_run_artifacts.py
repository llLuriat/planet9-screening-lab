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


def test_candidate_failure_writes_crash_log(tmp_path, monkeypatch):
    from planet9lab.engine import ReboundEngine

    def boom(self, *args, **kwargs):
        raise RuntimeError("simulated candidate failure")

    monkeypatch.setattr(ReboundEngine, "run_control_pair", boom)
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    crash = (run_dir / "audit" / "crash_log.jsonl").read_text(encoding="utf-8")
    assert "simulated candidate failure" in crash
    assert "RuntimeError" in crash
    assert "Traceback" in crash


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

    def fake_run_scan(config_path, etnos, giants, seed, run_dir):
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

