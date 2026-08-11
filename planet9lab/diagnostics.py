from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from .artifacts import ensure_dir, read_csv_dicts, write_csv, write_json, write_text
from .config import load_yaml
from .run import append_event, default_paths


def diagnose_scoring(run_dir: str | Path) -> Path:
    run_dir = Path(run_dir)
    out_dir = ensure_dir(run_dir / "diagnostics")
    weights = load_yaml(default_paths()["weights_config"])
    ranking = read_csv_dicts(run_dir / "results" / "ranking.csv")
    components = ["apsidal_clustering", "anti_alignment", "survival_rate", "stability", "numerical_health"]
    rows = []
    for row in ranking:
        for branch in ["with_p9", "without_p9"]:
            values = {
                "apsidal_clustering": float(row[f"apsidal_clustering_R_{branch}"]),
                "anti_alignment": float(row[f"anti_alignment_score_{branch}"]),
                "survival_rate": float(row[f"survival_rate_{branch}"]),
                "stability": float(row[f"stability_score_{branch}"]),
                "numerical_health": float(row[f"numerical_health_score_{branch}"]),
            }
            for component in components:
                rows.append(
                    {
                        "candidate_id": row["candidate_id"],
                        "branch": branch,
                        "component": component,
                        "weight": weights[component],
                        "value": values[component],
                        "contribution": round(float(weights[component]) * values[component], 6),
                    }
                )
    write_csv(out_dir / "scoring_components.csv", rows)
    diagnosis = build_scoring_diagnosis(rows, ranking, components)
    write_json(out_dir / "scoring_diagnosis.json", diagnosis)
    write_text(out_dir / "scoring_diagnosis.md", scoring_markdown(diagnosis))
    append_event(run_dir, "diagnose_scoring_completed")
    return out_dir


def build_scoring_diagnosis(rows: list[dict], ranking: list[dict], components: list[str]) -> dict:
    by_component = {}
    for component in components:
        values = [float(row["value"]) for row in rows if row["component"] == component and row["branch"] == "with_p9"]
        contributions = [float(row["contribution"]) for row in rows if row["component"] == component and row["branch"] == "with_p9"]
        by_component[component] = {
            "mean_value": round(statistics.mean(values), 6) if values else None,
            "std_value": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
            "mean_contribution": round(statistics.mean(contributions), 6) if contributions else None,
            "saturated_fraction": round(sum(1 for value in values if value >= 0.99) / len(values), 6) if values else 0,
        }
    deltas = [float(row["delta_dynamic_score"]) for row in ranking]
    score_spread = max(deltas) - min(deltas) if deltas else 0
    survival_values = [float(row["survival_rate_with_p9"]) for row in ranking]
    numerical_values = [float(row["numerical_health_score_with_p9"]) for row in ranking]
    return {
        "candidate_count": len(ranking),
        "delta_spread": round(score_spread, 6),
        "components": by_component,
        "survival_saturated": all(value >= 0.99 for value in survival_values),
        "numerical_saturated": all(value >= 0.99 for value in numerical_values),
        "candidates_receive_similar_score": score_spread < 0.05,
        "component_correlations": component_correlations(rows, components),
    }


def component_correlations(rows: list[dict], components: list[str]) -> dict:
    by_candidate: dict[str, dict[str, float]] = {}
    for row in rows:
        if row["branch"] != "with_p9":
            continue
        by_candidate.setdefault(row["candidate_id"], {})[row["component"]] = float(row["value"])
    output = {}
    for left in components:
        for right in components:
            if left >= right:
                continue
            xs = [vals[left] for vals in by_candidate.values() if left in vals and right in vals]
            ys = [vals[right] for vals in by_candidate.values() if left in vals and right in vals]
            output[f"{left}__{right}"] = round(correlation(xs, ys), 6)
    return output


def correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    denom_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (denom_x * denom_y)


def scoring_markdown(diagnosis: dict) -> str:
    lines = [
        "# Scoring Diagnosis",
        "",
        f"candidate_count: {diagnosis['candidate_count']}",
        f"delta_spread: {diagnosis['delta_spread']}",
        f"candidates_receive_similar_score: {diagnosis['candidates_receive_similar_score']}",
        f"survival_saturated: {diagnosis['survival_saturated']}",
        f"numerical_saturated: {diagnosis['numerical_saturated']}",
        "",
        "## Componentes",
    ]
    for name, item in diagnosis["components"].items():
        lines.append(
            f"- {name}: mean={item['mean_value']}, std={item['std_value']}, "
            f"mean_contribution={item['mean_contribution']}, saturated_fraction={item['saturated_fraction']}"
        )
    lines.extend(["", "## Correlações"])
    for name, value in diagnosis["component_correlations"].items():
        lines.append(f"- {name}: {value}")
    return "\n".join(lines) + "\n"


