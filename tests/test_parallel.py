"""Etapa 1 regression: parallel execution must not change any science output.

The mandatory sequential-vs-parallel test: running the same screen on
configs/budgets/low.yaml with max_workers=1 and max_workers>1 must produce
byte-identical candidate-level artifacts (ranking, metrics, control pairs,
candidate order, result cache, manifests). The only things that legitimately
differ between two runs are wall-clock timestamps and the run_id (which embeds
a timestamp), so those files are excluded/normalized below.
"""

import csv
import json

from planet9lab.parallel import resolve_max_workers, run_parallel_map

DETERMINISTIC_ARTIFACTS = [
    "candidates_results_cache.json",
    "results/ranking.csv",
    "results/metrics_by_candidate.csv",
    "results/control_pairs.csv",
    "results/top_candidates.csv",
    "results/rejected_candidates.csv",
    "results/numerical_failures.csv",
    "results/ranking_summary.json",
    "results/seed_stability_summary.json",
    "presentation/top10_table.csv",
    "audit/blockers.json",
    "audit/hashes.json",
]

# These embed wall-clock timestamps and/or the timestamped run_id.
TIMESTAMP_BEARING_ARTIFACTS = [
    "audit/run_manifest.json",
    "reports/report.md",
    "presentation/summary_for_presentation.md",
]


def _normalized_status_rows(path):
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for row in rows:
        row.pop("started_at", None)
        row.pop("ended_at", None)
    return sorted(rows, key=lambda row: row["candidate_id"])


def test_sequential_and_parallel_are_byte_identical_on_low_budget(tmp_path):
    import planet9lab.run as run_module

    old_runs_dir = run_module.RUNS_DIR
    run_module.RUNS_DIR = tmp_path
    try:
        sequential = run_module.run_screen("configs/budgets/low.yaml", 12345, max_workers=1)
        parallel = run_module.run_screen("configs/budgets/low.yaml", 12345, max_workers=2)
    finally:
        run_module.RUNS_DIR = old_runs_dir

    for rel in DETERMINISTIC_ARTIFACTS:
        seq_bytes = (sequential / rel).read_bytes()
        par_bytes = (parallel / rel).read_bytes()
        assert seq_bytes == par_bytes, f"{rel} diverged between sequential and parallel"

    # candidates_status.csv carries wall-clock started_at/ended_at; everything
    # else in it must match.
    assert _normalized_status_rows(sequential / "candidates_status.csv") == _normalized_status_rows(
        parallel / "candidates_status.csv"
    )

    # Candidate order is part of the DoD: ranking rows must be identical.
    seq_ranking = (sequential / "results/ranking.csv").read_text(encoding="utf-8")
    assert seq_ranking == (parallel / "results/ranking.csv").read_text(encoding="utf-8")
    seq_ids = [row["candidate_id"] for row in csv.DictReader(seq_ranking.splitlines())]
    assert seq_ids == [row["candidate_id"] for row in csv.DictReader((parallel / "results/ranking.csv").open())]

    # Timestamp-bearing artifacts must differ only in run_id/timestamp, not in
    # any scientific field.
    seq_manifest = json.loads((sequential / "audit/run_manifest.json").read_text(encoding="utf-8"))
    par_manifest = json.loads((parallel / "audit/run_manifest.json").read_text(encoding="utf-8"))
    for key in set(seq_manifest) | set(par_manifest):
        if key in {"run_id", "timestamp"}:
            continue
        assert seq_manifest[key] == par_manifest[key], f"manifest field {key} diverged"


def test_run_parallel_map_preserves_input_order():
    results = run_parallel_map(_double, [1, 2, 3, 4, 5], max_workers=1)
    assert results == [2, 4, 6, 8, 10]
    results = run_parallel_map(_double, [1, 2, 3, 4, 5], max_workers=2)
    assert results == [2, 4, 6, 8, 10]


def _double(x):
    return x * 2


def test_run_parallel_map_runs_initializer_on_sequential_fallback():
    state = {}

    def init(payload):
        state.update(payload)

    def worker(x):
        return state["base"] + x

    results = run_parallel_map(worker, [1, 2, 3], max_workers=1, initializer=init, initargs=({"base": 10},))
    assert results == [11, 12, 13]


