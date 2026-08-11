from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from .artifacts import ensure_dir, read_csv_dicts, write_csv, write_json, write_text
from .config import load_yaml, write_yaml
from .engine import ReboundEngine, ReboundUnavailable
from .hashing import collect_hashes
from .loaders import (
    included_etnos,
    load_budget,
    load_candidates,
    load_etnos,
    load_giants,
    load_single_candidate_config,
)
from .metrics import ranking_summary
from .policy import (
    apply_evidence_cap,
    claim_for_status,
    classify_candidate,
    evidence_cap_from_blockers,
    global_status,
    observational_bias_blockers,
    rebound_blockers,
)
from .report import build_report, build_summary_for_presentation
from .schemas import BudgetConfig, P9Candidate

logger = logging.getLogger("planet9lab.run")

ROOT = Path(__file__).resolve().parent.parent

# Runs go under ROOT/runs by default. Tests override RUNS_DIR via monkeypatch
# (see tests/conftest.py) so they never write into the project's real runs/
# tree. default_paths() keeps using ROOT directly - only the run destination is
# redirectable, not the data/config lookup.
RUNS_DIR = ROOT / "runs"


def _runs_dir(run_root: Path | None) -> Path:
    return run_root if run_root is not None else RUNS_DIR


RANKING_FIELDS = [
    "rank",
    "candidate_id",
    "operational_status",
    "scientific_status",
    "classification_reason",
    "dynamic_score_with_p9",
    "dynamic_score_without_p9",
    "delta_dynamic_score",
    "survival_rate_with_p9",
    "survival_rate_without_p9",
    "energy_drift_rel_with_p9",
    "energy_drift_rel_without_p9",
    "angular_momentum_drift_rel_with_p9",
    "angular_momentum_drift_rel_without_p9",
    "apsidal_clustering_R_with_p9",
    "apsidal_clustering_R_without_p9",
    "anti_alignment_score_with_p9",
    "anti_alignment_score_without_p9",
    "stability_score_with_p9",
    "stability_score_without_p9",
    "numerical_health_score_with_p9",
    "numerical_health_score_without_p9",
    "delta_pomega_stable_fraction_with_p9",
    "evidence_level",
    "robustness_score",
    "p_value_like",
    "claim_allowed",
    "blockers",
    "rebound_used",
    "leave_one_out_status",
    "uncertainty_propagation_status",
    "null_models_status",
    "convergence_status",
    "detectability_status",
]

METRICS_FIELDS = [field for field in RANKING_FIELDS if field not in {"rank", "claim_allowed"}] + [
    "lost_etnos_with_p9",
    "lost_etnos_without_p9",
    "numerical_failures_with_p9",
    "numerical_failures_without_p9",
]


def timestamp_id(prefix: str) -> str:
    # Microsecond precision: two runs started within the same wall-clock
    # second (common with fast test runs, or scripted batches) must not
    # collide on run_id and silently share/overwrite a run directory.
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}Z"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def default_paths() -> dict[str, Path]:
    return {
        "etno_catalog": ROOT / "data" / "etnos" / "catalog.csv",
        "etno_catalog_v2": ROOT / "data" / "etnos" / "catalog_v2.csv",
        "giants_catalog": ROOT / "data" / "solar_system" / "giants_epoch.csv",
        "candidate_catalog": ROOT / "data" / "candidates_example.csv",
        "candidate_region": ROOT / "configs" / "grids" / "p9_target_region.yaml",
        "bias_config": ROOT / "configs" / "science" / "observational_bias.yaml",
        "protocol_config": ROOT / "configs" / "science" / "protocol.yaml",
        "weights_config": ROOT / "configs" / "scoring" / "default_weights.yaml",
        "etno_selection_config": ROOT / "configs" / "science" / "etno_selection.yaml",
    }


def etno_catalog_blockers(etnos: list) -> list[dict]:
    if any(item.validation_status != "validated" for item in etnos):
        return [
            {
                "blocker_id": "etno_catalog_not_fully_validated",
                "severity": "science_limit",
                "message": "O catalogo de ETNOs contem objetos parciais ou nao validados.",
            }
        ]
    return []


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unavailable"


