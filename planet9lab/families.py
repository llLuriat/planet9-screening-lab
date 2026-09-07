from __future__ import annotations

import json
import math
from pathlib import Path

from .artifacts import ensure_dir, read_csv_dicts, write_csv, write_text
from .run import append_event

PARAMETERS = [
    "mass_earth",
    "a_au",
    "e",
    "i_deg",
    "omega_deg",
    "Omega_deg",
    "mean_anomaly_deg",
]

MIN_SCALES = {
    "mass_earth": 20.0,
    "a_au": 800.0,
    "e": 0.5,
    "i_deg": 90.0,
    "omega_deg": 180.0,
    "Omega_deg": 180.0,
    "mean_anomaly_deg": 180.0,
}


def candidate_families(run_dir: str | Path, top: int = 20) -> Path:
    run_dir = Path(run_dir)
    out_dir = ensure_dir(run_dir / "analysis")
    ranking = read_csv_dicts(run_dir / "results" / "ranking.csv")[:top]
    candidates = {row["candidate_id"]: row for row in read_csv_dicts(run_dir / "candidates_input.csv")}
    selected = [candidates[row["candidate_id"]] | row for row in ranking if row["candidate_id"] in candidates]
    families = group_candidates(selected)
    rows = []
    for family_id, members in enumerate(families, start=1):
        deltas = [float(member["delta_dynamic_score"]) for member in members]
        for member in members:
            rows.append(
                {
                    "family_id": family_id,
                    "candidate_id": member["candidate_id"],
                    "rank": member["rank"],
                    "family_size": len(members),
                    "delta_dynamic_score": member["delta_dynamic_score"],
                    "scientific_status": member["scientific_status"],
                    "mass_earth": member["mass_earth"],
                    "a_au": member["a_au"],
                    "e": member["e"],
                    "i_deg": member["i_deg"],
                    "omega_deg": member["omega_deg"],
                    "Omega_deg": member["Omega_deg"],
                    "mean_anomaly_deg": member["mean_anomaly_deg"],
                    "family_mean_delta": round(sum(deltas) / len(deltas), 6),
                }
            )
    write_csv(out_dir / "candidate_families.csv", rows)
    write_text(out_dir / "candidate_families_summary.md", family_summary_markdown(families))
    append_event(run_dir, "candidate_families_completed", top=top, family_count=len(families))
    return out_dir


def group_candidates(candidates: list[dict], threshold: float = 0.42) -> list[list[dict]]:
    families: list[list[dict]] = []
    if not candidates:
        return families
    ranges = parameter_ranges(candidates)
    for candidate in candidates:
        placed = False
        for family in families:
            if distance(candidate, family[0], ranges) <= threshold:
                family.append(candidate)
                placed = True
                break
        if not placed:
            families.append([candidate])
    return families


def parameter_ranges(candidates: list[dict]) -> dict[str, float]:
    ranges = {}
    for name in PARAMETERS:
        values = [float(candidate[name]) for candidate in candidates]
        ranges[name] = max(max(values) - min(values), MIN_SCALES[name])
    return ranges


def distance(left: dict, right: dict, ranges: dict[str, float]) -> float:
    parts = []
    for name in PARAMETERS:
        diff = abs(float(left[name]) - float(right[name]))
        if name in {"omega_deg", "Omega_deg", "mean_anomaly_deg"}:
            diff = min(diff, 360.0 - diff)
            scale = 180.0
        else:
            scale = ranges[name]
        parts.append((diff / max(scale, 1e-9)) ** 2)
    return math.sqrt(sum(parts) / len(parts))


def family_summary_markdown(families: list[list[dict]]) -> str:
    if not families:
        return "# Candidate Families\n\nNenhum candidato disponivel para agrupamento.\n"
    multi = [family for family in families if len(family) > 1]
    if multi:
        verdict = "familia de candidatos"
    elif len(families) == 1:
        verdict = "candidato isolado"
    else:
        verdict = "nenhum padrao robusto"
    lines = [
        "# Candidate Families",
        "",
        f"diagnostico: {verdict}",
        f"families_total: {len(families)}",
        "",
    ]
    for family_id, family in enumerate(families, start=1):
        member_ids = ", ".join(member["candidate_id"] for member in family)
        deltas = [float(member["delta_dynamic_score"]) for member in family]
        lines.append(
            f"- family_{family_id}: size={len(family)}, members={member_ids}, "
            f"mean_delta={round(sum(deltas) / len(deltas), 6)}"
        )
    lines.append("")
    lines.append("Este agrupamento e diagnostico simples; nao e evidencia orbital independente.")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({"diagnostico": verdict, "families_total": len(families)}, indent=2))
    lines.append("```")
    return "\n".join(lines) + "\n"
