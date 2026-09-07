import json
import random

from planet9lab.loaders import load_etnos
from planet9lab.selection_bias import (
    _depth_prob_from_h,
    apply_selection_function,
    generate_synthetic_population,
    load_bias_config,
    load_h_catalog,
    real_catalog_varpis,
    run_selection_bias_check,
    selection_bias_check,
)

# Real 16-ETNO catalog used by the canonical article runs
# (scripts/run_artigo.py and the runs' --etnos flags). The placeholder
# catalog.csv / catalog_v2.csv only carry 5 fixtures each; this is the
# current 16-object catalog.
REAL_ETNO_CATALOG = "data/etnos/catalog_validated.csv"


def test_load_bias_config_reads_science_yaml():
    config = load_bias_config("configs/science/observational_bias.yaml")
    assert config.bias_model == "h_prior_from_catalog"
    assert config.h_catalog_path == "data/etnos/h_values.csv"
    assert config.albedo_default == 0.10


def test_generate_synthetic_population_shape_and_angle_ranges():
    rows = generate_synthetic_population(random.Random(7), n=100)
    assert len(rows) == 100
    for row in rows:
        assert 0 <= row["omega_deg"] < 360
        assert 0 <= row["Omega_deg"] < 360
        assert 0 <= row["mean_anomaly_deg"] < 360


def test_generate_synthetic_population_is_deterministic():
    first = generate_synthetic_population(random.Random(42), n=100)
    second = generate_synthetic_population(random.Random(42), n=100)
    other = generate_synthetic_population(random.Random(43), n=100)
    assert first == second
    assert first != other


def test_apply_selection_function_is_deterministic_for_fixed_seed():
    # The Step 5b passthrough stub is gone: the selection function now filters
    # probabilistically, so "returns population unchanged" no longer holds for
    # realistic factors. This test pins the determinism contract that keeps the
    # bias check reproducible (same seeded RNG -> same surviving subset).
    population = generate_synthetic_population(random.Random(7), n=200)
    first = apply_selection_function(
        population,
        rng=random.Random(99),
        limiting_magnitude_v=24.0,
        sky_coverage_deg2=15000.0,
        min_tracking_arc_years=2.0,
    )
    second = apply_selection_function(
        population,
        rng=random.Random(99),
        limiting_magnitude_v=24.0,
        sky_coverage_deg2=15000.0,
        min_tracking_arc_years=2.0,
    )
    other = apply_selection_function(
        population,
        rng=random.Random(100),
        limiting_magnitude_v=24.0,
        sky_coverage_deg2=15000.0,
        min_tracking_arc_years=2.0,
    )
    assert first == second
    assert first != other


def test_real_catalog_varpis_returns_16_catalog_values():
    etnos = load_etnos(REAL_ETNO_CATALOG)
    assert len(etnos) == 16
    varpis = real_catalog_varpis(etnos)
    assert len(varpis) == 16
    assert all(0 <= value < 360 for value in varpis)


def test_apply_selection_function_reduces_population_when_factors_restrictive():
    population = generate_synthetic_population(random.Random(7), n=500)
    restrictive = apply_selection_function(
        population,
        rng=random.Random(1),
        limiting_magnitude_v=22.0,   # depth = 1 - 0.15*(24.5-22.0) = 0.625
        sky_coverage_deg2=5000.0,    # sky = 5000/41253 ~= 0.121
        min_tracking_arc_years=10.0,  # arc = 1/(1+0.2*10) ~= 0.333
    )
    assert 0 < len(restrictive) < len(population)


def test_apply_selection_function_keeps_most_when_factors_permissive():
    population = generate_synthetic_population(random.Random(7), n=200)
    permissive = apply_selection_function(
        population,
        rng=random.Random(2),
        limiting_magnitude_v=24.5,   # depth = 1.0
        sky_coverage_deg2=41253.0,   # full sky: sky = 1.0
        min_tracking_arc_years=0.0,  # arc = 1.0
    )
    # All three factors are 1.0, so survival is (deterministically) 100%.
    assert len(permissive) == len(population)


def test_selection_bias_check_returns_all_required_keys():
    etnos = load_etnos(REAL_ETNO_CATALOG)
    config = load_bias_config("configs/science/observational_bias.yaml")
    result = selection_bias_check(etnos, config, seed=12345)
    assert {
        "n_real_catalog",
        "n_synthetic_generated",
        "n_synthetic_surviving",
        "surviving_fraction",
        "real_catalog_resultant_length_R",
        "surviving_synthetic_resultant_length_R",
        "real_exceeds_synthetic_R",
        "interpretation",
        "caveats",
    } <= set(result)
    assert result["n_real_catalog"] == 16
    assert result["n_synthetic_generated"] == config.n_synthetic
    assert len(result["caveats"]) == 3


