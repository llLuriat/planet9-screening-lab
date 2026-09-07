"""Etapa 5: formal circular statistics (Rayleigh / Kuiper / power) as an
OPTIONAL, configurable diagnostic placed alongside the current ad-hoc
thresholds. None of these tests asserts or changes any candidate
classification, and the real-run comparison is strictly read-only."""

import json
import random
from pathlib import Path

import pytest

from planet9lab.circular_report import circular_stats_report
from planet9lab.circular_tests import (
    kuiper_v,
    rayleigh_from_resultant_length,
    rayleigh_power,
    rayleigh_z,
    required_n_for_rayleigh_power,
)
from planet9lab.loaders import included_etnos, load_etnos

REAL_RUNS = [
    Path("runs/experiment_angle_robustness_20260812T145545073924Z"),
    Path("runs/experiment_i_boundary_scan_20260812T145800363579Z"),
]


def _uniform_angles(n=100, seed=7):
    rng = random.Random(seed)
    return [rng.uniform(0.0, 360.0) for _ in range(n)]


def _clustered_angles(n=13, seed=7):
    rng = random.Random(seed)
    return [10.0 + rng.uniform(-3.0, 3.0) for _ in range(n)]


def test_rayleigh_uniform_high_p_and_clustered_low_p():
    assert rayleigh_z(_uniform_angles())["p"] > 0.05
    assert rayleigh_z(_clustered_angles())["p"] < 0.05


def test_rayleigh_z_matches_resultant_length_form():
    angles = _clustered_angles()
    direct = rayleigh_z(angles)
    from_metric = rayleigh_from_resultant_length(direct["R"], direct["n"])
    assert direct["Z"] == pytest.approx(from_metric["Z"], rel=1e-3)
    assert direct["p"] == pytest.approx(from_metric["p"], rel=1e-3)


def test_rayleigh_p_bounds():
    result = rayleigh_z(_uniform_angles())
    assert 0.0 <= result["p"] <= 1.0
    assert rayleigh_from_resultant_length(0.0, 10)["p"] == 1.0


def test_kuiper_uniform_high_p_and_clustered_low_p():
    assert kuiper_v(_uniform_angles())["p"] > 0.05
    assert kuiper_v(_clustered_angles())["p"] < 0.05


def test_kuiper_p_bounds_and_deterministic():
    angles = _uniform_angles()
    first = kuiper_v(angles)
    second = kuiper_v(angles)
    assert first == second
    assert 0.0 <= first["p"] <= 1.0


def test_rayleigh_power_monotonic_in_n_and_rho():
    assert rayleigh_power(0.5, 50, 0.05, seed=1) > rayleigh_power(0.5, 10, 0.05, seed=1)
    assert rayleigh_power(0.7, 50, 0.05, seed=1) > rayleigh_power(0.5, 50, 0.05, seed=1)


def test_required_n_increases_as_rho_decreases():
    small = required_n_for_rayleigh_power(0.7, 0.05, 0.80, seed=12345)
    large = required_n_for_rayleigh_power(0.3, 0.05, 0.80, seed=12345)
    assert large["required_n"] is not None
    assert small["required_n"] is not None
    assert large["required_n"] > small["required_n"]


def _run_bytes(run_dir: Path) -> dict[str, bytes]:
    return {
        rel.name: rel.read_bytes()
        for rel in sorted(run_dir.glob("*"))
        if rel.is_file()
    }


def test_circular_stats_report_over_real_run_read_only():
    for run in REAL_RUNS:
        if not run.exists():
            continue
        before = _run_bytes(run)
        report = circular_stats_report(run)
        after = _run_bytes(run)
        assert report["etno_count_from_manifest"] == 13
        assert report["observed_catalog"]["sample_matches_manifest"] is True
        assert len(report["per_candidate"]) == len(
            json.loads((run / "candidates_results_cache.json").read_text(encoding="utf-8"))
        )
        for item in report["per_candidate"]:
            assert item["rayleigh_with_p9"] is not None
            assert 0.0 <= item["rayleigh_with_p9"]["p"] <= 1.0
        assert before == after
        assert report["comparison_summary"]["candidates_classified_candidate_of_interest"] >= 0
        assert "Categoria B" in report["comparison_summary"]["note"]


def test_observed_catalog_etnos_match_manifest():
    for run in REAL_RUNS:
        if not run.exists():
            continue
        report = circular_stats_report(run)
        observed = report["observed_catalog"]
        catalog_etnos = included_etnos(
            load_etnos(observed["catalog_path"])
        )
        names_in_run = {
            item["candidate_id"]
            for item in report["per_candidate"]
        }
        assert names_in_run
        assert observed["manifest_etno_count"] == 13
        assert len(catalog_etnos) >= observed["catalog_etno_count"]
