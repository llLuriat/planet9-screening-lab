from __future__ import annotations

import csv
import json
import math
from pathlib import Path

REQUIRED_FILES = [
    "SUCCESS.marker|INVALID.marker|FAILED.marker",
    "status.json",
    "heartbeat.json",
    "events.log",
    "config.resolved.yaml",
    "replay_command.txt",
    "environment.json",
    "data_manifest.json",
    "candidates_input.csv",
    "candidates_status.csv",
    "results/ranking.csv",
    "results/metrics_by_candidate.csv",
    "results/control_pairs.csv",
    "results/ranking_summary.json",
    "results/top_candidates.csv",
    "results/rejected_candidates.csv",
    "results/numerical_failures.csv",
    "audit/run_manifest.json",
    "audit/blockers.json",
    "audit/hashes.json",
    "reports/report.md",
    "presentation/summary_for_presentation.md",
    "presentation/top10_table.csv",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def bad_number(value: str) -> bool:
    if value in {"", None}:
        return False
    lowered = str(value).strip().lower()
    if lowered in {"nan", "inf", "-inf", "infinity", "-infinity"}:
        return True
    try:
        return not math.isfinite(float(lowered))
    except ValueError:
        return False


def audit_run(run_dir: str | Path) -> tuple[bool, list[str]]:
    run_dir = Path(run_dir)
    issues: list[str] = []
    for relative in REQUIRED_FILES:
        if "|" in relative:
            options = relative.split("|")
            if not any((run_dir / item).exists() for item in options):
                issues.append(f"missing required marker: {relative}")
        elif not (run_dir / relative).exists():
            issues.append(f"missing required file: {relative}")
    if issues:
        return False, issues

    marker_names = ["SUCCESS.marker", "INVALID.marker", "FAILED.marker"]
    markers = [name for name in marker_names if (run_dir / name).exists()]
    if len(markers) != 1:
        issues.append("run must contain exactly one final marker")
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "audit" / "run_manifest.json").read_text(encoding="utf-8"))
    blockers = json.loads((run_dir / "audit" / "blockers.json").read_text(encoding="utf-8")).get("blockers", [])
    blocker_ids = {blocker.get("blocker_id") for blocker in blockers}
    if markers and markers[0] == "SUCCESS.marker" and status.get("status") != "completed":
        issues.append("SUCCESS.marker requires status=completed")
    if markers and markers[0] == "INVALID.marker" and status.get("status") != "invalid":
        issues.append("INVALID.marker requires status=invalid")
    if markers and markers[0] == "FAILED.marker" and status.get("status") != "failed":
        issues.append("FAILED.marker requires status=failed")
    ranking = read_csv_rows(run_dir / "results" / "ranking.csv")
    metrics = read_csv_rows(run_dir / "results" / "metrics_by_candidate.csv")
    controls = read_csv_rows(run_dir / "results" / "control_pairs.csv")
    metrics_ids = {row["candidate_id"] for row in metrics}
    controls_by_id = {row["candidate_id"]: row for row in controls}
    for row in ranking:
        if row.get("operational_status") == "completed":
            cid = row["candidate_id"]
            if cid not in metrics_ids:
                issues.append(f"completed candidate missing metrics: {cid}")
            control = controls_by_id.get(cid)
            if not control:
                issues.append(f"completed candidate missing control pair: {cid}")
            elif control.get("with_p9_status") not in {"completed", "failed", "invalid"} or control.get(
                "without_p9_status"
            ) not in {"completed", "failed", "invalid"}:
                issues.append(f"candidate control status invalid: {cid}")
    if ranking and ranking[0].get("scientific_status") == "invalid":
        issues.append("ranking places invalid candidate as top valid row")
    for relative in [
        "results/ranking.csv",
        "results/metrics_by_candidate.csv",
        "results/control_pairs.csv",
        "candidates_status.csv",
    ]:
        for line, row in enumerate(read_csv_rows(run_dir / relative), start=2):
            for key, value in row.items():
                if bad_number(value):
                    issues.append(f"bad numeric value in {relative}:{line}:{key}")
    hashes = json.loads((run_dir / "audit" / "hashes.json").read_text(encoding="utf-8"))
    for required_hash in [
        "config_hash",
        "catalog_hash",
        "giants_hash",
        "candidate_region_hash",
        "scoring_hash",
        "protocol_hash",
    ]:
        if required_hash not in hashes or not hashes[required_hash]:
            issues.append(f"missing hash: {required_hash}")
    if not manifest.get("rebound_used") and "rebound_not_available" not in blocker_ids:
        issues.append("REBOUND not used but rebound_not_available blocker is absent")
    if not (run_dir / "reports" / "report.md").read_text(encoding="utf-8").strip():
        issues.append("reports/report.md is empty")
    if not (run_dir / "replay_command.txt").read_text(encoding="utf-8").strip():
        issues.append("replay_command.txt is empty")
    v2_pairs = [
        ("robustness/leave_one_out.csv", "robustness/leave_one_out_summary.json"),
        ("robustness/convergence.csv", "robustness/convergence_summary.json"),
        ("robustness/null_models.csv", "robustness/null_models_summary.json"),
        ("robustness/null_models.csv", "robustness/null_model_percentiles.csv"),
        ("validation/ias15_validation.csv", "validation/ias15_summary.json"),
    ]
    for trigger, required in v2_pairs:
        if (run_dir / trigger).exists() and not (run_dir / required).exists():
            issues.append(f"missing V2 artifact after {trigger}: {required}")
    return not issues, issues

