

import csv

from planet9lab.loaders import load_candidates, load_candidates_with_excluded


def _write_catalog(path, rows):
    path.write_text(
        "candidate_id,mass_earth,a_au,e,i_deg,omega_deg,Omega_deg,mean_anomaly_deg\n"
        + "".join(rows),
        encoding="utf-8",
    )
    return path


def _line(candidate_id, mass=5.0, a=500, e=0.25, i=20, omega=150, omega_node=80, mean_anomaly=0):
    return (
        f"{candidate_id},{mass},{a},{e},{i},{omega},{omega_node},{mean_anomaly}\n"
    )


class TestLoadCandidatesDeterministicOrder:
    """P0-2: truncation must follow `candidate_id` order, not CSV line order."""

    def test_selection_is_independent_of_csv_line_order(self, tmp_path):
        path = _write_catalog(
            tmp_path / "shuffled.csv",
            [_line("p9_row3"), _line("p9_row1"), _line("p9_row2"), _line("p9_row7"), _line("p9_row5")],
        )
        selected = load_candidates(path, max_candidates=3)
        assert [c.candidate_id for c in selected] == ["p9_row1", "p9_row2", "p9_row3"]

    def test_all_candidates_when_max_not_reached(self, tmp_path):
        path = _write_catalog(tmp_path / "small.csv", [_line("p9_b"), _line("p9_a")])
        assert {c.candidate_id for c in load_candidates(path, max_candidates=10)} == {"p9_a", "p9_b"}

    def test_with_excluded_returns_capacity_survivors(self, tmp_path):
        path = _write_catalog(
            tmp_path / "quadro2_style.csv",
            [_line("p9_row6"), _line("p9_row1"), _line("p9_row3"), _line("p9_row7")],
        )
        selected, excluded = load_candidates_with_excluded(path, max_candidates=2)
        assert [c.candidate_id for c in selected] == ["p9_row1", "p9_row3"]
        assert [c.candidate_id for c in excluded] == ["p9_row6", "p9_row7"]

    def test_with_excluded_no_cut_returns_empty_excluded(self, tmp_path):
        path = _write_catalog(tmp_path / "single.csv", [_line("p9_a")])
        selected, excluded = load_candidates_with_excluded(path, max_candidates=5)
        assert [c.candidate_id for c in selected] == ["p9_a"]
        assert excluded == []


class TestNotEvaluatedCapacityLimit:
    """P0-2: runs record capacity-cut survivors in both manifests."""

    def test_screen_manifest_records_capacity_exclusions(self, tmp_path):
        from planet9lab.run import run_screen

        catalog = _write_catalog(
            tmp_path / "catalog_over_budget.csv",
            [_line("p9_row1"), _line("p9_row2"), _line("p9_row3"), _line("p9_row4")],
        )
        budget = "configs/budgets/low.yaml"  # max_candidates=5
        run_dir = run_screen(budget, 12345, candidate_catalog=catalog, run_root=tmp_path / "runs")

        data_manifest = _read_json(run_dir / "data_manifest.json")
        assert data_manifest["not_evaluated_capacity_limit"] == []

        run_manifest = _read_json(run_dir / "audit" / "run_manifest.json")
        assert "not_evaluated_capacity_limit" in run_manifest
        assert run_manifest["candidate_count"] == 4

    def test_manifest_records_excluded_when_over_capacity(self, tmp_path):
        from planet9lab.run import run_screen

        catalog = _write_catalog(
            tmp_path / "catalog_over_budget.csv",
            [_line("p9_row1"), _line("p9_row2"), _line("p9_row3"), _line("p9_row4"), _line("p9_row5"), _line("p9_row6"), _line("p9_row7")],
        )
        budget = "configs/budgets/low.yaml"  # max_candidates=5
        run_dir = run_screen(budget, 12345, candidate_catalog=catalog, run_root=tmp_path / "runs")

        data_manifest = _read_json(run_dir / "data_manifest.json")
        assert data_manifest["not_evaluated_capacity_limit"] == ["p9_row6", "p9_row7"]

        run_manifest = _read_json(run_dir / "audit" / "run_manifest.json")
        assert run_manifest["not_evaluated_capacity_limit"] == ["p9_row6", "p9_row7"]
        assert run_manifest["candidate_count"] == 5

    def test_plan_reports_excluded_candidates(self):
        from planet9lab.run import plan_run

        plan = plan_run("configs/budgets/low.yaml")  # default catalog has 5, max 5
        assert plan["candidate_count"] == 5
        assert plan["candidates_excluded_capacity_limit"] == []


def _read_json(path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


class TestSeedInertForScreenCompare:
    """P1-1: `seed` must not change `screen`/`compare` results."""

    def _screen_ranking(self, tmp_path, seed):
        from planet9lab.run import run_screen

        run_dir = run_screen("configs/budgets/low.yaml", seed, run_root=tmp_path / "runs")
        return _read_csv(run_dir / "results" / "ranking.csv")

    def test_screen_ranking_identical_across_seeds(self, tmp_path):
        ranking_12345 = self._screen_ranking(tmp_path / "s12345", 12345)
        ranking_99999 = self._screen_ranking(tmp_path / "s99999", 99999)
        assert ranking_12345 == ranking_99999

    def test_run_manifest_declares_seed_inert(self, tmp_path):
        from planet9lab.run import run_screen

        run_dir = run_screen("configs/budgets/low.yaml", 12345, run_root=tmp_path / "runs")
        manifest = _read_json(run_dir / "audit" / "run_manifest.json")
        assert manifest["seed_effect"] == "inert_for_screen_compare_fixed_catalog"


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
