from planet9lab.engine import ReboundEngine, ReboundUnavailable
from planet9lab.loaders import included_etnos, load_budget, load_candidates, load_etnos, load_giants


def test_control_pair_generates_both_branches():
    budget = load_budget("configs/budgets/low.yaml")
    engine = ReboundEngine(budget, 123, load_giants("data/solar_system/giants_epoch.csv"))
    pair = engine.run_control_pair(
        included_etnos(load_etnos("data/etnos/catalog.csv")),
        load_candidates("data/candidates_example.csv", 1)[0],
        {
            "apsidal_clustering": 0.2,
            "anti_alignment": 0.25,
            "survival_rate": 0.2,
            "stability": 0.2,
            "numerical_health": 0.15,
        },
    )
    assert pair["with_p9"]["result"]["branch"] == "with_p9"
    assert pair["without_p9"]["result"]["branch"] == "without_p9"


def test_no_rebound_without_fallback_fails_honestly():
    import planet9lab.engine as engine_module

    original = engine_module.rebound_available
    engine_module.rebound_available = lambda: False
    try:
        failed = False
        try:
            ReboundEngine(load_budget("configs/budgets/low.yaml"), 1, [], False)
        except ReboundUnavailable:
            failed = True
        assert failed is True
    finally:
        engine_module.rebound_available = original


def test_no_rebound_with_fallback_marks_invalid():
    import planet9lab.engine as engine_module

    original = engine_module.rebound_available
    engine_module.rebound_available = lambda: False
    try:
        engine = ReboundEngine(load_budget("configs/budgets/low.yaml"), 1, [], True)
        assert engine.rebound_available is False
    finally:
        engine_module.rebound_available = original

