"""Gate tests for the separate sensitivity experiments.

These assert the experiment configs are well-formed and that the variant
builder produces the expected grid from them - so a silent breakage in the
experiment wiring fails fast instead of producing a wrong grid at run time.
They do NOT run the pipeline (no execute_run here).
"""
import importlib.util
from pathlib import Path

import pytest

from planet9lab.config import load_yaml

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = ROOT / "configs" / "experiments"


def _load_driver():
    driver = ROOT / "scripts" / "experiments" / "run_grid_experiment.py"
    spec = importlib.util.spec_from_file_location("run_grid_experiment", driver)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


@pytest.fixture(scope="module")
def configs():
    return {
        "angle_robustness": load_yaml(EXPERIMENTS_DIR / "angle_robustness.yaml"),
        "i_boundary_scan": load_yaml(EXPERIMENTS_DIR / "i_boundary_scan.yaml"),
    }


@pytest.mark.parametrize("name", ["angle_robustness", "i_boundary_scan"])
def test_experiment_config_is_well_formed(configs, name):
    experiment = configs[name]
    assert experiment["experiment_id"]
    assert experiment["base_catalog"]
    assert experiment["budget"]
    assert experiment.get("seed")
    assert experiment["axes"]

    base = ROOT / experiment["base_catalog"]
    budget = ROOT / experiment["budget"]
    assert base.is_file(), f"base_catalog not found: {base}"
    assert budget.is_file(), f"budget not found: {budget}"
    if experiment.get("etno_catalog"):
        assert (ROOT / experiment["etno_catalog"]).is_file(), "etno_catalog not found"
    for values in experiment["axes"].values():
        assert all(isinstance(value, (int, float)) for value in values)


def test_angle_robustness_grid_shape(driver, configs):
    from planet9lab.loaders import load_candidates

    experiment = configs["angle_robustness"]
    base = load_candidates(ROOT / experiment["base_catalog"])
    variants = driver.build_variants(base, experiment["axes"])

    assert len(base) == 1, "Cenario 6 robustness test should sweep a single base candidate"
    assert len(variants) == len(base) * 5
    ids = [variant.candidate_id for variant in variants]
    assert len(ids) == len(set(ids)), "variant ids must be unique"

    omega_values = {variant.omega_deg for variant in variants}
    assert omega_values == {0, 90, 180, 200, 270}
    assert all(variant.Omega_deg == b.Omega_deg for b in base for variant in variants if variant.candidate_id.startswith(b.candidate_id))


def test_angle_robustness_keeps_non_swept_elements(driver, configs):
    from planet9lab.loaders import load_candidates

    experiment = configs["angle_robustness"]
    base = load_candidates(ROOT / experiment["base_catalog"])
    variants = driver.build_variants(base, experiment["axes"])
    by_base = {}
    for variant in variants:
        by_base.setdefault(variant.candidate_id.split("__")[0], []).append(variant)

    for original in base:
        for variant in by_base[original.candidate_id]:
            assert variant.mass_earth == original.mass_earth
            assert variant.a_au == original.a_au
            assert variant.e == original.e
            assert variant.Omega_deg == original.Omega_deg
            assert variant.mean_anomaly_deg == original.mean_anomaly_deg


def test_i_boundary_scan_shape(driver, configs):
    from planet9lab.loaders import load_candidates

    experiment = configs["i_boundary_scan"]
    base = load_candidates(ROOT / experiment["base_catalog"])
    assert len(base) == 1
    variants = driver.build_variants(base, experiment["axes"])

    assert len(variants) == 5
    assert {variant.i_deg for variant in variants} == {31, 32, 33, 34, 35}
    assert len({variant.candidate_id for variant in variants}) == 5
    for variant in variants:
        assert variant.omega_deg == base[0].omega_deg
        assert variant.Omega_deg == base[0].Omega_deg
        assert variant.a_au == base[0].a_au
