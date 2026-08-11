from __future__ import annotations

import json
from pathlib import Path

from .run import candidate_details_from_run, read_manifest


def _blockers(run_dir: str | Path) -> str:
    path = Path(run_dir) / "audit" / "blockers.json"
    if not path.exists():
        return "none"
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = [item.get("blocker_id", "unknown") for item in data.get("blockers", [])]
    return ", ".join(ids) if ids else "none"


def explain_candidate(candidate_id: str, run_dir: str | Path) -> str:
    ranking, metrics, control = candidate_details_from_run(run_dir, candidate_id)
    manifest = read_manifest(run_dir)
    improved: list[str] = []
    worsened: list[str] = []
    for metric in [
        "apsidal_clustering_R",
        "anti_alignment_score",
        "survival_rate",
        "stability_score",
        "numerical_health_score",
    ]:
        with_key = f"{metric}_with_p9" if metric != "survival_rate" else "survival_rate_with_p9"
        without_key = f"{metric}_without_p9" if metric != "survival_rate" else "survival_rate_without_p9"
        if with_key in ranking and without_key in ranking:
            try:
                delta = float(ranking[with_key]) - float(ranking[without_key])
            except ValueError:
                continue
            if delta > 0:
                improved.append(metric)
            elif delta < 0:
                worsened.append(metric)
    lines = [
        f"# Explain Candidate: {candidate_id}",
        "",
        f"Ranking: {ranking['rank']}",
        f"Scientific status: {ranking['scientific_status']}",
        f"Operational status: {ranking['operational_status']}",
        f"Dynamic score with P9: {ranking['dynamic_score_with_p9']}",
        f"Dynamic score without P9: {ranking['dynamic_score_without_p9']}",
        f"Delta dynamic score: {ranking['delta_dynamic_score']}",
        f"Metrics improved: {', '.join(improved) if improved else 'none'}",
        f"Metrics worsened: {', '.join(worsened) if worsened else 'none'}",
        f"Control used: {control.get('control_type', 'unknown')}",
        f"Blockers: {_blockers(run_dir)}",
        f"Evidence level: {ranking['evidence_level']}",
        f"Claim allowed: {ranking['claim_allowed']}",
        f"REBOUND used: {manifest.get('rebound_used')}",
    ]
    return "\n".join(lines) + "\n"


def why_rejected(candidate_id: str, run_dir: str | Path) -> str:
    ranking, metrics, _control = candidate_details_from_run(run_dir, candidate_id)
    lines = [
        f"# Why Rejected: {candidate_id}",
        "",
        f"Scientific status: {ranking['scientific_status']}",
        f"Operational status: {ranking['operational_status']}",
        f"Reason: {ranking['classification_reason']}",
        f"Delta dynamic score: {ranking['delta_dynamic_score']}",
        f"Survival with P9: {ranking['survival_rate_with_p9']}",
        f"Energy drift with P9: {ranking['energy_drift_rel_with_p9']}",
        f"Angular momentum drift with P9: {ranking['angular_momentum_drift_rel_with_p9']}",
        f"ETNOs lost with P9: {metrics.get('lost_etnos_with_p9') or 'none'}",
        f"Numerical failures with P9: {metrics.get('numerical_failures_with_p9') or 'none'}",
        f"Blockers: {ranking.get('blockers') or _blockers(run_dir)}",
    ]
    return "\n".join(lines) + "\n"