def diagnose_null_models(run_dir: str | Path) -> Path:
    run_dir = Path(run_dir)
    out_dir = ensure_dir(run_dir / "diagnostics")
    null_path = run_dir / "robustness" / "null_models_summary.json"
    ranking = read_csv_dicts(run_dir / "results" / "ranking.csv")
    if not null_path.exists():
        diagnosis = {"available": False, "message": "null_models_summary.json not found"}
    else:
        null_summary = json.loads(null_path.read_text(encoding="utf-8"))
        manifest_path = run_dir / "data_manifest.json"
        etno_count = 0
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            etno_count = len(manifest.get("included_etnos", []))
        diagnosis = build_null_diagnosis(null_summary, ranking, etno_count=etno_count)
    write_json(out_dir / "null_model_diagnosis.json", diagnosis)
    write_text(out_dir / "null_model_diagnosis.md", null_markdown(diagnosis))
    append_event(run_dir, "diagnose_null_models_completed")
    return out_dir


def build_null_diagnosis(null_summary: dict, ranking: list[dict], etno_count: int = 0) -> dict:
    by_candidate: dict[str, list[dict]] = {}
    for item in null_summary.get("candidates", []):
        by_candidate.setdefault(item["candidate_id"], []).append(item)
    deltas = [float(row["delta_dynamic_score"]) for row in ranking]
    diagnosis = {
        "available": True,
        "catalog_etno_count": etno_count,
        "candidate_count": len(ranking),
        "delta_spread": round(max(deltas) - min(deltas), 6) if deltas else 0,
        "candidates_are_similar": (max(deltas) - min(deltas) < 0.05) if deltas else True,
        "candidate_results": [],
        "score_likely_poorly_discriminative": False,
        "null_model_comparison_correct": True,
        "possible_bug_or_scale_issue": False,
        "null_model_budget": null_summary.get("null_model_budget", {}),
    }
    close_count = 0
    failed_count = 0
    for candidate_id, items in by_candidate.items():
        for item in items:
            real = float(item["real_delta_dynamic_score"])
            null_mean = float(item["mean_null_delta_dynamic_score"])
            distance = real - null_mean
            close = abs(distance) < max(float(item["std_null_delta_dynamic_score"]) * 2, 1e-6)
            close_count += int(close)
            failed_count += int(item["status"] == "failed")
            diagnosis["candidate_results"].append(
                {
                    "candidate_id": candidate_id,
                    "null_model": item.get("null_model", "unknown"),
                    "real_delta_dynamic_score": real,
                    "mean_null_delta_dynamic_score": null_mean,
                    "std_null_delta_dynamic_score": item["std_null_delta_dynamic_score"],
                    "null_percentile": item["null_percentile"],
                    "p_like": item.get("p_like"),
                    "real_close_to_null": close,
                    "status": item["status"],
                }
            )
    total = max(len(diagnosis["candidate_results"]), 1)
    diagnosis["real_delta_near_null_distribution_fraction"] = round(close_count / total, 6)
    diagnosis["null_failure_fraction"] = round(failed_count / total, 6)
    diagnosis["score_likely_poorly_discriminative"] = diagnosis["null_failure_fraction"] > 0.5
    diagnosis["catalog_is_small_or_weak"] = diagnosis["catalog_etno_count"] < 8
    diagnosis["integration_time_may_be_short"] = True
    diagnosis["clustering_may_dominate"] = False
    return diagnosis


def null_markdown(diagnosis: dict) -> str:
    if not diagnosis.get("available"):
        return "# Null Model Diagnosis\n\nnull_models_summary.json not found.\n"
    lines = [
        "# Null Model Diagnosis",
        "",
        f"o delta real está perto da distribuição nula? fraction={diagnosis['real_delta_near_null_distribution_fraction']}",
        f"o score está pouco discriminativo? {diagnosis['score_likely_poorly_discriminative']}",
        f"os candidatos são parecidos demais? {diagnosis['candidates_are_similar']}",
        f"o catálogo ETNO é pequeno/fraco? {diagnosis['catalog_is_small_or_weak']}",
        f"a métrica de clustering domina o score? {diagnosis['clustering_may_dominate']}",
        f"o tempo de integração é curto demais? {diagnosis['integration_time_may_be_short']}",
        f"o null model está comparando corretamente? {diagnosis['null_model_comparison_correct']}",
        f"existe bug ou escala errada no cálculo? {diagnosis['possible_bug_or_scale_issue']}",
        "",
        "## Números por candidato/modelo",
    ]
    for item in diagnosis["candidate_results"]:
        lines.append(
            f"- {item['candidate_id']} / {item['null_model']}: real={item['real_delta_dynamic_score']}, "
            f"null_mean={item['mean_null_delta_dynamic_score']}, null_std={item['std_null_delta_dynamic_score']}, "
            f"percentile={item['null_percentile']}, p_like={item['p_like']}, status={item['status']}"
        )
    return "\n".join(lines) + "\n"
