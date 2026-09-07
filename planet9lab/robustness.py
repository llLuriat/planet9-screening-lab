from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from .artifacts import ensure_dir, read_csv_dicts, write_csv, write_json
from .config import load_yaml
from .engine import ReboundEngine
from .loaders import load_etnos, load_giants, selected_etnos
from .metrics import dynamic_score, normalize_degrees
from .parallel import run_parallel_map
from .policy import classify_candidate
from .report import build_report, build_summary_for_presentation
from .run import (
    RANKING_FIELDS,
    ROOT,
    append_event,
    default_paths,
    normalize_metric_columns,
    read_manifest,
    sync_root_copy,
    write_root_copies,
)
from .schemas import BudgetConfig, ETNORecord, P9Candidate


def _context(run_dir: str | Path):
    run_dir = Path(run_dir)
    manifest = read_manifest(run_dir)
    budget = BudgetConfig.model_validate(manifest["budget"])
    paths = default_paths()
    weights = load_yaml(paths["weights_config"])
    etno_path = paths["etno_catalog_v2"] if paths["etno_catalog_v2"].exists() else paths["etno_catalog"]
    etnos, _rejected_etnos = selected_etnos(load_etnos(etno_path), load_yaml(paths["etno_selection_config"]))
    giants = load_giants(paths["giants_catalog"])
    candidates = {
        row["candidate_id"]: P9Candidate.model_validate(row)
        for row in read_csv_dicts(run_dir / "candidates_input.csv")
    }
    ranking = read_csv_dicts(run_dir / "results" / "ranking.csv")
    return run_dir, manifest, budget, weights, etnos, giants, candidates, ranking


def top_candidate_ids(ranking: list[dict], top: int) -> list[str]:
    return [row["candidate_id"] for row in ranking[:top]]


def _run_pair(candidate: P9Candidate, etnos: list[ETNORecord], giants, budget: BudgetConfig, seed: int, weights: dict):
    engine = ReboundEngine(budget, seed, giants, allow_analytical_fallback=False)
    return engine.run_control_pair(etnos, candidate, weights)


# ---------------------------------------------------------------------------
# Parallel robustness workers (Etapa 1). The RNG-driven null-model setup
# (build_null_etnos draws) stays in the parent so the random sequence is
# byte-identical to a sequential run; workers only run the independent
# REBOUND pairs and return pure payloads. The parent appends rows in task
# order and computes summaries, keeping every output CSV identical.
# ---------------------------------------------------------------------------
_RB_WORKER_CTX: dict = {}


def _init_robustness_worker(ctx_payload: dict) -> None:
    _RB_WORKER_CTX.update(ctx_payload)


def _loo_worker(task: tuple[str, str]) -> dict:
    cid, removed_name = task
    ctx = _RB_WORKER_CTX
    candidate = ctx["candidates"][cid]
    subset = [etno for etno in ctx["etnos"] if etno.name != removed_name]
    pair = _run_pair(candidate, subset, ctx["giants"], ctx["budget"], ctx["seed"], ctx["weights"])
    delta = pair["delta_dynamic_score"]
    status, _reason, _raw = classify_candidate(delta, pair["with_p9"]["metrics"]["survival_rate"], ctx["weights"])
    return {
        "candidate_id": cid,
        "removed_etno": removed_name,
        "delta_dynamic_score": delta,
        "scientific_status": status,
        "survival_rate_with_p9": pair["with_p9"]["metrics"]["survival_rate"],
        "survival_rate_without_p9": pair["without_p9"]["metrics"]["survival_rate"],
        "passed": delta > 0,
    }