def test_selection_bias_check_is_deterministic_for_fixed_seed():
    etnos = load_etnos(REAL_ETNO_CATALOG)
    config = load_bias_config("configs/science/observational_bias.yaml")
    first = selection_bias_check(etnos, config, seed=12345)
    second = selection_bias_check(etnos, config, seed=12345)
    assert first == second


# ---------------------------------------------------------------------------
# Blocker reconciliation in run_selection_bias_check: a favorable result
# (real_exceeds_synthetic_R: true) must retire the generic
# no_observational_bias_model config blocker for that run; an unfavorable
# result must keep it (the specific selection_bias_not_ruled_out blocker
# already covers the case). These tests run against a minimal run skeleton
# (run manifest + data manifest + pre-seeded blockers.json), which is all
# run_selection_bias_check reads.
# ---------------------------------------------------------------------------

UNFAVORABLE_BIAS_CONFIG_YAML = (
    "bias_model: none\n"
    "blocker_if_none: true\n"
    "limiting_magnitude_v: 22.0\n"
    "sky_coverage_deg2: 5000.0\n"
    "min_tracking_arc_years: 10.0\n"
    "n_synthetic: 200\n"
)


def _write_minimal_run(tmp_path, seed):
    run_dir = tmp_path / "run_blocker_check"
    audit_dir = run_dir / "audit"
    audit_dir.mkdir(parents=True)
    (audit_dir / "run_manifest.json").write_text(json.dumps({"seed": seed}), encoding="utf-8")
    # included_etnos left empty on purpose: the sample-vs-manifest check is
    # skipped when the list is empty, and the real catalog is resolvable
    # from the project root.
    (run_dir / "data_manifest.json").write_text(
        json.dumps({"input_files": {"etno_catalog": REAL_ETNO_CATALOG}, "included_etnos": []}),
        encoding="utf-8",
    )
    (audit_dir / "blockers.json").write_text(
        json.dumps(
            {
                "blockers": [
                    {
                        "blocker_id": "no_observational_bias_model",
                        "severity": "science_limit",
                        "message": "Não há modelo completo de viés observacional nesta versão; portanto, o resultado é apenas screening exploratório.",
                    },
                    {
                        "blocker_id": "etno_catalog_not_fully_validated",
                        "severity": "science_limit",
                        "message": "O catalogo de ETNOs contem objetos parciais ou nao validados.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def _blocker_ids(run_dir):
    data = json.loads((run_dir / "audit" / "blockers.json").read_text(encoding="utf-8"))
    return [item["blocker_id"] for item in data.get("blockers", [])]


def test_favorable_bias_check_removes_no_observational_bias_model_blocker(tmp_path):
    run_dir = _write_minimal_run(tmp_path, seed=20260903)
    result_path = run_selection_bias_check(run_dir, "configs/science/observational_bias.yaml")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    # Guard: this scenario must genuinely be the favorable outcome, so the
    # blocker assertions below never pass vacuously.
    assert result["real_exceeds_synthetic_R"] is True
    ids = _blocker_ids(run_dir)
    assert "no_observational_bias_model" not in ids
    # Unrelated blockers are untouched.
    assert "etno_catalog_not_fully_validated" in ids
    # The root-level snapshot copy stays in sync with audit/blockers.json.
    root_data = json.loads((run_dir / "blockers.json").read_text(encoding="utf-8"))
    assert "no_observational_bias_model" not in [item["blocker_id"] for item in root_data["blockers"]]


def test_unfavorable_bias_check_keeps_no_observational_bias_model_blocker(tmp_path):
    run_dir = _write_minimal_run(tmp_path, seed=6)
    restrictive = tmp_path / "observational_bias_restrictive.yaml"
    restrictive.write_text(UNFAVORABLE_BIAS_CONFIG_YAML, encoding="utf-8")
    result_path = run_selection_bias_check(run_dir, str(restrictive))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    # Guard: this scenario must genuinely be the unfavorable outcome.
    assert result["real_exceeds_synthetic_R"] is False
    ids = _blocker_ids(run_dir)
    # The generic blocker is kept on purpose, and the specific one is added.
    assert "no_observational_bias_model" in ids
    assert "selection_bias_not_ruled_out" in ids
    assert "etno_catalog_not_fully_validated" in ids


# New tests for the H-prior integration (observational bias model v1 with SBDB magnitudes)


def test_load_h_catalog_reads_csv():
    catalog = load_h_catalog("data/etnos/h_values.csv")
    assert len(catalog) == 16
    names = {name for name, _ in catalog}
    assert "90377 Sedna (2003 VB12)" in names
    assert "541132 Leleakuhonua (2015 TG387)" in names
    for _, h in catalog:
        assert isinstance(h, float)
        assert h > 0


def test_load_h_catalog_raises_on_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_h_catalog("data/etnos/does_not_exist.csv")


def test_load_h_catalog_raises_on_empty_csv(tmp_path):
    import pytest
    empty = tmp_path / "empty.csv"
    empty.write_text("# comment only\nobject,h\n", encoding="utf-8")
    with pytest.raises(ValueError, match="contains no H values"):
        load_h_catalog(empty)


def test_depth_prob_from_h_deterministic():
    assert _depth_prob_from_h(7.0, 24.5) == _depth_prob_from_h(7.0, 24.5)


def test_depth_prob_from_h_fainter_objects_have_lower_probability():
    bright = _depth_prob_from_h(3.0, 24.5)
    median = _depth_prob_from_h(6.5, 24.5)
    faint = _depth_prob_from_h(8.5, 24.5)
    assert bright == median  # brighter than median is NOT boosted (conservative)
    assert faint < median    # fainter than median is penalized
    assert 0.0 <= faint <= bright <= 1.0


def test_depth_prob_from_h_deeper_survey_increases_probability():
    shallow = _depth_prob_from_h(8.0, 22.0)
    deep = _depth_prob_from_h(8.0, 24.5)
    assert deep > shallow
    assert 0.0 <= shallow <= 1.0
    assert 0.0 <= deep <= 1.0


def test_generate_synthetic_population_with_h_prior_assigns_h_values():
    h_prior = [1.5, 6.16, 6.14, 7.8]
    pop = generate_synthetic_population(random.Random(7), n=50, h_prior_values=h_prior)
    assert len(pop) == 50
    for row in pop:
        assert "h_value" in row
        assert row["h_value"] in h_prior
    assert all(0 <= row["omega_deg"] < 360 for row in pop)
    assert all(0 <= row["Omega_deg"] < 360 for row in pop)
    assert all(0 <= row["mean_anomaly_deg"] < 360 for row in pop)


def test_generate_synthetic_population_without_h_prior_has_no_h():
    pop = generate_synthetic_population(random.Random(7), n=30)
    assert len(pop) == 30
    for row in pop:
        assert "h_value" not in row


def test_generate_synthetic_population_with_h_prior_is_deterministic():
    h_prior = [1.5, 6.16, 6.14, 7.8]
    a = generate_synthetic_population(random.Random(42), n=40, h_prior_values=h_prior)
    b = generate_synthetic_population(random.Random(42), n=40, h_prior_values=h_prior)
    c = generate_synthetic_population(random.Random(43), n=40, h_prior_values=h_prior)
    assert a == b
    assert a != c


def test_apply_selection_function_with_h_uses_per_object_depth():
    h_prior = [1.5, 8.5]
    pop = generate_synthetic_population(random.Random(7), n=200, h_prior_values=h_prior)
    survivors = apply_selection_function(
        pop, rng=random.Random(99), limiting_magnitude_v=24.5,
        sky_coverage_deg2=40000.0, min_tracking_arc_years=0.5,
    )
    assert 0 < len(survivors) <= len(pop)


def test_selection_bias_check_with_h_prior_reports_h_prior_stats(tmp_path):
    run_dir = _write_minimal_run(tmp_path, seed=20260903)
    result_path = run_selection_bias_check(run_dir, "configs/science/observational_bias.yaml")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["bias_model"] == "h_prior_from_catalog"
    assert result["h_prior_source"] == "data/etnos/h_values.csv"
    stats = result["h_prior_stats"]
    assert stats is not None
    assert stats["h_prior_n"] == 16
    assert stats["h_prior_min"] <= stats["h_prior_median"] <= stats["h_prior_max"]
    assert stats["h_prior_min"] <= stats["h_prior_mean"] <= stats["h_prior_max"]
    assert stats["h_prior_min"] <= 2.0
    assert stats["h_prior_max"] >= 7.0

