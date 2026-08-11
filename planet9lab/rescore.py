from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .artifacts import ensure_dir, read_csv_dicts, write_csv, write_json, write_text
from .config import load_yaml
from .hashing import file_hash
from .metrics import dynamic_score, ranking_summary
from .policy import classify_candidate
from .run import RANKING_FIELDS, read_manifest


def rescore_run(run_dir: str | Path, weights_path: str | Path) -> Path:
    run_dir = Path(run_dir)
    weights = load_yaml(weights_path)
    old_manifest = read_manifest(run_dir)
    original_ranking = read_csv_dicts(run_dir / "results" / "ranking.csv")
    rescored = []
    for row in original_ranking:
        with_metrics = {
            "apsidal_clustering_R": row["apsidal_clustering_R_with_p9"],
            "anti_alignment_score": row["anti_alignment_score_with_p9"],
            "survival_rate": row["survival_rate_with_p9"],
            "stability_score": row["stability_score_with_p9"],
            "numerical_health_score": row["numerical_health_score_with_p9"],
        }
        without_metrics = {
            "apsidal_clustering_R": row["apsidal_clustering_R_without_p9"],
            "anti_alignment_score": row["anti_alignment_score_without_p9"],
            "survival_rate": row["survival_rate_without_p9"],
            "stability_score": row["stability_score_without_p9"],
            "numerical_health_score": row["numerical_health_score_without_p9"],
        }
        with_score = dynamic_score(with_metrics, weights)
        without_score = dynamic_score(without_metrics, weights)
        delta = round(with_score - without_score, 6)
        scientific_status, reason, raw_evidence = classify_candidate(
            delta,
            float(row["survival_rate_with_p9"]) if row["survival_rate_with_p9"] else None,
            weights,
            blockers=row.get("blockers", "").split(";") if row.get("blockers") else [],
        )
        new_row = dict(row)
        new_row.update(
            {
                "dynamic_score_with_p9": with_score,
                "dynamic_score_without_p9": without_score,
                "delta_dynamic_score": delta,
                "scientific_status": scientific_status,
                "classification_reason": reason,
                "evidence_level": "none" if raw_evidence == "none" else row.get("evidence_level", raw_evidence),
            }
        )
        rescored.append(new_row)
    rescored.sort(
        key=lambda item: (
            item.get("scientific_status") == "invalid",
            -float(item["delta_dynamic_score"]) if item.get("delta_dynamic_score") not in {"", None} else 0,
        )
    )
    for rank, row in enumerate(rescored, start=1):
        row["rank"] = rank
    rescore_dir = ensure_dir(run_dir / f"rescore_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}Z")
    old_hash = old_manifest["hashes"].get("scoring_hash")
    new_hash = file_hash(weights_path)
    write_csv(rescore_dir / "ranking.csv", rescored, RANKING_FIELDS)
    write_json(rescore_dir / "ranking_summary.json", ranking_summary(rescored))
    write_json(rescore_dir / "rescore_hashes.json", {"old_scoring_hash": old_hash, "new_scoring_hash": new_hash})
    write_text(rescore_dir / "old_scoring_hash.txt", str(old_hash) + "\n")
    write_text(rescore_dir / "new_scoring_hash.txt", str(new_hash) + "\n")
    write_text(
        rescore_dir / "rescore_report.md",
        "\n".join(
            [
                "# Rescore Report",
                "",
                f"Source run: {run_dir}",
                f"old_scoring_hash: {old_hash}",
                f"new_scoring_hash: {new_hash}",
                "",
                "Ranking original preservado; este rescore não reexecutou simulações.",
            ]
        )
        + "\n",
    )
    return rescore_dir