def _conv_worker(task: tuple[str, int]) -> dict:
    cid, factor = task
    ctx = _RB_WORKER_CTX
    candidate = ctx["candidates"][cid]
    test_budget = ctx["budget"].model_copy(
        update={"timestep_years": ctx["budget"].timestep_years / factor, "integrator": "whfast"}
    )
    pair = _run_pair(candidate, ctx["etnos"], ctx["giants"], test_budget, ctx["seed"], ctx["weights"])
    return {
        "candidate_id": cid,
        "dt_factor": factor,
        "timestep_years": test_budget.timestep_years,
        "delta_dynamic_score": pair["delta_dynamic_score"],
        "energy_drift_rel_with_p9": pair["with_p9"]["health"]["energy_drift_rel"],
        "energy_drift_rel_without_p9": pair["without_p9"]["health"]["energy_drift_rel"],
        "angular_momentum_drift_rel_with_p9": pair["with_p9"]["health"]["angular_momentum_drift_rel"],
        "angular_momentum_drift_rel_without_p9": pair["without_p9"]["health"]["angular_momentum_drift_rel"],
        "survival_rate": min(
            pair["with_p9"]["metrics"]["survival_rate"], pair["without_p9"]["metrics"]["survival_rate"]
        ),
    }


def _validate_worker(task: tuple[str, str]) -> dict:
    cid, integrator = task
    ctx = _RB_WORKER_CTX
    candidate = ctx["candidates"][cid]
    test_budget = ctx["budget"].model_copy(update={"integrator": integrator})
    pair = _run_pair(candidate, ctx["etnos"], ctx["giants"], test_budget, ctx["seed"], ctx["weights"])
    ias_delta = pair["delta_dynamic_score"]
    whfast_delta = ctx["whfast_by_id"][cid]
    same_sign = (ias_delta >= 0 and whfast_delta >= 0) or (ias_delta < 0 and whfast_delta < 0)
    survival = min(pair["with_p9"]["metrics"]["survival_rate"], pair["without_p9"]["metrics"]["survival_rate"])
    if same_sign and survival >= 0.8:
        status = "validated_preliminarily"
    elif not same_sign:
        status = "rejected_after_ias15"
    else:
        status = "inconclusive"
    return {
        "candidate_id": cid,
        "integrator": integrator,
        "whfast_delta_dynamic_score": whfast_delta,
        "ias15_delta_dynamic_score": ias_delta,
        "same_delta_sign": same_sign,
        "survival_rate": survival,
        "status": status,
    }


def _null_worker(task: tuple[str, int, list]) -> list:
    model_name, shuffle_id, null_etnos = task
    ctx = _RB_WORKER_CTX
    engine = ReboundEngine(ctx["null_budget"], ctx["seed"] + shuffle_id + 1, ctx["giants"], allow_analytical_fallback=False)
    without = engine.run_branch(null_etnos, ctx["reference_candidate"], include_p9=False)
    output: list = []
    if model_name == "no_p9_catalog_baseline":
        baseline_delta = round(
            float(without["metrics"]["apsidal_clustering_R"] - without["metrics"]["mean_angular_alignment_score"]),
            6,
        )
        for cid in ctx["top_ids"]:
            output.append((cid, baseline_delta, build_null_row(cid, model_name, shuffle_id, ctx["real_delta"][cid], baseline_delta)))
        return output
    without_score = dynamic_score(without["metrics"], ctx["weights"])
    for cid in ctx["top_ids"]:
        with_p9 = engine.run_branch(null_etnos, ctx["candidates"][cid], include_p9=True)
        delta = round(dynamic_score(with_p9["metrics"], ctx["weights"]) - without_score, 6)
        output.append((cid, delta, build_null_row(cid, model_name, shuffle_id, ctx["real_delta"][cid], delta)))
    return output


