import csv
import json

from planet9lab.audit import audit_run
from planet9lab.diagnostics import diagnose_null_models, diagnose_scoring
from planet9lab.families import candidate_families, group_candidates
from planet9lab.loaders import load_budget, selected_etnos
from planet9lab.robustness import null_models, refresh_v2_report
from planet9lab.run import run_screen
from planet9lab.schemas import ETNORecord


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def etno(**overrides):
    base = {
        "name": "test_etno",
        "a_au": 250,
        "e": 0.7,
        "i_deg": 10,
        "omega_deg": 20,
        "Omega_deg": 30,
        "mean_anomaly_deg": 40,
        "epoch": "J2000",
        "frame": "heliocentric_ecliptic",
        "source": "unit_test",
        "validation_status": "partial",
        "selection_included": True,
        "selection_reason": "unit_test",
        "selection_notes": "unit_test",
    }
    base.update(overrides)
    return ETNORecord.model_validate(base)


def write_multiseed_budget(tmp_path):
    path = tmp_path / "multiseed.yaml"
    path.write_text(
        "\n".join(
            [
                "integration_years: 10",
                "timestep_years: 1.0",
                "seeds: [11, 22]",
                "integrator: whfast",
                "max_candidates: 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_etno_selection_rejects_low_a():
    selected, rejected = selected_etnos([etno(a_au=100, e=0.5)], {"min_a_au": 150, "min_q_au": 30})
    assert selected == []
    assert rejected[0]["reasons"] == ["a_au_below_threshold"]


def test_etno_selection_rejects_low_q():
    selected, rejected = selected_etnos([etno(a_au=200, e=0.9)], {"min_a_au": 150, "min_q_au": 30})
    assert selected == []
    assert "q_au_below_threshold" in rejected[0]["reasons"]


def test_etno_selection_allows_unvalidated_when_configured():
    selected, rejected = selected_etnos([etno(validation_status="unvalidated")], {"allow_unvalidated": True})
    assert len(selected) == 1
    assert rejected == []


def test_serious_budget_loads_aliases():
    budget = load_budget("configs/budgets/serious.yaml")
    assert budget.max_candidates == 100
    assert budget.integration_years == 50_000
    assert budget.timestep_years == 0.25
    assert budget.seeds == [12345, 22345, 32345]


def test_diagnose_scoring_outputs_files():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    diagnose_scoring(run_dir)
    assert (run_dir / "diagnostics" / "scoring_diagnosis.md").exists()
    assert (run_dir / "diagnostics" / "scoring_components.csv").exists()


def test_scoring_components_include_weights():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    diagnose_scoring(run_dir)
    rows = read_rows(run_dir / "diagnostics" / "scoring_components.csv")
    assert {"candidate_id", "component", "weight", "contribution"}.issubset(rows[0])


def test_diagnose_null_models_without_nulls_is_honest():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    diagnose_null_models(run_dir)
    data = json.loads((run_dir / "diagnostics" / "null_model_diagnosis.json").read_text(encoding="utf-8"))
    assert data["available"] is False


def test_null_models_multiple_models_and_percentiles():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    null_models(run_dir, top=1, n_shuffles=2, models="shuffle_varpi,randomize_angles,no_p9_catalog_baseline")
    rows = read_rows(run_dir / "robustness" / "null_models.csv")
    assert {row["null_model"] for row in rows} == {
        "shuffle_varpi",
        "randomize_angles",
        "no_p9_catalog_baseline",
    }
    assert (run_dir / "robustness" / "null_model_percentiles.csv").exists()


def test_null_model_rows_have_p_like_and_percentile():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    null_models(run_dir, top=1, n_shuffles=2, models="shuffle_varpi")
    row = read_rows(run_dir / "robustness" / "null_models.csv")[0]
    assert row["p_like"] != ""
    assert row["null_percentile"] != ""


def test_multiseed_budget_generates_seed_stability(tmp_path):
    run_dir = run_screen(write_multiseed_budget(tmp_path), 11)
    assert (run_dir / "results" / "seed_stability.csv").exists()
    summary = json.loads((run_dir / "results" / "seed_stability_summary.json").read_text(encoding="utf-8"))
    assert summary["enabled"] is True


def test_seed_stability_scores_between_zero_and_one(tmp_path):
    run_dir = run_screen(write_multiseed_budget(tmp_path), 11)
    summary = json.loads((run_dir / "results" / "seed_stability_summary.json").read_text(encoding="utf-8"))
    score = summary["candidates"][0]["seed_stability_score"]
    assert 0 <= score <= 1


def test_candidate_families_outputs_files():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    candidate_families(run_dir, top=3)
    assert (run_dir / "analysis" / "candidate_families.csv").exists()
    assert (run_dir / "analysis" / "candidate_families_summary.md").exists()


def test_candidate_families_summary_has_verdict_keyword():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    candidate_families(run_dir, top=3)
    text = (run_dir / "analysis" / "candidate_families_summary.md").read_text(encoding="utf-8")
    assert any(term in text for term in ["candidato isolado", "familia de candidatos", "nenhum padrao robusto"])


def test_catalog_partial_blocker_active_in_run():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    blockers = json.loads((run_dir / "audit" / "blockers.json").read_text(encoding="utf-8"))["blockers"]
    assert "etno_catalog_not_fully_validated" in {blocker["blocker_id"] for blocker in blockers}


def test_report_includes_post_v2_diagnostics_sections():
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    diagnose_scoring(run_dir)
    diagnose_null_models(run_dir)
    candidate_families(run_dir, top=3)
    refresh_v2_report(run_dir)
    report = (run_dir / "reports" / "report.md").read_text(encoding="utf-8")
    assert "Diagnóstico do score" in report
    assert "Diagnóstico dos modelos nulos" in report
    assert "Famílias de candidatos" in report
    assert "Mesmo que algum candidato supere testes internos, este projeto não confirma a existência do Planeta 9." in report


def test_audit_detects_missing_null_model_percentiles(tmp_path):
    run_dir = run_screen("configs/budgets/low.yaml", 12345)
    null_models(run_dir, top=1, n_shuffles=2)
    target = run_dir / "robustness" / "null_model_percentiles.csv"
    backup = tmp_path / "null_model_percentiles.csv"
    backup.write_bytes(target.read_bytes())
    target.unlink()
    ok, issues = audit_run(run_dir)
    assert ok is False
    assert any("null_model_percentiles" in issue for issue in issues)
    target.write_bytes(backup.read_bytes())


def test_group_candidates_can_find_family():
    candidates = [
        {"candidate_id": "a", "rank": "1", "delta_dynamic_score": "0.1", "scientific_status": "weak_candidate", "mass_earth": "5", "a_au": "450", "e": "0.2", "i_deg": "10", "omega_deg": "20", "Omega_deg": "30", "mean_anomaly_deg": "40"},
        {"candidate_id": "b", "rank": "2", "delta_dynamic_score": "0.09", "scientific_status": "weak_candidate", "mass_earth": "5.1", "a_au": "455", "e": "0.21", "i_deg": "11", "omega_deg": "22", "Omega_deg": "31", "mean_anomaly_deg": "42"},
    ]
    families = group_candidates(candidates)
    assert len(families) == 1