def test_resolve_max_workers_handles_override(monkeypatch):
    monkeypatch.delenv("PLANET9_MAX_WORKERS", raising=False)
    assert resolve_max_workers(3) == 3
    assert resolve_max_workers(0) == 1
    monkeypatch.setenv("PLANET9_MAX_WORKERS", "7")
    assert resolve_max_workers() == 7
    monkeypatch.setenv("PLANET9_MAX_WORKERS", "not-a-number")
    assert resolve_max_workers(4) == 4


def test_montecarlo_scan_sequential_and_parallel_identical(tmp_path, monkeypatch):
    """Stage 2/3 of the funnel must produce byte-identical funnel CSVs whether
    run sequentially or in parallel. secular.yaml is NOT exercised here (the
    budget loader is stubbed with the cheap low.yaml budget) so this test
    never performs a secular/Gyr integration."""
    import yaml

    from planet9lab import montecarlo as mc_module
    from planet9lab.loaders import load_budget

    config = {
        "bounds": {"mass_earth": [5.0, 20.0], "a_au": [380.0, 980.0], "e": [0.1, 0.8], "i_deg": [0.0, 40.0]},
        "method": "qmc_halton",
        "seed": 20260727,
        "n_points": 12,
        "max_stage2_samples": 6,
        "max_stage3_samples": 4,
        "stage2_budget": "configs/budgets/montecarlo_stage2.yaml",
    }
    config_path = tmp_path / "small_mc.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    def cheap_budget(_path):
        return load_budget("configs/budgets/low.yaml")

    monkeypatch.setattr(mc_module, "load_budget", cheap_budget)

    import planet9lab.run as run_module

    old_runs_dir = run_module.RUNS_DIR
    run_module.RUNS_DIR = tmp_path
    try:
        seq_dir = run_module.run_montecarlo_scan(str(config_path), seed=20260727, max_workers=1)
        par_dir = run_module.run_montecarlo_scan(str(config_path), seed=20260727, max_workers=2)
    finally:
        run_module.RUNS_DIR = old_runs_dir

    for rel in [
        "results/parameter_space_scan.csv",
        "results/reduction_funnel_summary.json",
    ]:
        assert (seq_dir / rel).read_bytes() == (par_dir / rel).read_bytes(), f"{rel} diverged"


def _run_screen_pair(tmp_path):
    import planet9lab.run as run_module

    old_runs_dir = run_module.RUNS_DIR
    run_module.RUNS_DIR = tmp_path
    try:
        seq_dir = run_module.run_screen("configs/budgets/low.yaml", 12345, max_workers=1)
        par_dir = run_module.run_screen("configs/budgets/low.yaml", 12345, max_workers=2)
    finally:
        run_module.RUNS_DIR = old_runs_dir
    return seq_dir, par_dir


def test_robustness_sequential_and_parallel_identical(tmp_path):
    from planet9lab.robustness import convergence, leave_one_out, null_models, validate_top

    seq_dir, par_dir = _run_screen_pair(tmp_path)

    cases = [
        (leave_one_out, {"top": 2}, ["robustness/leave_one_out.csv", "robustness/leave_one_out_summary.json"]),
        (convergence, {"top": 2}, ["robustness/convergence.csv", "robustness/convergence_summary.json"]),
        (
            validate_top,
            {"top": 2, "integrator": "ias15"},
            ["validation/ias15_validation.csv", "validation/ias15_summary.json"],
        ),
        (
            null_models,
            {"top": 2, "n_shuffles": 3, "models": "shuffle_varpi"},
            [
                "robustness/null_models.csv",
                "robustness/null_model_percentiles.csv",
                "robustness/null_models_summary.json",
            ],
        ),
    ]
    for func, kwargs, artifacts in cases:
        func(seq_dir, max_workers=1, **kwargs)
        func(par_dir, max_workers=2, **kwargs)
        for artifact in artifacts:
            assert (seq_dir / artifact).read_bytes() == (par_dir / artifact).read_bytes(), (
                f"{artifact} diverged for {func.__name__}"
            )


def test_validate_top_parallel_writes_validation_dir(tmp_path):
    from planet9lab.robustness import validate_top

    _seq_dir, par_dir = _run_screen_pair(tmp_path)
    validate_top(par_dir, top=2, max_workers=2)
    assert (par_dir / "validation" / "ias15_validation.csv").exists()
    assert (par_dir / "validation" / "ias15_summary.json").exists()