def leave_one_out(run_dir: str | Path, top: int = 5, max_workers: int | None = None) -> Path:
    run_dir, manifest, budget, weights, etnos, giants, candidates, ranking = _context(run_dir)
    out_dir = ensure_dir(run_dir / "robustness")
    rows: list[dict] = []
    summary: list[dict] = []
    append_event(run_dir, "v2_leave_one_out_started", top=top)
    top_ids = top_candidate_ids(ranking, top)
    tasks = [(cid, removed.name) for cid in top_ids for removed in etnos]
    results = run_parallel_map(
        _loo_worker,
        tasks,
        max_workers=max_workers,
        initializer=_init_robustness_worker,
        initargs=(
            {
                "giants": giants,
                "weights": weights,
                "seed": manifest["seed"],
                "budget": budget,
                "etnos": etnos,
                "candidates": candidates,
            },
        ),
    )
    for _task, row in zip(tasks, results):
        rows.append(row)
    for cid in top_ids:
        candidate_rows = [r for r in rows if r["candidate_id"] == cid]
        deltas = [float(r["delta_dynamic_score"]) for r in candidate_rows]
        passed = sum(1 for r in candidate_rows if r["passed"])
        summary.append(
            {
                "candidate_id": cid,
                "runs_total": len(deltas),
                "runs_passed": passed,
                "robustness_score": round(passed / len(deltas), 6) if deltas else 0.0,
                "mean_delta_dynamic_score": round(statistics.mean(deltas), 6) if deltas else None,
                "std_delta_dynamic_score": round(statistics.pstdev(deltas), 6) if len(deltas) > 1 else 0.0,
                "min_delta_dynamic_score": round(min(deltas), 6) if deltas else None,
                "max_delta_dynamic_score": round(max(deltas), 6) if deltas else None,
            }
        )
    write_csv(out_dir / "leave_one_out.csv", rows)
    write_json(out_dir / "leave_one_out_summary.json", {"candidates": summary})
    append_event(run_dir, "v2_leave_one_out_completed", rows=len(rows))
    refresh_v2_report(run_dir)
    return out_dir


def convergence(run_dir: str | Path, top: int = 5, max_workers: int | None = None) -> Path:
    run_dir, manifest, budget, weights, etnos, giants, candidates, ranking = _context(run_dir)
    out_dir = ensure_dir(run_dir / "robustness")
    rows: list[dict] = []
    summary: list[dict] = []
    append_event(run_dir, "v2_convergence_started", top=top)
    top_ids = top_candidate_ids(ranking, top)
    tasks = [(cid, factor) for cid in top_ids for factor in [1, 2, 4]]
    results = run_parallel_map(
        _conv_worker,
        tasks,
        max_workers=max_workers,
        initializer=_init_robustness_worker,
        initargs=(
            {
                "giants": giants,
                "weights": weights,
                "seed": manifest["seed"],
                "budget": budget,
                "etnos": etnos,
                "candidates": candidates,
            },
        ),
    )
    for _task, row in zip(tasks, results):
        rows.append(row)
    for cid in top_ids:
        candidate_rows = [r for r in rows if r["candidate_id"] == cid]
        deltas = [float(r["delta_dynamic_score"]) for r in candidate_rows]
        survival_rates = [float(r["survival_rate"]) for r in candidate_rows]
        spread = max(deltas) - min(deltas)
        if spread <= 0.05 and min(survival_rates) >= 0.8:
            status = "passed"
        elif spread > 0.1 or min(survival_rates) < 0.8:
            status = "failed"
        else:
            status = "inconclusive"
        summary.append(
            {
                "candidate_id": cid,
                "status": status,
                "delta_spread": round(spread, 6),
                "ranking_stability": "passed" if status == "passed" else status,
                "mean_delta_dynamic_score": round(statistics.mean(deltas), 6),
                "min_survival_rate": round(min(survival_rates), 6),
            }
        )
    write_csv(out_dir / "convergence.csv", rows)
    payload = {"candidates": summary, "blockers": []}
    if any(item["status"] == "failed" for item in summary):
        payload["blockers"].append("numerical_convergence_failed")
        merge_blocker(
            run_dir,
            {
                "blocker_id": "numerical_convergence_failed",
                "severity": "science_limit",
                "message": "A convergência numérica V2 falhou para ao menos um top candidato.",
            },
        )
    write_json(out_dir / "convergence_summary.json", payload)
    append_event(run_dir, "v2_convergence_completed", rows=len(rows))
    refresh_v2_report(run_dir)
    return out_dir


