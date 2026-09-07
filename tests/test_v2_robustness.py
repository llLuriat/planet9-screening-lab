import csv
import json

from planet9lab.audit import audit_run
from planet9lab.robustness import (
    convergence,
    leave_one_out,
    null_models,
    refresh_v2_report,
    validate_top,
)
from planet9lab.run import run_screen


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_leave_one_out_generates_rows():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    leave_one_out(run_dir, top=1)
    rows = read_rows(run_dir / "robustness" / "leave_one_out.csv")
    assert len(rows) == 4


def test_robustness_score_between_zero_and_one():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    leave_one_out(run_dir, top=1)
    summary = json.loads((run_dir / "robustness" / "leave_one_out_summary.json").read_text(encoding="utf-8"))
    score = summary["candidates"][0]["robustness_score"]
    assert 0 <= score <= 1


def test_convergence_generates_summary():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    convergence(run_dir, top=1)
    assert (run_dir / "robustness" / "convergence_summary.json").exists()


def test_convergence_status_allowed():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    convergence(run_dir, top=1)
    summary = json.loads((run_dir / "robustness" / "convergence_summary.json").read_text(encoding="utf-8"))
    assert summary["candidates"][0]["status"] in {"passed", "failed", "inconclusive"}


def test_ias15_validation_avoids_strong_claims():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    validate_top(run_dir, top=1, integrator="ias15")
    text = (run_dir / "validation" / "ias15_summary.json").read_text(encoding="utf-8")
    assert "validated_planet9" not in text


def test_null_model_generates_distribution():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    null_models(run_dir, top=1, n_shuffles=2)
    rows = read_rows(run_dir / "robustness" / "null_models.csv")
    assert len(rows) == 2


def test_null_model_summary_has_percentile():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    null_models(run_dir, top=1, n_shuffles=2)
    summary = json.loads((run_dir / "robustness" / "null_models_summary.json").read_text(encoding="utf-8"))
    assert "null_percentile" in summary["candidates"][0]


def test_report_includes_v2_required_phrase():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    leave_one_out(run_dir, top=1)
    convergence(run_dir, top=1)
    validate_top(run_dir, top=1)
    null_models(run_dir, top=1, n_shuffles=2)
    refresh_v2_report(run_dir)
    report = (run_dir / "reports" / "report.md").read_text(encoding="utf-8")
    assert "Mesmo após os testes de robustez V2, este projeto não confirma a existência do Planeta 9." in report


def test_evidence_level_never_strong_after_v2_report():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    leave_one_out(run_dir, top=1)
    convergence(run_dir, top=1)
    validate_top(run_dir, top=1)
    null_models(run_dir, top=1, n_shuffles=2)
    refresh_v2_report(run_dir)
    ranking = (run_dir / "results" / "ranking.csv").read_text(encoding="utf-8")
    assert "strong" not in ranking


def test_audit_detects_missing_v2_summary(tmp_path):
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    leave_one_out(run_dir, top=1)
    target = run_dir / "robustness" / "leave_one_out_summary.json"
    backup = tmp_path / "leave_one_out_summary.json"
    backup.write_bytes(target.read_bytes())
    target.unlink()
    ok, issues = audit_run(run_dir)
    assert ok is False
    assert any("leave_one_out_summary" in issue for issue in issues)
    target.write_bytes(backup.read_bytes())


def test_v2_audit_passes_after_report():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    leave_one_out(run_dir, top=1)
    convergence(run_dir, top=1)
    validate_top(run_dir, top=1)
    null_models(run_dir, top=1, n_shuffles=2)
    refresh_v2_report(run_dir)
    ok, issues = audit_run(run_dir)
    assert ok, issues


def test_v2_report_lists_limitations_section():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    leave_one_out(run_dir, top=1)
    refresh_v2_report(run_dir)
    assert "Limitações restantes" in (run_dir / "reports" / "report.md").read_text(encoding="utf-8")


def test_ias15_status_allowed():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    validate_top(run_dir, top=1)
    summary = json.loads((run_dir / "validation" / "ias15_summary.json").read_text(encoding="utf-8"))
    assert summary["candidates"][0]["status"] in {"validated_preliminarily", "rejected_after_ias15", "inconclusive"}


def test_convergence_csv_has_three_dt_rows():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    convergence(run_dir, top=1)
    rows = read_rows(run_dir / "robustness" / "convergence.csv")
    assert len(rows) == 3

