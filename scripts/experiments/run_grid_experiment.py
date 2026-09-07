"""Run a grid/sweep sensitivity experiment (angle_robustness, i_boundary_scan).

This script turns a base candidate catalog into a grid of variants by crossing
it with one or more orbital-element axes, then screens the variants through the
standard execute_run pipeline. It adds no physics and no pipeline behavior: it
only generates candidate variants from the experiment's YAML config and reuses
the existing screening machinery.

Usage:
    python scripts/experiments/run_grid_experiment.py <config> \
        [--seed N] [--run-root DIR] [--budget-override PATH]
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from planet9lab.config import load_yaml  # noqa: E402
from planet9lab.loaders import load_candidates  # noqa: E402
from planet9lab.run import execute_run  # noqa: E402

AXIS_LABELS = {
    "i_deg": "i",
    "omega_deg": "omega",
    "Omega_deg": "Omega",
    "mean_anomaly_deg": "M0",
}


def _label(axis: str, value: float) -> str:
    prefix = AXIS_LABELS.get(axis, axis)
    return f"{prefix}{int(value)}"


def build_variants(base_candidates, axes: dict[str, list[float]]):
    """Cross every base candidate with the cartesian product of the axis
    values, overriding only the swept elements and keeping all others at the
    base candidate's own values. Each variant gets a unique candidate_id."""
    axis_names = list(axes)
    value_sets = [axes[name] for name in axis_names]
    variants: list = []
    for base, combo in itertools.product(base_candidates, itertools.product(*value_sets)):
        overrides = dict(zip(axis_names, combo))
        data = base.model_dump()
        data.update(overrides)
        suffix = "_".join(_label(name, value) for name, value in overrides.items())
        data["candidate_id"] = f"{base.candidate_id}__{suffix}"
        variants.append(type(base).model_validate(data))
    return variants


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument(
        "--budget-override",
        type=Path,
        default=None,
        help="Test-only affordance: run the exact same driver against a cheaper "
        "budget to verify wiring before the production run.",
    )
    args = parser.parse_args()

    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    experiment = load_yaml(config_path)
    base_catalog = experiment["base_catalog"]
    if not Path(base_catalog).is_absolute():
        base_catalog = ROOT / base_catalog
    budget = experiment["budget"] if args.budget_override is None else args.budget_override
    if not Path(budget).is_absolute():
        budget = ROOT / budget
    seed = args.seed if args.seed is not None else experiment.get("seed", 12345)
    etno_catalog = experiment.get("etno_catalog")
    if etno_catalog is not None and not Path(etno_catalog).is_absolute():
        etno_catalog = ROOT / etno_catalog

    base_candidates = load_candidates(base_catalog)
    variants = build_variants(base_candidates, experiment["axes"])

    run_dir = execute_run(
        candidates=variants,
        budget_path=budget,
        seed=seed,
        command_name="experiment_" + experiment["experiment_id"],
        replay_args=["experiment", str(config_path), "--seed", str(seed)],
        run_root=args.run_root,
        etno_catalog=etno_catalog,
    )

    # execute_run writes a "python main.py ..." replay line by default; these
    # experiments are driven by this script, so record the truthful command.
    (run_dir / "replay_command.txt").write_text(
        f"python scripts/experiments/run_grid_experiment.py {config_path} "
        f"--seed {seed}\n",
        encoding="utf-8",
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