def validate_top(run_dir: str | Path, top: int = 5, integrator: str = "ias15", max_workers: int | None = None) -> Path:
    run_dir, manifest, budget, weights, etnos, giants, candidates, ranking = _context(run_dir)
    out_dir = ensure_dir(run_dir / "validation")
    rows: list[dict] = []
    summary: list[dict] = []
    whfast_by_id = {row["candidate_id"]: float(row["delta_dynamic_score"]) for row in ranking}
    append_event(run_dir, "v2_ias15_started", top=top, integrator=integrator)
    top_ids = top_candidate_ids(ranking, top)
    tasks = [(cid, integrator) for cid in top_ids]
    results = run_parallel_map(
        _validate_worker,
        tasks,
        max_workers=max_workers,
        initializer=_init_robustness_worker,
        initargs=(
            {
                "giants": giants,
                "weights": weights,
                "seed": manifest["seed"],
                "budget": budget,
                "etnos": etnos,
                "candidates": candidates,
                "whfast_by_id": whfast_by_id,
            },
        ),
    )
    for _task, row in zip(tasks, results):
        rows.append(row)
        summary.append({"candidate_id": row["candidate_id"], "status": row["status"], "same_delta_sign": row["same_delta_sign"]})
    write_csv(out_dir / "ias15_validation.csv", rows)
    write_json(out_dir / "ias15_summary.json", {"candidates": summary})
    append_event(run_dir, "v2_ias15_completed", rows=len(rows))
    refresh_v2_report(run_dir)
    return out_dir


def build_null_etnos(etnos: list[ETNORecord], rng: random.Random, varpis: list[float], model_name: str) -> list[ETNORecord]:
    if model_name == "shuffle_varpi":
        shuffled = varpis[:]
        rng.shuffle(shuffled)
        return [
            etno.model_copy(update={"omega_deg": normalize_degrees(new_varpi - etno.Omega_deg)})
            for etno, new_varpi in zip(etnos, shuffled, strict=True)
        ]
    if model_name == "randomize_angles":
        return [
            etno.model_copy(
                update={
                    "omega_deg": rng.uniform(0, 360),
                    "Omega_deg": rng.uniform(0, 360),
                    "mean_anomaly_deg": rng.uniform(0, 360),
                }
            )
            for etno in etnos
        ]
    if model_name == "no_p9_catalog_baseline":
        return list(etnos)
    raise ValueError(f"Unknown null model: {model_name}")