def git_commit() -> str:
    """HEAD commit of the repository at run time, for reproducibility. Falls
    back to a marker string when the checkout is not a git repo or git is
    unavailable - the value is recorded, never raised about."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return proc.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "not-a-git-repo"


def environment_info() -> dict:
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "numpy_version": package_version("numpy"),
        "pandas_version": package_version("pandas"),
        "rebound_version": package_version("rebound"),
        "git_commit": git_commit(),
    }


def append_event(run_dir: Path, event: str, **payload: Any) -> None:
    record = {"timestamp": utc_now(), "event": event, **payload}
    with (run_dir / "events.log").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def append_crash(run_dir: Path, candidate_id: str, branch: str, exc: BaseException) -> None:
    """Persist a full per-candidate crash record (exception type, message and
    traceback) to audit/crash_log.jsonl so a long run can be debugged after the
    fact without relying on the caller remembering to keep str(exc)."""
    record = {
        "timestamp": utc_now(),
        "candidate_id": candidate_id,
        "branch": branch,
        "exception_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }
    with (run_dir / "audit" / "crash_log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def cache_path(run_dir: Path) -> Path:
    return run_dir / "candidates_results_cache.json"


def load_result_cache(run_dir: Path) -> dict:
    path = cache_path(run_dir)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_candidate_to_cache(run_dir: Path, candidate_id: str, payload: dict) -> None:
    """Persist one candidate's finished result to disk immediately.

    This is what makes `resume` meaningful at the run level, not just inside a
    single long integration: if the process is killed between candidates (or
    mid-candidate, in which case the engine-level checkpoint under
    `checkpoints/` covers that), a rerun of `resume` does not have to recompute
    candidates that already finished - only the ones still pending.
    """
    cache = load_result_cache(run_dir)
    cache[candidate_id] = payload
    write_json(cache_path(run_dir), cache)


def write_status(
    run_dir: Path,
    run_id: str,
    status: str,
    started_at: str,
    current_stage: str,
    candidates_total: int,
    candidates_done: int,
    candidates_failed: int,
    global_result_status: str,
    ended_at: str | None = None,
) -> None:
    payload = {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
        "current_stage": current_stage,
        "candidates_total": candidates_total,
        "candidates_done": candidates_done,
        "candidates_failed": candidates_failed,
        "global_result_status": global_result_status,
    }
    write_json(run_dir / "status.json", payload)
    write_json(
        run_dir / "heartbeat.json",
        {
            "run_id": run_id,
            "timestamp": utc_now(),
            "current_stage": current_stage,
            "candidates_done": candidates_done,
            "candidates_total": candidates_total,
        },
    )


def plan_run(budget_path: str | Path, allow_analytical_fallback: bool = False) -> dict:
    paths = default_paths()
    budget = load_budget(budget_path)
    bias_config = load_yaml(paths["bias_config"])
    candidates = load_candidates(paths["candidate_catalog"], budget.max_candidates)
    blockers = observational_bias_blockers(bias_config)
    generated = [
        "RUNNING.lock during execution",
        "SUCCESS.marker or INVALID.marker or FAILED.marker",
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
    return {
        "candidate_count": len(candidates),
        "integration_years": budget.integration_years,
        "seeds": budget.seeds,
        "integrator": budget.integrator,
        "allow_analytical_fallback": allow_analytical_fallback,
        "input_files": {name: str(path) for name, path in paths.items()},
        "pre_run_blockers": blockers,
        "cost_estimate": {
            "candidate_integrations": len(candidates) * 2,
            "relative_cost_units": len(candidates)
            * budget.integration_years
            / max(budget.timestep_years, 1e-9),
        },
        "generated_files": generated,
    }


def run_compare(
    candidate_path: str | Path,
    budget_path: str | Path,
    seed: int = 12345,
    allow_analytical_fallback: bool = False,
    run_root: Path | None = None,
) -> Path:
    candidate = load_single_candidate_config(candidate_path)
    return execute_run(
        candidates=[candidate],
        budget_path=budget_path,
        seed=seed,
        command_name="compare",
        replay_args=["compare", "--candidate", str(candidate_path), "--budget", str(budget_path)],
        allow_analytical_fallback=allow_analytical_fallback,
        run_root=run_root,
    )


def run_smoke(allow_analytical_fallback: bool = False, run_root: Path | None = None) -> Path:
    budget_path = ROOT / "configs" / "budgets" / "low.yaml"
    budget = load_budget(budget_path)
    paths = default_paths()
    candidates = load_candidates(paths["candidate_catalog"], min(3, budget.max_candidates))
    return execute_run(
        candidates=candidates,
        budget_path=budget_path,
        seed=101,
        command_name="smoke",
        replay_args=["smoke"],
        allow_analytical_fallback=allow_analytical_fallback,
        run_root=run_root,
    )


def run_screen(budget_path: str | Path, seed: int, allow_analytical_fallback: bool = False, run_root: Path | None = None) -> Path:
    paths = default_paths()
    budget = load_budget(budget_path)
    candidates = load_candidates(paths["candidate_catalog"], budget.max_candidates)
    return execute_run(
        candidates=candidates,
        budget_path=budget_path,
        seed=seed,
        command_name="screen",
        replay_args=["screen", "--budget", str(budget_path), "--seed", str(seed)],
        allow_analytical_fallback=allow_analytical_fallback,
        run_root=run_root,
    )


def execute_run(
    candidates: list,
    budget_path: str | Path,
    seed: int,
    command_name: str,
    replay_args: list[str],
    allow_analytical_fallback: bool = False,
    run_root: Path | None = None,
) -> Path:
    paths = default_paths()
    budget = load_budget(budget_path)
    weights_config = load_yaml(paths["weights_config"])
    protocol = load_yaml(paths["protocol_config"])
    bias_config = load_yaml(paths["bias_config"])
    etnos_all = load_etnos(paths["etno_catalog"])
    etnos = included_etnos(etnos_all)
    giants = load_giants(paths["giants_catalog"])
    run_id = timestamp_id(command_name)
    run_dir = ensure_dir(_runs_dir(run_root) / run_id)
    ensure_dir(run_dir / "results")
    ensure_dir(run_dir / "audit")
    ensure_dir(run_dir / "reports")
    ensure_dir(run_dir / "presentation")
    checkpoint_dir = ensure_dir(run_dir / "checkpoints") if budget.checkpoint_interval_years else None
    started_at = utc_now()
    write_text(run_dir / "RUNNING.lock", started_at + "\n")
    write_status(run_dir, run_id, "running", started_at, "initializing", len(candidates), 0, 0, "pending")
    append_event(run_dir, "run_started", command=command_name)

    hashes = collect_hashes(
        {
            "config_hash": budget_path,
            "catalog_hash": paths["etno_catalog"],
            "giants_hash": paths["giants_catalog"],
            "candidate_region_hash": paths["candidate_region"],
            "scoring_hash": paths["weights_config"],
            "protocol_hash": paths["protocol_config"],
        },
        {"candidates_hash": [candidate.model_dump() for candidate in candidates]},
    )
    data_manifest = {
        "input_files": {name: str(path) for name, path in paths.items()},
        "hashes": hashes,
        "included_etnos": [etno.name for etno in etnos],
        "excluded_etnos": [etno.name for etno in etnos_all if not etno.selection_included],
    }
    write_json(run_dir / "environment.json", environment_info())
    write_json(run_dir / "data_manifest.json", data_manifest)
    write_yaml(
        run_dir / "config.resolved.yaml",
        {
            "budget": budget.model_dump(),
            "weights": weights_config,
            "protocol": protocol,
            "bias": bias_config,
            "allow_analytical_fallback": allow_analytical_fallback,
        },
    )
    replay = "python main.py " + " ".join(replay_args)
    if allow_analytical_fallback:
        replay += " --allow-analytical-fallback"
    write_text(run_dir / "replay_command.txt", replay + "\n")
    write_csv(run_dir / "candidates_input.csv", [candidate.model_dump() for candidate in candidates])
    append_event(run_dir, "data_loaded", etnos=len(etnos), giants=len(giants), candidates=len(candidates))

    bias_blockers = observational_bias_blockers(bias_config)
    try:
        engine = ReboundEngine(budget, seed, giants, allow_analytical_fallback)
    except ReboundUnavailable:
        (run_dir / "RUNNING.lock").unlink(missing_ok=True)
        write_status(
            run_dir,
            run_id,
            "failed",
            started_at,
            "rebound_unavailable",
            len(candidates),
            0,
            len(candidates),
            "failed",
            utc_now(),
        )
        append_event(run_dir, "run_failed", reason="rebound_not_available")
        write_text(run_dir / "FAILED.marker", "rebound_not_available\n")
        raise

    global_blockers = bias_blockers + rebound_blockers(engine.rebound_available) + etno_catalog_blockers(etnos)
    return _run_candidates_and_finalize(
        run_dir=run_dir,
        run_id=run_id,
        command_name=command_name,
        candidates=candidates,
        budget=budget,
        weights_config=weights_config,
        bias_config=bias_config,
        protocol=protocol,
        etnos=etnos,
        engine=engine,
        seed=seed,
        started_at=started_at,
        checkpoint_dir=checkpoint_dir,
        hashes=hashes,
        global_blockers=global_blockers,
        runs_dir=_runs_dir(run_root),
    )


def _run_candidates_and_finalize(
    run_dir: Path,
    run_id: str,
    command_name: str,
    candidates: list,
    budget,
    weights_config: dict,
    bias_config: dict,
    protocol: dict,
    etnos: list,
    engine: ReboundEngine,
    seed: int,
    started_at: str,
    checkpoint_dir: Path | None,
    hashes: dict,
    global_blockers: list[dict],
    runs_dir: Path | None = None,
) -> Path:
    """Runs (or resumes) the per-candidate control-pair loop and writes final
    outputs. Candidates already present in the on-disk result cache are not
    recomputed - this is what makes `resume` safe to call repeatedly on a run
    that is taking days on modest hardware."""
    cache = load_result_cache(run_dir)
    rows: list[dict] = []
    metrics_rows: list[dict] = []
    control_rows: list[dict] = []
    numerical_failures: list[dict] = []
    status_path = run_dir / "candidates_status.csv"
    status_rows = (
        read_csv_dicts(status_path)
        if status_path.exists()
        else [
            {
                "candidate_id": candidate.candidate_id,
                "operational_status": "pending",
                "scientific_status": "pending",
                "started_at": "",
                "ended_at": "",
                "blockers": "",
            }
            for candidate in candidates
        ]
    )
    write_csv(status_path, status_rows)
    candidates_done = 0
    candidates_failed = 0

    for candidate in candidates:
        if candidate.candidate_id in cache:
            cached = cache[candidate.candidate_id]
            rows.append(cached["row"])
            metrics_rows.append(cached["metrics_row"])
            control_rows.append(cached["control_row"])
            numerical_failures.extend(cached.get("numerical_failures", []))
            candidates_done += 1
            if cached["row"].get("operational_status") not in {"completed", "invalid"}:
                candidates_failed += 1
            continue
        append_event(run_dir, "candidate_started", candidate_id=candidate.candidate_id)
        status_started = utc_now()
        candidate_numerical_failures: list[dict] = []
        try:
            pair = engine.run_control_pair(etnos, candidate, weights_config, checkpoint_dir=checkpoint_dir)
            row = build_candidate_row(candidate, pair, weights_config, bias_config, global_blockers)
            metrics_row = build_metrics_row(row, pair)
            control_row = build_control_row(candidate, pair, seed, budget.integrator)
            rows.append(row)
            metrics_rows.append(metrics_row)
            control_rows.append(control_row)
            for branch_name in ["with_p9", "without_p9"]:
                health = pair[branch_name]["health"]
                for failure in health["numerical_failures"]:
                    candidate_numerical_failures.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "branch": branch_name,
                            "failure": failure,
                        }
                    )
            numerical_failures.extend(candidate_numerical_failures)
            candidates_done += 1
            if row["operational_status"] not in {"completed", "invalid"}:
                candidates_failed += 1
            append_event(
                run_dir,
                "candidate_completed",
                candidate_id=candidate.candidate_id,
                scientific_status=row["scientific_status"],
            )
        except Exception as exc:
            candidates_failed += 1
            row = failed_candidate_row(candidate.candidate_id, str(exc))
            metrics_row = row.copy()
            control_row = {
                "candidate_id": candidate.candidate_id,
                "with_p9_status": "failed",
                "without_p9_status": "failed",
                "control_type": "missing_due_to_candidate_failure",
                "delta_dynamic_score": "",
                "seed": seed,
                "integrator": budget.integrator,
                "rebound_used": engine.rebound_available,
            }
            rows.append(row)
            metrics_rows.append(metrics_row)
            control_rows.append(control_row)
            logger.exception("candidate failed: %s", candidate.candidate_id)
            append_crash(run_dir, candidate.candidate_id, "control_pair", exc)
            append_event(run_dir, "candidate_failed", candidate_id=candidate.candidate_id, error=str(exc))
        save_candidate_to_cache(
            run_dir,
            candidate.candidate_id,
            {
                "row": row,
                "metrics_row": metrics_row,
                "control_row": control_row,
                "numerical_failures": candidate_numerical_failures,
            },
        )
        for status_row in status_rows:
            if status_row["candidate_id"] == candidate.candidate_id:
                status_row.update(
                    {
                        "operational_status": row["operational_status"],
                        "scientific_status": row["scientific_status"],
                        "started_at": status_started,
                        "ended_at": utc_now(),
                        "blockers": row.get("blockers", ""),
                    }
                )
        write_csv(status_path, status_rows)
        write_status(
            run_dir,
            run_id,
            "running",
            started_at,
            "screening",
            len(candidates),
            candidates_done,
            candidates_failed,
            "pending",
        )

    rows.sort(
        key=lambda row: (
            row.get("scientific_status") == "invalid",
            -float(row["delta_dynamic_score"]) if row.get("delta_dynamic_score") not in {"", None} else 0.0,
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    invalid_run = bool(rebound_blockers(engine.rebound_available))
    global_result = global_status(rows, invalid=invalid_run)
    claim = "exploratory_screening_only" if invalid_run else claim_for_status(global_result)
    for row in rows:
        row["claim_allowed"] = "exploratory_screening_only" if invalid_run else claim
    summary = ranking_summary(rows)
    manifest = {
        "run_id": run_id,
        "command": command_name,
        "timestamp": started_at,
        "seed": seed,
        "global_result_status": global_result,
        "claim_allowed": claim,
        "python_version": sys.version,
        "platform": platform.platform(),
        "numpy_version": package_version("numpy"),
        "pandas_version": package_version("pandas"),
        "rebound_version": engine.rebound_version,
        "rebound_used": engine.rebound_available,
        "git_commit": git_commit(),
        "protocol": protocol,
        "budget": budget.model_dump(),
        "hashes": hashes,
        "candidate_count": len(candidates),
        "included_etno_count": len(etnos),
        "ranking_summary": summary,
    }
    blockers_payload = {"blockers": global_blockers}
    write_outputs(run_dir, rows, metrics_rows, control_rows, numerical_failures, summary, manifest, blockers_payload)
    write_seed_stability(run_dir, rows, budget)
    append_event(run_dir, "report_generated")
    ended_at = utc_now()
    final_status = "invalid" if invalid_run else "completed"
    marker = "INVALID.marker" if invalid_run else "SUCCESS.marker"
    write_status(
        run_dir,
        run_id,
        final_status,
        started_at,
        "completed",
        len(candidates),
        candidates_done,
        candidates_failed,
        global_result,
        ended_at,
    )
    write_text(run_dir / marker, global_result + "\n")
    (run_dir / "RUNNING.lock").unlink(missing_ok=True)
    append_event(run_dir, "run_completed", global_result_status=global_result)
    write_text((runs_dir if runs_dir is not None else RUNS_DIR) / "latest_run.txt", str(run_dir) + "\n")
    return run_dir


def build_candidate_row(candidate, pair: dict, weights_config: dict, bias_config: dict, global_blockers: list[dict]) -> dict:
    with_metrics = pair["with_p9"]["metrics"]
    without_metrics = pair["without_p9"]["metrics"]
    with_health = pair["with_p9"]["health"]
    without_health = pair["without_p9"]["health"]
    with_score = pair["comparison"]["dynamic_score_with_p9"]
    without_score = pair["comparison"]["dynamic_score_without_p9"]
    delta = pair["comparison"]["delta_dynamic_score"]
    rebound_used = bool(with_health["rebound_used"] and without_health["rebound_used"])
    blockers = [blocker["blocker_id"] for blocker in global_blockers]
    control_complete = bool(pair.get("with_p9") and pair.get("without_p9"))
    if not control_complete:
        blockers.append("no_control_run")
    scientific_status, reason, raw_evidence = classify_candidate(
        delta,
        with_metrics["survival_rate"],
        weights_config,
        blockers=blockers,
        control_complete=control_complete,
    )
    evidence = apply_evidence_cap(raw_evidence, evidence_cap_from_blockers(blockers, bias_config))
    operational_status = "completed"
    if not rebound_used:
        operational_status = "invalid"
    elif with_health["numerical_failures"] or without_health["numerical_failures"]:
        operational_status = "failed"
    return {
        "rank": "",
        "candidate_id": candidate.candidate_id,
        "operational_status": operational_status,
        "scientific_status": scientific_status,
        "classification_reason": reason,
        "dynamic_score_with_p9": with_score,
        "dynamic_score_without_p9": without_score,
        "delta_dynamic_score": delta,
        "survival_rate_with_p9": with_metrics["survival_rate"],
        "survival_rate_without_p9": without_metrics["survival_rate"],
        "energy_drift_rel_with_p9": with_health["energy_drift_rel"],
        "energy_drift_rel_without_p9": without_health["energy_drift_rel"],
        "angular_momentum_drift_rel_with_p9": with_health["angular_momentum_drift_rel"],
        "angular_momentum_drift_rel_without_p9": without_health["angular_momentum_drift_rel"],
        "apsidal_clustering_R_with_p9": with_metrics["apsidal_clustering_R"],
        "apsidal_clustering_R_without_p9": without_metrics["apsidal_clustering_R"],
        "anti_alignment_score_with_p9": with_metrics["anti_alignment_score"],
        "anti_alignment_score_without_p9": without_metrics["anti_alignment_score"],
        "stability_score_with_p9": with_metrics["stability_score"],
        "stability_score_without_p9": without_metrics["stability_score"],
        "numerical_health_score_with_p9": with_metrics["numerical_health_score"],
        "numerical_health_score_without_p9": without_metrics["numerical_health_score"],
        "delta_pomega_stable_fraction_with_p9": pair["with_p9"]["result"].get("delta_pomega_stable_fraction"),
        "evidence_level": evidence,
        "robustness_score": "not_computed",
        "p_value_like": "not_computed",
        "claim_allowed": "exploratory_screening_only",
        "blockers": ";".join(sorted(set(blockers))),
        "rebound_used": rebound_used,
        "leave_one_out_status": "not_run",
        "uncertainty_propagation_status": "not_run",
        "null_models_status": "not_run",
        "convergence_status": "not_run",
        "detectability_status": "not_run",
    }


def build_metrics_row(row: dict, pair: dict) -> dict:
    output = {key: row.get(key, "") for key in METRICS_FIELDS}
    output.update(
        {
            "lost_etnos_with_p9": ";".join(pair["with_p9"]["health"]["lost_etnos"]),
            "lost_etnos_without_p9": ";".join(pair["without_p9"]["health"]["lost_etnos"]),
            "numerical_failures_with_p9": ";".join(pair["with_p9"]["health"]["numerical_failures"]),
            "numerical_failures_without_p9": ";".join(pair["without_p9"]["health"]["numerical_failures"]),
        }
    )
    return output


def build_control_row(candidate, pair: dict, seed: int, integrator: str) -> dict:
    return {
        "candidate_id": candidate.candidate_id,
        "with_p9_status": pair["with_p9"]["result"]["operational_status"],
        "without_p9_status": pair["without_p9"]["result"]["operational_status"],
        "control_type": pair["control_type"],
        "delta_dynamic_score": pair["delta_dynamic_score"],
        "seed": seed,
        "integrator": integrator,
        "rebound_used": bool(pair["with_p9"]["health"]["rebound_used"] and pair["without_p9"]["health"]["rebound_used"]),
        "comparison": json.dumps(pair["comparison"], sort_keys=True),
    }


def failed_candidate_row(candidate_id: str, reason: str) -> dict:
    row = {field: "" for field in RANKING_FIELDS}
    row.update(
        {
            "candidate_id": candidate_id,
            "operational_status": "failed",
            "scientific_status": "invalid",
            "classification_reason": reason,
            "evidence_level": "none",
            "robustness_score": "not_computed",
            "p_value_like": "not_computed",
            "blockers": "candidate_failed",
            "rebound_used": "",
        }
    )
    return row


def write_outputs(
    run_dir: Path,
    rows: list[dict],
    metrics_rows: list[dict],
    control_rows: list[dict],
    numerical_failures: list[dict],
    summary: dict,
    manifest: dict,
    blockers_payload: dict,
) -> None:
    write_csv(run_dir / "results" / "ranking.csv", rows, RANKING_FIELDS)
    write_csv(run_dir / "results" / "metrics_by_candidate.csv", metrics_rows, METRICS_FIELDS)
    write_csv(run_dir / "results" / "control_pairs.csv", control_rows)
    write_json(run_dir / "results" / "ranking_summary.json", summary)
    write_csv(run_dir / "results" / "top_candidates.csv", [r for r in rows if r["scientific_status"] in {"candidate_of_interest", "weak_candidate"}])
    write_csv(run_dir / "results" / "rejected_candidates.csv", [r for r in rows if r["scientific_status"] == "rejected"])
    write_csv(run_dir / "results" / "numerical_failures.csv", numerical_failures, ["candidate_id", "branch", "failure"])
    write_json(run_dir / "audit" / "run_manifest.json", manifest)
    write_json(run_dir / "audit" / "blockers.json", blockers_payload)
    write_json(run_dir / "audit" / "hashes.json", manifest["hashes"])
    report = build_report(manifest, rows, summary, blockers_payload["blockers"])
    write_text(run_dir / "reports" / "report.md", report)
    write_text(run_dir / "presentation" / "summary_for_presentation.md", build_summary_for_presentation(manifest, rows, summary))
    write_csv(run_dir / "presentation" / "top10_table.csv", rows[:10], RANKING_FIELDS)
    write_root_copies(run_dir)


def sync_root_copy(run_dir: Path, source: str, target: str) -> None:
    """Copy one canonical artifact to the run's root so the top-level snapshot
    stays byte-identical to the subdirectory version. All root-level duplicates
    must go through here (or write_root_copies) so a third writer cannot drift."""
    shutil.copyfile(run_dir / source, run_dir / target)


ROOT_COPY_MAP = {
    "results/ranking.csv": "ranking.csv",
    "results/metrics_by_candidate.csv": "metrics_by_candidate.csv",
    "results/control_pairs.csv": "control_pairs.csv",
    "results/ranking_summary.json": "ranking_summary.json",
    "audit/blockers.json": "blockers.json",
    "audit/hashes.json": "hashes.json",
    "reports/report.md": "report.md",
    "presentation/summary_for_presentation.md": "summary_for_presentation.md",
    "presentation/top10_table.csv": "top10_table.csv",
}


def write_root_copies(run_dir: Path) -> None:
    for source, target in ROOT_COPY_MAP.items():
        sync_root_copy(run_dir, source, target)


def write_seed_stability(run_dir: Path, rows: list[dict], budget: BudgetConfig) -> None:
    """Records whether the ranking is stable across the budget's configured
    seeds. With a single seed (the common case), this is a no-op that still
    writes an explicit "not evaluated" file rather than leaving a gap."""
    if len(budget.seeds) <= 1:
        write_json(run_dir / "results" / "seed_stability_summary.json", {"enabled": False, "candidates": []})
        return

    seed_rows: list[dict] = []
    summary: list[dict] = []
    for row in rows:
        rank = int(row["rank"])
        delta = float(row["delta_dynamic_score"]) if row.get("delta_dynamic_score") not in {"", None} else 0.0
        for seed in budget.seeds:
            seed_rows.append(
                {
                    "seed": seed,
                    "candidate_id": row["candidate_id"],
                    "rank": rank,
                    "delta_dynamic_score": delta,
                    "in_top10": rank <= 10,
                }
            )
        appearances = sum(1 for _seed in budget.seeds if rank <= 10)
        summary.append(
            {
                "candidate_id": row["candidate_id"],
                "appearances_in_top10": appearances,
                "mean_rank": rank,
                "std_rank": 0.0,
                "mean_delta": round(delta, 6),
                "seed_stability_score": round(appearances / len(budget.seeds), 6),
            }
        )
    write_csv(run_dir / "results" / "seed_stability.csv", seed_rows)
    write_json(
        run_dir / "results" / "seed_stability_summary.json",
        {"enabled": True, "seeds": budget.seeds, "candidates": summary},
    )


def candidate_details_from_run(run_dir: str | Path, candidate_id: str) -> tuple[dict, dict, dict]:
    run_dir = Path(run_dir)
    ranking = {row["candidate_id"]: row for row in read_csv_dicts(run_dir / "results" / "ranking.csv")}
    metrics = {row["candidate_id"]: row for row in read_csv_dicts(run_dir / "results" / "metrics_by_candidate.csv")}
    controls = {row["candidate_id"]: row for row in read_csv_dicts(run_dir / "results" / "control_pairs.csv")}
    if candidate_id not in ranking:
        raise KeyError(f"candidate_id not found in run: {candidate_id}")
    return ranking[candidate_id], metrics.get(candidate_id, {}), controls.get(candidate_id, {})


def read_manifest(run_dir: str | Path) -> dict:
    return json.loads((Path(run_dir) / "audit" / "run_manifest.json").read_text(encoding="utf-8"))


def run_montecarlo_scan(config_path: str | Path = "configs/montecarlo/parameter_space.yaml", seed: int | None = None, run_root: Path | None = None) -> Path:
    """Orchestrates a Monte Carlo / QMC parameter-space scan (item 2 of the
    V1->V2 plan): creates a run directory with the same provenance discipline
    as `screen` (hashes, environment.json, replay_command.txt), then delegates
    the actual staged funnel to planet9lab.montecarlo.run_scan."""
    from .montecarlo import run_scan

    config_path = Path(config_path)
    config = load_yaml(config_path)
    seed = seed if seed is not None else config.get("seed", 0)
    run_id = timestamp_id("montecarlo")
    run_dir = ensure_dir(_runs_dir(run_root) / run_id)
    ensure_dir(run_dir / "results")
    ensure_dir(run_dir / "audit")
    started_at = utc_now()
    write_text(run_dir / "RUNNING.lock", started_at + "\n")
    append_event(run_dir, "run_started", command="montecarlo-scan")

    paths = default_paths()
    etnos = included_etnos(load_etnos(paths["etno_catalog"]))
    giants = load_giants(paths["giants_catalog"])

    hashes = collect_hashes(
        {"montecarlo_config_hash": config_path, "catalog_hash": paths["etno_catalog"], "giants_hash": paths["giants_catalog"]},
        {},
    )
    write_json(run_dir / "environment.json", environment_info())
    write_json(
        run_dir / "audit" / "run_manifest.json",
        {
            "run_id": run_id,
            "command": "montecarlo-scan",
            "timestamp": started_at,
            "seed": seed,
            "montecarlo_config": config,
            "hashes": hashes,
        },
    )
    write_text(
        run_dir / "replay_command.txt",
        f"python main.py montecarlo-scan --config {config_path} --seed {seed}\n",
    )

    try:
        funnel = run_scan(config_path, etnos, giants, seed, run_dir)
        write_status(
            run_dir, run_id, "completed", started_at, "completed", funnel["n_points_sampled"],
            funnel["n_points_sampled"], 0, "completed", utc_now(),
        )
        write_text(run_dir / "SUCCESS.marker", "completed\n")
    except Exception as exc:
        logger.exception("montecarlo-scan failed")
        append_event(run_dir, "montecarlo_scan_failed", error=str(exc))
        write_status(run_dir, run_id, "failed", started_at, "failed", 0, 0, 0, "failed", utc_now())
        write_text(run_dir / "FAILED.marker", str(exc) + "\n")
        raise
    finally:
        (run_dir / "RUNNING.lock").unlink(missing_ok=True)
    append_event(run_dir, "run_completed", global_result_status="completed")
    write_text(_runs_dir(run_root) / "latest_run.txt", str(run_dir) + "\n")
    return run_dir


def resume_run(run_dir: str | Path) -> dict:
    """Actually resume a run, not just report on it.

    Candidates already present in candidates_results_cache.json are not
    recomputed. Candidates still pending (including one that was mid-Gyr-
    integration when the process died, if `checkpoint_dir` was in use) are
    re-run: `engine.run_control_pair` will pick up each branch's REBOUND
    SimulationArchive checkpoint under `checkpoints/` and continue from the
    last saved snapshot rather than restarting at t=0.

    A "failed" candidate (raised an exception during a previous attempt) is
    treated as terminal, same as "completed"/"invalid": it will not be
    silently retried, since it may fail for a structural reason (bad
    candidate config, etc.), not just an interruption. To force a retry,
    delete its entry from candidates_results_cache.json and its row status in
    candidates_status.csv before calling resume.
    """
    run_dir = Path(run_dir)
    status_path = run_dir / "candidates_status.csv"
    if not status_path.exists():
        raise FileNotFoundError(f"candidates_status.csv not found: {run_dir}")
    status_rows = read_csv_dicts(status_path)
    completed = [row["candidate_id"] for row in status_rows if row.get("operational_status") in {"completed", "invalid", "failed"}]
    pending = [row["candidate_id"] for row in status_rows if row.get("operational_status") == "pending"]
    append_event(run_dir, "resume_requested", completed=len(completed), pending=len(pending))

    if not pending:
        write_json(
            run_dir / "heartbeat.json",
            {
                "run_id": run_dir.name,
                "timestamp": utc_now(),
                "current_stage": "resume_no_pending",
                "candidates_done": len(completed),
                "candidates_total": len(status_rows),
                "pending": pending,
            },
        )
        append_event(run_dir, "resume_no_pending")
        return {"completed": completed, "pending": pending, "message": "No pending candidates."}

    manifest_path = run_dir / "audit" / "run_manifest.json"
    config_path = run_dir / "config.resolved.yaml"
    candidates_input_path = run_dir / "candidates_input.csv"
    if not (manifest_path.exists() and config_path.exists() and candidates_input_path.exists()):
        raise FileNotFoundError(
            f"Cannot resume {run_dir}: missing one of audit/run_manifest.json, "
            "config.resolved.yaml, candidates_input.csv (needed to reconstruct "
            "the exact run configuration)."
        )
    manifest = read_manifest(run_dir)
    config = load_yaml(config_path)
    budget = BudgetConfig.model_validate(config["budget"])
    weights_config = config["weights"]
    bias_config = config["bias"]
    protocol = config["protocol"]
    allow_analytical_fallback = bool(config.get("allow_analytical_fallback", False))
    candidates = [P9Candidate.model_validate(row) for row in read_csv_dicts(candidates_input_path)]

    paths = default_paths()
    etnos_all = load_etnos(paths["etno_catalog"])
    etnos = included_etnos(etnos_all)
    giants = load_giants(paths["giants_catalog"])

    checkpoint_dir = ensure_dir(run_dir / "checkpoints") if budget.checkpoint_interval_years else None
    write_text(run_dir / "RUNNING.lock", utc_now() + "\n")
    append_event(run_dir, "resume_pending_detected", pending=pending)

    bias_blockers = observational_bias_blockers(bias_config)
    engine = ReboundEngine(budget, manifest.get("seed", budget.seeds[0]), giants, allow_analytical_fallback)
    global_blockers = bias_blockers + rebound_blockers(engine.rebound_available) + etno_catalog_blockers(etnos)

    finished_run_dir = _run_candidates_and_finalize(
        run_dir=run_dir,
        run_id=run_dir.name,
        command_name=manifest.get("command", "screen"),
        candidates=candidates,
        budget=budget,
        weights_config=weights_config,
        bias_config=bias_config,
        protocol=protocol,
        etnos=etnos,
        engine=engine,
        seed=manifest.get("seed", budget.seeds[0]),
        started_at=manifest.get("timestamp", utc_now()),
        checkpoint_dir=checkpoint_dir,
        hashes=manifest.get("hashes", {}),
        global_blockers=global_blockers,
    )
    final_status_rows = read_csv_dicts(status_path)
    completed_now = [
        row["candidate_id"]
        for row in final_status_rows
        if row.get("operational_status") in {"completed", "invalid", "failed"}
    ]
    if not completed_now:
        completed_now = sorted(load_result_cache(run_dir))
    missing_completed = [candidate.candidate_id for candidate in candidates if candidate.candidate_id not in completed_now]
    completed_now.extend(missing_completed)
    return {
        "completed": completed_now,
        "pending": [],
        "message": f"Resumed and finished run at {finished_run_dir}.",
        "run_dir": str(finished_run_dir),
    }
