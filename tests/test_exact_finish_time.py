"""Etapa 2 regression: `_run_rebound` must integrate with exact_finish_time=0,
matching `run_branch_checkpointed` and `scripts/benchmark_integration_cost.py`.

REBOUND's default is exact_finish_time=1, which snaps the final step so the
trajectory ends exactly at the requested target time. With exact_finish_time=0
the last step is not adjusted: on budgets where integration_years is not an
exact multiple of the timestep the trajectory ends slightly past the target
and the energy drift changes by a small, bounded amount.

Documented magnitude (budget integration_years=100 yr, timestep=0.593644 yr,
data/solar_system/giants_epoch.csv, data/etnos/catalog.csv, first candidate of
data/candidates_example.csv):

    |delta energy_drift_rel| ~= 1.6e-07
    delta t_final          ~= 0.33 yr

On budgets where integration_years IS an exact multiple of the timestep (e.g.
configs/budgets/low.yaml: 50 yr / 0.5 yr = integer steps) the change is exactly
zero, because the default already terminates on the same step boundary.
"""

from planet9lab.engine import ReboundEngine
from planet9lab.loaders import (
    included_etnos,
    load_budget,
    load_candidates,
    load_etnos,
    load_giants,
)
from planet9lab.schemas import BudgetConfig

NON_ALIGNED_BUDGET = dict(
    integration_years=100,
    timestep_years=0.593644,
    seeds=[12345],
    integrator="whfast",
    max_candidates=5,
)


def _drift_and_final_time(engine, candidate, etnos, exact_finish_time):
    sim = engine._configure_sim(etnos, candidate, include_p9=True)
    energy_initial = sim.energy()
    sim.integrate(engine.budget.integration_years, exact_finish_time=exact_finish_time)
    energy_final = sim.energy()
    drift = abs((energy_final - energy_initial) / energy_initial)
    return drift, sim.t


def _engine_and_inputs(budget):
    engine = ReboundEngine(budget, 123, load_giants("data/solar_system/giants_epoch.csv"))
    candidate = load_candidates("data/candidates_example.csv", 1)[0]
    etnos = included_etnos(load_etnos("data/etnos/catalog.csv"))
    return engine, candidate, etnos


def test_run_rebound_standardized_to_exact_finish_time_zero():
    budget = BudgetConfig.model_validate(NON_ALIGNED_BUDGET)
    engine, candidate, etnos = _engine_and_inputs(budget)

    new_drift, new_t = _drift_and_final_time(engine, candidate, etnos, exact_finish_time=0)
    old_drift, old_t = _drift_and_final_time(engine, candidate, etnos, exact_finish_time=1)

    run_drift = float(
        engine._run_rebound(etnos, candidate, include_p9=True)["health"]["energy_drift_rel"]
    )
    assert run_drift == new_drift

    assert abs(new_drift - old_drift) > 0.0
    assert abs(new_t - old_t) > 1e-9
    assert abs(new_drift - old_drift) < 1e-5


def test_exact_finish_time_delta_is_zero_on_aligned_budget():
    budget = load_budget("configs/budgets/low.yaml")
    engine, candidate, etnos = _engine_and_inputs(budget)

    new_drift, _ = _drift_and_final_time(engine, candidate, etnos, exact_finish_time=0)
    old_drift, _ = _drift_and_final_time(engine, candidate, etnos, exact_finish_time=1)

    assert new_drift == old_drift