def null_models(
    run_dir: str | Path,
    top: int = 5,
    n_shuffles: int = 20,
    models: str | list[str] = "shuffle_varpi",
    max_workers: int | None = None,
) -> Path:
    run_dir, manifest, budget, weights, etnos, giants, candidates, ranking = _context(run_dir)
    out_dir = ensure_dir(run_dir / "robustness")
    rows: list[dict] = []
    percentile_rows: list[dict] = []
    summary: list[dict] = []
    top_ids = top_candidate_ids(ranking, top)
    real_delta = {row["candidate_id"]: float(row["delta_dynamic_score"]) for row in ranking}
    null_deltas: dict[tuple[str, str], list[float]] = {
        (cid, model): [] for cid in top_ids for model in ([item.strip() for item in models.split(",")] if isinstance(models, str) else models)
    }
    rng = random.Random(manifest["seed"])
    model_names = [item.strip() for item in models.split(",")] if isinstance(models, str) else models
    varpis = [normalize_degrees(etno.omega_deg + etno.Omega_deg) for etno in etnos]
    null_budget = budget
    if budget.null_model_integration_years:
        null_budget = budget.model_copy(update={"integration_years": budget.null_model_integration_years})
    append_event(run_dir, "v2_null_models_started", top=top, n_shuffles=n_shuffles, models=model_names)
    reference_candidate = candidates[top_ids[0]] if top_ids else next(iter(candidates.values()))
    # RNG draws (build_null_etnos) stay here in the parent, in the exact
    # sequential order, so the null catalogs are identical regardless of how
    # many workers run the REBOUND branches.
    tasks: list[tuple[str, int, list]] = []
    for model_name in model_names:
        for shuffle_id in range(n_shuffles):
            null_etnos = build_null_etnos(etnos, rng, varpis, model_name)
            tasks.append((model_name, shuffle_id, null_etnos))
    results = run_parallel_map(
        _null_worker,
        tasks,
        max_workers=max_workers,
        initializer=_init_robustness_worker,
        initargs=(
            {
                "giants": giants,
                "weights": weights,
                "seed": manifest["seed"],
                "candidates": candidates,
                "null_budget": null_budget,
                "top_ids": top_ids,
                "real_delta": real_delta,
                "reference_candidate": reference_candidate,
            },
        ),
    )
    for (model_name, _shuffle_id, _null), task_rows in zip(tasks, results):
        for cid, delta, row in task_rows:
            null_deltas[(cid, model_name)].append(delta)
            rows.append(row)
    for cid in top_ids:
        for model_name in model_names:
            values = null_deltas[(cid, model_name)]
            percentile = 100.0 * sum(1 for value in values if value <= real_delta[cid]) / len(values)
            p_like = (sum(1 for value in values if value >= real_delta[cid]) + 1) / (len(values) + 1)
            passed = percentile >= 95.0
            for row in rows:
                if row["candidate_id"] == cid and row["null_model"] == model_name:
                    row["null_percentile"] = round(percentile, 3)
                    row["p_like"] = round(p_like, 6)
                    row["passed"] = passed
            percentile_rows.append(
                {
                    "candidate_id": cid,
                    "null_model": model_name,
                    "real_delta_dynamic_score": real_delta[cid],
                    "null_percentile": round(percentile, 3),
                    "p_like": round(p_like, 6),
                    "passed": passed,
                }
            )
            summary.append(
                {
                    "candidate_id": cid,
                    "null_model": model_name,
                    "runs_total": n_shuffles,
                    "real_delta_dynamic_score": real_delta[cid],
                    "mean_null_delta_dynamic_score": round(statistics.mean(values), 6),
                    "std_null_delta_dynamic_score": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
                    "null_percentile": round(percentile, 3),
                    "p_like": round(p_like, 6),
                    "status": "passed" if passed else "failed",
                }
            )
    payload = {
        "candidates": summary,
        "blockers": [],
        "null_model_budget": {
            "screen_integration_years": budget.integration_years,
            "null_model_integration_years": null_budget.integration_years,
            "note": "Modelos nulos usam REBOUND real, mas podem usar sub-orcamento configurado para manter a bateria executavel.",
        },
    }
    if any(item["status"] == "failed" for item in summary):
        payload["blockers"].append("null_model_not_exceeded")
        merge_blocker(
            run_dir,
            {
                "blocker_id": "null_model_not_exceeded",
                "severity": "science_limit",
                "message": "O delta real não se destacou dos modelos nulos simples para ao menos um top candidato.",
            },
        )
    write_csv(out_dir / "null_models.csv", rows)
    write_csv(out_dir / "null_model_percentiles.csv", percentile_rows)
    write_json(out_dir / "null_models_summary.json", payload)
    append_event(run_dir, "v2_null_models_completed", rows=len(rows))
    refresh_v2_report(run_dir)
    return out_dir


def build_null_row(candidate_id: str, model_name: str, shuffle_id: int, real_delta: float, null_delta: float) -> dict:
    return {
        "candidate_id": candidate_id,
        "null_model": model_name,
        "shuffle_id": shuffle_id,
        "real_delta_dynamic_score": real_delta,
        "null_delta_dynamic_score": null_delta,
        "null_percentile": "",
        "p_like": "",
        "passed": "",
    }


def merge_blocker(run_dir: Path, blocker: dict) -> None:
    path = run_dir / "audit" / "blockers.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"blockers": []}
    existing = {item.get("blocker_id") for item in data.get("blockers", [])}
    if blocker["blocker_id"] not in existing:
        data.setdefault("blockers", []).append(blocker)
        write_json(path, data)
        sync_root_copy(run_dir, "audit/blockers.json", "blockers.json")


def remove_blocker(run_dir: Path, blocker_id: str) -> bool:
    """Remove a blocker by blocker_id from the run's audit/blockers.json.

    Companion to merge_blocker (which only ever appends): same read /
    write / root-copy sync pattern, but filters the matching blocker out
    instead of adding one. Returns True if the file was changed; returns
    False without writing anything when the file is missing or the
    blocker is not present (idempotent).
    """
    path = run_dir / "audit" / "blockers.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    remaining = [item for item in data.get("blockers", []) if item.get("blocker_id") != blocker_id]
    if len(remaining) == len(data.get("blockers", [])):
        return False
    data["blockers"] = remaining
    write_json(path, data)
    sync_root_copy(run_dir, "audit/blockers.json", "blockers.json")
    return True


