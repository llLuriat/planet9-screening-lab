from planet9lab.metrics import delta_pomega_instant, delta_pomega_stability


def test_librating_series_is_classified_stable():
    # Delta_pomega oscillates around 180 deg with small amplitude: librating.
    series = [175.0, 180.0, 185.0, 178.0, 182.0, 179.0, 181.0, 176.0]
    result = delta_pomega_stability({"etno_a": series})
    assert result["per_etno"]["etno_a"]["classification"] == "librating_stable"
    assert result["delta_pomega_stable_fraction"] == 1.0


def test_circulating_series_is_classified_unstable():
    # Delta_pomega sweeps through the full circle, twice, so that the SECOND
    # HALF of the series (the part the criterion actually evaluates) also
    # covers the full circle uniformly: genuinely circulating, not apsidally
    # confined. (A single sweep would leave only a quarter-circle arc in the
    # second half, which is not a fair test of "circulating".)
    sweep = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
    series = sweep + sweep
    result = delta_pomega_stability({"etno_b": series})
    assert result["per_etno"]["etno_b"]["classification"] == "circulating_unstable"
    assert result["delta_pomega_stable_fraction"] == 0.0


def test_short_series_marked_insufficient_data():
    result = delta_pomega_stability({"etno_c": [10.0, 12.0]})
    assert result["per_etno"]["etno_c"]["classification"] == "insufficient_data"
    # insufficient-data candidates are excluded from the evaluated fraction, not
    # silently counted as stable or unstable.
    assert result["evaluated_count"] == 0
    assert result["delta_pomega_stable_fraction"] is None


def test_mixed_population_fraction():
    librating = [175.0, 180.0, 185.0, 178.0, 182.0, 179.0] * 2
    circ_sweep = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    circulating = circ_sweep + circ_sweep
    result = delta_pomega_stability({"a": librating, "b": circulating})
    assert result["evaluated_count"] == 2
    assert result["stable_count"] == 1
    assert result["delta_pomega_stable_fraction"] == 0.5


def test_delta_pomega_instant_none_without_p9():
    assert delta_pomega_instant([{"name": "x", "omega_deg": 10, "Omega_deg": 20}], None) is None


def test_delta_pomega_instant_computes_relative_angle():
    etnos = [{"name": "x", "omega_deg": 10.0, "Omega_deg": 20.0}]
    p9 = {"omega_deg": 100.0, "Omega_deg": 50.0}
    result = delta_pomega_instant(etnos, p9)
    # (10+20) - (100+50) = -120 -> normalized to 240
    assert abs(result["x"] - 240.0) < 1e-6
