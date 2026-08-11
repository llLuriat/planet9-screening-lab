import numpy as np

from planet9lab.montecarlo import (
    FILTER_COLUMNS,
    halton_points,
    sample_parameter_space,
    stage0_physical_bounds,
    stage1_hill_separation_proxy,
)


def test_halton_points_are_deterministic_and_in_unit_box():
    a = halton_points(50, 4)
    b = halton_points(50, 4)
    assert np.array_equal(a, b)
    assert a.shape == (50, 4)
    assert (a >= 0).all() and (a < 1).all()


def test_halton_points_cover_more_than_a_single_corner():
    points = halton_points(200, 2)
    # A degenerate/buggy sequence could collapse to a line or a point; check
    # basic spread across the unit square instead.
    assert points[:, 0].std() > 0.1
    assert points[:, 1].std() > 0.1


def test_sample_parameter_space_respects_configured_bounds():
    config = {
        "bounds": {
            "mass_earth": [5.0, 20.0],
            "a_au": [380.0, 980.0],
            "e": [0.1, 0.8],
            "i_deg": [0.0, 40.0],
        },
        "method": "qmc_halton",
        "n_points": 300,
    }
    samples = sample_parameter_space(config)
    assert len(samples) == 300
    for point in samples:
        assert 5.0 <= point["mass_earth"] <= 20.0
        assert 380.0 <= point["a_au"] <= 980.0
        assert 0.1 <= point["e"] <= 0.8
        assert 0.0 <= point["i_deg"] <= 40.0


def test_sample_parameter_space_uniform_random_is_seed_reproducible():
    config = {
        "bounds": {"mass_earth": [5.0, 20.0], "a_au": [380.0, 980.0], "e": [0.1, 0.8], "i_deg": [0.0, 40.0]},
        "method": "uniform_random",
        "seed": 42,
        "n_points": 20,
    }
    first = sample_parameter_space(config)
    second = sample_parameter_space(config)
    assert first == second


def test_stage0_rejects_unphysical_points():
    bad = stage0_physical_bounds({"a_au": -5.0, "e": 0.3, "mass_earth": 10.0})
    assert bad["pass"] is False
    good = stage0_physical_bounds({"a_au": 600.0, "e": 0.3, "mass_earth": 10.0})
    assert good["pass"] is True
    assert good["perihelion_au"] == 600.0 * 0.7


def test_stage0_flags_literature_perihelion_band():
    # perihelion = a*(1-e); pick values landing inside vs outside 150-350 AU.
    inside = stage0_physical_bounds({"a_au": 500.0, "e": 0.5, "mass_earth": 10.0})  # q=250
    outside = stage0_physical_bounds({"a_au": 900.0, "e": 0.1, "mass_earth": 10.0})  # q=810
    assert inside["within_literature_perihelion_band"] is True
    assert outside["within_literature_perihelion_band"] is False


def test_stage1_hill_proxy_passes_for_typical_p9_separation():
    # A typical sampled point (a~600, e~0.4, far from Neptune's 30 AU) should
    # pass easily - this filter mainly exists to catch pathological corners.
    result = stage1_hill_separation_proxy({"a_au": 600.0, "e": 0.4, "mass_earth": 10.0})
    assert result["pass"] is True
    assert result["hill_radii_separation"] > 3.0


def test_filter_columns_match_documented_stages():
    assert FILTER_COLUMNS == [
        "stage0_physical_bounds",
        "stage1_hill_separation_proxy",
        "stage2_gross_stability",
        "stage3_apsidal_alignment",
        "stage4_secular_hamiltonian",
        "stage5_detectability_ir_optical",
    ]