def refresh_v2_report(run_dir: str | Path) -> Path:
    run_dir = Path(run_dir)
    manifest = read_manifest(run_dir)
    ranking = read_csv_dicts(run_dir / "results" / "ranking.csv")
    ranking_summary = json.loads((run_dir / "results" / "ranking_summary.json").read_text(encoding="utf-8"))
    blockers = json.loads((run_dir / "audit" / "blockers.json").read_text(encoding="utf-8")).get("blockers", [])
    v2 = load_post_v2_text(run_dir)
    ranking = apply_v2_evidence(run_dir, ranking)
    ranking = normalize_metric_columns(ranking)
    write_csv(run_dir / "results" / "ranking.csv", ranking, RANKING_FIELDS)
    report = build_report(manifest, ranking, ranking_summary, blockers, v2=v2)
    report_path = run_dir / "reports" / "report.md"
    report_path.write_text(report, encoding="utf-8")
    (run_dir / "presentation" / "summary_for_presentation.md").write_text(
        build_summary_for_presentation(manifest, ranking, ranking_summary),
        encoding="utf-8",
    )
    write_root_copies(run_dir)
    append_event(run_dir, "v2_report_refreshed")
    return report_path


def _summary_by_id(path: Path, key: str = "candidates") -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["candidate_id"]: item for item in data.get(key, [])}


def _read_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_v2_evidence(run_dir: Path, ranking: list[dict]) -> list[dict]:
    loo = _summary_by_id(run_dir / "robustness" / "leave_one_out_summary.json")
    conv = _summary_by_id(run_dir / "robustness" / "convergence_summary.json")
    ias = _summary_by_id(run_dir / "validation" / "ias15_summary.json")
    nulls_by_candidate = _null_summary_by_candidate(run_dir / "robustness" / "null_models_summary.json")
    bias = _read_json_if_exists(run_dir / "diagnostics" / "selection_bias.json")
    for row in ranking:
        cid = row["candidate_id"]
        if row.get("scientific_status") in {"invalid", "rejected"}:
            row["evidence_level"] = "none"
            continue
        level = "weak"
        if loo.get(cid, {}).get("robustness_score", 0) < 0.5:
            level = "weak"
        if conv.get(cid, {}).get("status") == "failed":
            row["scientific_status"] = "inconclusive"
            level = "weak"
        if ias.get(cid, {}).get("status") == "rejected_after_ias15":
            row["scientific_status"] = "rejected_after_validation"
            row["classification_reason"] = "ias15_contradicted_whfast"
            level = "none"
        null_items = nulls_by_candidate.get(cid, [])
        null_passed = bool(null_items) and all(item.get("status") == "passed" for item in null_items)
        if null_items:
            row["null_model_score"] = round(sum(float(item.get("null_percentile", 0)) for item in null_items) / (100 * len(null_items)), 6)
        if null_items and not null_passed:
            level = "weak"
        all_pass = (
            loo.get(cid, {}).get("robustness_score", 0) >= 0.75
            and conv.get(cid, {}).get("status") == "passed"
            and ias.get(cid, {}).get("status") == "validated_preliminarily"
            and null_passed
        )
        if all_pass and level != "none":
            level = "moderate_requires_validation"
        bias_not_ruled_out = bool(bias) and bias.get("real_exceeds_synthetic_R") is False
        if bias_not_ruled_out and level != "none":
            # Removes the upgrade path of a favorable robustness suite, and
            # caps the evidence level at weak. Same philosophy as the
            # config's max_evidence_level_without_bias_model, but inverted:
            # here the bias check EXISTS and found it cannot rule out a
            # selection-artifact origin (max_evidence_level_when_bias_not_ruled_out).
            # Runs that never called the selection-bias-check command keep
            # their previous behavior (no bias file -> no penalty).
            level = "weak"
        row["evidence_level"] = level
    return ranking


