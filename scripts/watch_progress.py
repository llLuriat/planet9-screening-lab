"""Live progress monitor for a running (or finished) screen/montecarlo-scan run.

Reads the checkpoint drift-series CSVs under runs/<run_id>/checkpoints/ (or
runs/<run_id>/montecarlo_checkpoints/) and status.json/heartbeat.json, and
prints a refreshing table of how far each candidate/branch has integrated,
with an estimated time remaining. Safe to run in a second terminal while
`python main.py screen ...` is running in another - it only reads files, it
never writes to the run directory.

Usage
-----
    python scripts/watch_progress.py                     # watches the latest run
    python scripts/watch_progress.py --run-dir runs/screen_20260728T014825Z
    python scripts/watch_progress.py --interval 30        # refresh every 30s (default 15)
    python scripts/watch_progress.py --once                # print once and exit (no loop)

Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_run_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    latest_pointer = ROOT / "runs" / "latest_run.txt"
    if not latest_pointer.exists():
        raise SystemExit("runs/latest_run.txt not found; pass --run-dir explicitly.")
    return Path(latest_pointer.read_text(encoding="utf-8").strip())


def read_yaml(path: Path) -> dict:
    import yaml

    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> dict:
    import json

    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def last_csv_row(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (FileNotFoundError, OSError):
        return None
    return rows[-1] if rows else None


def format_duration(seconds: float) -> str:
    if seconds != seconds or seconds in (float("inf"), float("-inf")):  # NaN/inf guard
        return "?"
    seconds = max(0, seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{int(days)}d")
    if hours or days:
        parts.append(f"{int(hours)}h")
    parts.append(f"{int(minutes)}m")
    return " ".join(parts)


def build_report(run_dir: Path) -> str:
    lines = []
    status = read_json(run_dir / "status.json")
    heartbeat = read_json(run_dir / "heartbeat.json")
    config = read_yaml(run_dir / "config.resolved.yaml")
    budget = config.get("budget", {})
    integration_years = budget.get("integration_years")

    lines.append(f"Run: {run_dir.name}")
    lines.append(
        f"  status={status.get('status', '?')}  stage={status.get('current_stage', '?')}  "
        f"candidates {status.get('candidates_done', '?')}/{status.get('candidates_total', '?')}  "
        f"failed={status.get('candidates_failed', 0)}"
    )
    if heartbeat.get("timestamp"):
        lines.append(f"  last heartbeat: {heartbeat['timestamp']}")
    if integration_years:
        lines.append(f"  integration_years target (per branch): {integration_years:,.0f}")
    else:
        lines.append("  (no integration_years found in config.resolved.yaml - not a checkpointed run?)")
    lines.append("")

    checkpoint_dirs = [run_dir / "checkpoints", run_dir / "montecarlo_checkpoints"]
    any_series = False
    for checkpoint_dir in checkpoint_dirs:
        if not checkpoint_dir.exists():
            continue
        series_files = sorted(checkpoint_dir.glob("*_drift_series.csv"))
        if not series_files:
            continue
        any_series = True
        header = f"{'candidate/branch':40} {'t_years':>14} {'%':>7} {'ETA':>10} {'last write':>12}"
        lines.append(header)
        lines.append("-" * len(header))
        now = time.time()
        for series_path in series_files:
            name = series_path.name.replace("_drift_series.csv", "")
            row = last_csv_row(series_path)
            if row is None:
                lines.append(f"{name:40} {'(no data yet)':>14}")
                continue
            t_years = float(row["t_years"])
            mtime = series_path.stat().st_mtime
            age_s = now - mtime
            pct = (t_years / integration_years * 100) if integration_years else None
            pct_str = f"{pct:6.2f}%" if pct is not None else "?"

            eta_str = "?"
            if integration_years and t_years > 0:
                # Rate estimated from the file's creation time to now (approx:
                # first checkpoint write happens shortly after t=0). This is
                # an estimate, not an exact figure - REBOUND integration speed
                # can vary somewhat as particles get lost/stable etc.
                created = series_path.stat().st_ctime
                elapsed_wall = max(now - created, 1e-6)
                rate_years_per_sec = t_years / elapsed_wall
                remaining_years = integration_years - t_years
                if rate_years_per_sec > 0:
                    eta_seconds = remaining_years / rate_years_per_sec
                    eta_str = format_duration(eta_seconds) if remaining_years > 0 else "done"
            age_str = f"{int(age_s)}s ago" if age_s < 120 else format_duration(age_s) + " ago"
            lines.append(f"{name:40} {t_years:14,.0f} {pct_str:>7} {eta_str:>10} {age_str:>12}")
        lines.append("")

    if not any_series:
        lines.append(
            "No *_drift_series.csv found yet under checkpoints/ - either the run has not "
            "reached its first checkpoint, or it is not using a checkpointed budget "
            "(check checkpoint_interval_years in config.resolved.yaml)."
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--interval", type=float, default=15.0, help="seconds between refreshes")
    parser.add_argument("--once", action="store_true", help="print once and exit, no loop")
    args = parser.parse_args()

    run_dir = find_run_dir(args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")

    try:
        while True:
            report = build_report(run_dir)
            if not args.once:
                os.system("cls" if os.name == "nt" else "clear")
            print(report)
            if args.once:
                break
            print(f"\n(refreshing every {args.interval:.0f}s - Ctrl+C to stop)")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
