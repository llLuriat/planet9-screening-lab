from planet9lab.rescore import rescore_run
from planet9lab.run import run_screen


def test_rescore_does_not_overwrite_original_ranking():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    original = (run_dir / "results" / "ranking.csv").read_text(encoding="utf-8")
    rescore_dir = rescore_run(run_dir, "configs/scoring/default_weights.yaml")
    assert (rescore_dir / "rescore_report.md").exists()
    assert (run_dir / "results" / "ranking.csv").read_text(encoding="utf-8") == original