def _null_summary_by_candidate(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    output: dict[str, list[dict]] = {}
    for item in data.get("candidates", []):
        output.setdefault(item["candidate_id"], []).append(item)
    return output


def load_v2_text(run_dir: Path) -> dict:
    def describe(path: Path, label: str) -> str:
        if not path.exists():
            return "Não executado."
        data = json.loads(path.read_text(encoding="utf-8"))
        lines = []
        for item in data.get("candidates", []):
            fields = ", ".join(f"{k}={v}" for k, v in item.items() if k != "candidate_id")
            lines.append(f"- `{item['candidate_id']}`: {fields}")
        blockers = data.get("blockers", [])
        if blockers:
            lines.append(f"Blockers V2: {', '.join(blockers)}")
        if data.get("null_model_budget"):
            budget_note = data["null_model_budget"]
            lines.append(
                "Null model budget: "
                f"screen_years={budget_note.get('screen_integration_years')}, "
                f"null_years={budget_note.get('null_model_integration_years')}"
            )
        return "\n".join(lines) if lines else f"{label} executado, sem candidatos no resumo."

    return {
        "leave_one_out": describe(run_dir / "robustness" / "leave_one_out_summary.json", "Leave-one-out"),
        "convergence": describe(run_dir / "robustness" / "convergence_summary.json", "Convergência"),
        "ias15": describe(run_dir / "validation" / "ias15_summary.json", "IAS15"),
        "null_models": describe(run_dir / "robustness" / "null_models_summary.json", "Modelos nulos"),
    }


def load_post_v2_text(run_dir: Path) -> dict:
    def describe(path: Path, label: str) -> str:
        if not path.exists():
            return "Não executado."
        data = json.loads(path.read_text(encoding="utf-8"))
        lines = []
        for item in data.get("candidates", []):
            fields = ", ".join(f"{k}={v}" for k, v in item.items() if k != "candidate_id")
            lines.append(f"- `{item['candidate_id']}`: {fields}")
        blockers = data.get("blockers", [])
        if blockers:
            lines.append(f"Blockers V2: {', '.join(blockers)}")
        return "\n".join(lines) if lines else f"{label} executado, sem candidatos no resumo."

    def read_text_if_exists(path: Path, fallback: str = "Não executado.") -> str:
        if not path.exists():
            return fallback
        return path.read_text(encoding="utf-8").strip() or fallback

    def seed_stability() -> str:
        path = run_dir / "results" / "seed_stability_summary.json"
        if not path.exists():
            return "Não executado."
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("enabled"):
            return "Não executado; budget de seed única."
        lines = []
        for item in data.get("candidates", []):
            lines.append(
                f"- `{item['candidate_id']}`: appearances_in_top10={item['appearances_in_top10']}, "
                f"mean_rank={item['mean_rank']}, std_rank={item['std_rank']}, "
                f"mean_delta={item['mean_delta']}, seed_stability_score={item['seed_stability_score']}"
            )
        return "\n".join(lines) if lines else "Executado, sem candidatos no resumo."

    return {
        "leave_one_out": describe(run_dir / "robustness" / "leave_one_out_summary.json", "Leave-one-out"),
        "convergence": describe(run_dir / "robustness" / "convergence_summary.json", "Convergência"),
        "ias15": describe(run_dir / "validation" / "ias15_summary.json", "IAS15"),
        "null_models": describe(run_dir / "robustness" / "null_models_summary.json", "Modelos nulos"),
        "scoring_diagnosis": read_text_if_exists(run_dir / "diagnostics" / "scoring_diagnosis.md"),
        "null_model_diagnosis": read_text_if_exists(run_dir / "diagnostics" / "null_model_diagnosis.md"),
        "seed_stability": seed_stability(),
        "candidate_families": read_text_if_exists(run_dir / "analysis" / "candidate_families_summary.md"),
        "catalog_status": read_text_if_exists(
            ROOT / "data" / "etnos" / "catalog_validation_report.md",
            "Catalogo V2 parcial; verificar data/etnos/catalog_validation_report.md.",
        ),
    }

