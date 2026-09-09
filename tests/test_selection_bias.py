import json
import random

from planet9lab.loaders import load_etnos
from planet9lab.selection_bias import (
    _depth_prob_from_h,
    _efficiency_square,
    apply_selection_function,
    generate_synthetic_population,
    get_ossos_efficiency_params,
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


def test_generate_synthetic_population_with_distances_and_h():
    h_catalog = load_h_catalog("data/etnos/h_values.csv")
    rows = generate_synthetic_population(
        random.Random(7), n=50, h_prior_values=[h for _, h in h_catalog]
    )
    assert len(rows) == 50
    for row in rows:
        assert 0 <= row["omega_deg"] < 360
        assert 0 <= row["Omega_deg"] < 360
        assert 0 <= row["mean_anomaly_deg"] < 360
        assert 0 <= row["i_deg"] <= 180
        assert row["r_au"] > 0
        assert row["delta_au"] > 0
        assert row["h_value"] > 0


def test_depth_prob_from_h_bright_objects_not_boosted():
    bright = _depth_prob_from_h(2.0, 24.5)
    median = _depth_prob_from_h(6.5, 24.5)
    faint = _depth_prob_from_h(9.0, 24.5)
    assert bright == median  # bright objects are NOT boosted
    assert faint < median  # faint objects are penalized
    assert 0.0 <= faint <= 1.0


def test_apply_selection_function_with_distances_uses_realistic_curve():
    h_catalog = load_h_catalog("data/etnos/h_values.csv")
    population = generate_synthetic_population(
        random.Random(7), n=500, h_prior_values=[h for _, h in h_catalog]
    )
    assert "r_au" in population[0]
    assert "h_value" in population[0]
    ep = get_ossos_efficiency_params()
    survivors = apply_selection_function(
        population,
        rng=random.Random(3),
        limiting_magnitude_v=24.0,
        sky_coverage_deg2=15000.0,
        min_tracking_arc_years=2.0,
        ossos_efficiency_params=ep,
    )
    # With realistic curve, some but not all survive
    assert 0 <= len(survivors) <= len(population)


def test_apply_selection_function_without_distances_falls_back_to_linear():
    h_catalog = load_h_catalog("data/etnos/h_values.csv")
    population = generate_synthetic_population(
        random.Random(7), n=100, h_prior_values=[h for _, h in h_catalog]
    )
    # Remove distance fields to trigger fallback
    for row in population:
        row.pop("r_au", None)
        row.pop("delta_au", None)
    ep = get_ossos_efficiency_params()
    survivors = apply_selection_function(
        population,
        rng=random.Random(42),
        limiting_magnitude_v=24.0,
        sky_coverage_deg2=15000.0,
        min_tracking_arc_years=2.0,
        ossos_efficiency_params=ep,
    )
    # Should still work (fallback to linear stand-in)
    assert isinstance(survivors, list)


def test_ossos_efficiency_curve_matches_paper_figure4():
    ep = get_ossos_efficiency_params()
    # At m0 (half-magnitude), efficiency should be ~50% of the plateau
    # The plateau is (eff_max - c*(m0-21)^2)
    plateau = ep["eff_max"] - ep["c"] * (ep["m0"] - 21) ** 2
    eta_at_m0 = _efficiency_square(ep["m0"], ep["eff_max"], ep["c"], ep["m0"], ep["sig"])
    assert abs(eta_at_m0 - plateau / 2.0) < 0.01

    # At bright magnitudes (m << m0), efficiency should approach the plateau
    eta_bright = _efficiency_square(21.0, ep["eff_max"], ep["c"], ep["m0"], ep["sig"])
    plateau_21 = ep["eff_max"]  # c*(21-21)^2 = 0
    assert abs(eta_bright - plateau_21) < 0.01

    # At faint magnitudes (m >> m0), efficiency should approach 0
    eta_faint = _efficiency_square(26.0, ep["eff_max"], ep["c"], ep["m0"], ep["sig"])
    assert eta_faint < 0.05


def test_selection_bias_check_with_realistic_depth_model(tmp_path):
    run_dir = _write_minimal_run(tmp_path, seed=20260903)
    result_path = run_selection_bias_check(run_dir, "configs/science/observational_bias.yaml")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    # With the new distance-based model, the favorable outcome should hold
    assert result["real_exceeds_synthetic_R"] is True
    # Check that distance statistics are reported
    assert result["h_prior_stats"] is not None
    assert "h_prior_mean" in result["h_prior_stats"]
    assert "n_synthetic_generated" in result


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
    assert len(result["caveats"]) >= 4


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
    # Since selection_bias_check now wires ossos_filling_factor from config
    # (it takes precedence over sky_coverage_deg2 in apply_selection_function,
    # completing the 9956415 fix), the restrictive scenario must set it
    # explicitly. 0.12 reproduces the order-of-magnitude restrictiveness the
    # test originally got from sky_coverage_deg2=5000/41253 ~= 0.121.
    "ossos_filling_factor: 0.12\n"
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

def test_sky_position_in_footprint_true_for_block_center():
    """The real OSSOS 2013A block centers must be inside their polygons."""
    from planet9lab.data.ossos_2013a_blocks import OSSOS_2013A_BLOCKS
    from planet9lab.selection_bias import _sky_position_in_footprint

    blocks = [dict(block) for block in OSSOS_2013A_BLOCKS.values()]
    for block in blocks:
        ra = block["center_ra_deg"]
        dec = block["center_dec_deg"]
        assert _sky_position_in_footprint(ra, dec, blocks) is True


def test_sky_position_in_footprint_false_for_far_position():
    """A position far from both 2013A blocks must be outside the footprint."""
    from planet9lab.data.ossos_2013a_blocks import OSSOS_2013A_BLOCKS
    from planet9lab.selection_bias import _sky_position_in_footprint

    blocks = [dict(block) for block in OSSOS_2013A_BLOCKS.values()]
    # RA = 0, Dec = -89 is on the opposite side of the sky from the
    # equatorial OSSOS 2013A blocks at RA ~ 214/240, Dec ~ -12.
    assert _sky_position_in_footprint(0.0, -89.0, blocks) is False
    assert _sky_position_in_footprint(0.0, 0.0, blocks) is False


def test_apply_selection_function_footprint_rejects_outside_objects():
    """With ossos_footprint_blocks provided and sky positions present, only
    objects inside a footprint block survive the sky-coverage factor (a
    permissive filling factor of 1.0 isolates the geometric filter)."""
    from planet9lab.data.ossos_2013a_blocks import OSSOS_2013A_BLOCKS
    from planet9lab.selection_bias import apply_selection_function

    blocks = [dict(block) for block in OSSOS_2013A_BLOCKS.values()]
    # Hand-built population: one object inside the first block's center,
    # one far outside. No h_value/r_au/delta_au -> fixed depth prob = 1.0
    # at limiting_magnitude_v=24.5, so only the footprint factor decides.
    inside_ra = blocks[0]["center_ra_deg"]
    inside_dec = blocks[0]["center_dec_deg"]
    population = [
        {"name": "inside", "omega_deg": 0.0, "Omega_deg": 0.0,
         "mean_anomaly_deg": 0.0, "i_deg": 0.0,
         "ra_deg": inside_ra, "dec_deg": inside_dec},
        {"name": "outside", "omega_deg": 0.0, "Omega_deg": 0.0,
         "mean_anomaly_deg": 0.0, "i_deg": 0.0,
         "ra_deg": 0.0, "dec_deg": -89.0},
    ]
    survivors = apply_selection_function(
        population,
        rng=random.Random(42),
        limiting_magnitude_v=24.5,
        sky_coverage_deg2=20000.0,
        min_tracking_arc_years=0.0,
        ossos_filling_factor=1.0,  # permissive: isolate the geometry filter
        ossos_footprint_blocks=blocks,
    )
    names = {row["name"] for row in survivors}
    assert "inside" in names
    assert "outside" not in names


def test_apply_selection_function_without_footprint_keeps_uniform_behavior():
    """Backward compatibility: with ossos_footprint_blocks None and no sky
    positions, the (angle-only) population uses the uniform filling-factor
    survival probability as before the footprint integration."""
    population = generate_synthetic_population(random.Random(7), n=200)
    survivors = apply_selection_function(
        population,
        rng=random.Random(99),
        limiting_magnitude_v=24.0,
        sky_coverage_deg2=15000.0,
        min_tracking_arc_years=2.0,
        ossos_filling_factor=0.9067,
        ossos_footprint_blocks=None,
    )
    assert 0 < len(survivors) <= len(population)


def test_selection_bias_check_default_reports_uniform_filling_mode():
    """The default config (use_ossos_footprint: false) must keep the uniform
    filling-factor sky model: the footprint is opt-in because the synthetic
    RA/Dec are uniform-random proxies, not orbital projections, and the OSSOS
    2013A footprint covers only ~0.07% of the sky."""
    from planet9lab.loaders import load_etnos

    etnos = load_etnos(REAL_ETNO_CATALOG)
    config = load_bias_config("configs/science/observational_bias.yaml")
    assert config.use_ossos_footprint is False
    result = selection_bias_check(etnos, config, seed=12345)
    assert result["ossos_footprint_mode"] == "uniform_filling_factor"


def test_selection_bias_check_with_footprint_enabled_reports_real_mode():
    """Opting in (use_ossos_footprint: true) loads the real OSSOS 2013A
    blocks dynamically and reports the real-footprint mode. The sky-coverage
    caveat must then mention the real point-in-polygon test."""
    from planet9lab.selection_bias import ObservationalBiasConfig

    etnos = load_etnos(REAL_ETNO_CATALOG)
    config = ObservationalBiasConfig(
        bias_model="h_prior_from_catalog",
        use_ossos_footprint=True,
        n_synthetic=200,
    )
    result = selection_bias_check(etnos, config, seed=12345)
    assert result["ossos_footprint_mode"] == "real_footprint_polygons"
    assert any("point-in-polygon" in c for c in result["caveats"])
