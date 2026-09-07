from planet9lab.loaders import load_budget, load_giants
from planet9lab.physics import recommended_timestep_years


def test_secular_budget_loads_and_has_checkpointing():
    budget = load_budget("configs/budgets/secular.yaml")
    assert budget.integration_years >= 1e8
    assert budget.checkpoint_interval_years is not None
    assert budget.checkpoint_interval_years <= budget.integration_years


def test_secular_timestep_matches_derivation_from_giants_catalog():
    giants = load_giants("data/solar_system/giants_epoch.csv")
    derived = recommended_timestep_years(giants)
    budget = load_budget("configs/budgets/secular.yaml")
    # The yaml file documents the derivation in comments; this test guarantees
    # the file cannot silently drift away from the code that justifies it.
    assert abs(derived["recommended_timestep_years"] - budget.timestep_years) < 1e-3
    assert derived["shortest_period_body"] == "Jupiter"


def test_checkpoint_interval_cannot_exceed_integration_years():
    from pydantic import ValidationError

    from planet9lab.schemas import BudgetConfig

    failed = False
    try:
        BudgetConfig(
            integration_years=100.0,
            timestep_years=0.5,
            seeds=[1],
            max_candidates=1,
            checkpoint_interval_years=200.0,
        )
    except ValidationError:
        failed = True
    assert failed is True
