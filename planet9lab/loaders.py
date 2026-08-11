from __future__ import annotations

import csv
from pathlib import Path

from .config import load_yaml
from .schemas import BudgetConfig, ETNORecord, GiantPlanetRecord, P9Candidate


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_etnos(path: str | Path) -> list[ETNORecord]:
    return [ETNORecord.model_validate(row) for row in read_csv(path)]


def load_giants(path: str | Path) -> list[GiantPlanetRecord]:
    return [GiantPlanetRecord.model_validate(row) for row in read_csv(path)]


def load_candidates(path: str | Path, max_candidates: int | None = None) -> list[P9Candidate]:
    rows = [P9Candidate.model_validate(row) for row in read_csv(path)]
    return rows[:max_candidates] if max_candidates else rows


def load_single_candidate_config(path: str | Path) -> P9Candidate:
    return P9Candidate.model_validate(load_yaml(path))


def load_budget(path: str | Path) -> BudgetConfig:
    return BudgetConfig.model_validate(load_yaml(path))


def included_etnos(etnos: list[ETNORecord]) -> list[ETNORecord]:
    return [item for item in etnos if item.selection_included]


def selected_etnos(
    etnos: list[ETNORecord],
    selection_config: dict,
) -> tuple[list[ETNORecord], list[dict]]:
    """Selection with an explicit, auditable reason per rejected ETNO
    (min_a_au, min_q_au, validation_status), used by the V2 catalog
    (catalog_v2.csv) and the robustness commands. Separate from
    `included_etnos`, which just respects the catalog's own
    `selection_included` flag."""
    min_a_au = float(selection_config.get("min_a_au", 0))
    min_q_au = float(selection_config.get("min_q_au", 0))
    allow_unvalidated = bool(selection_config.get("allow_unvalidated", False))

    selected: list[ETNORecord] = []
    rejected: list[dict] = []
    for item in included_etnos(etnos):
        reasons: list[str] = []
        q_au = item.a_au * (1 - item.e)
        if item.a_au < min_a_au:
            reasons.append("a_au_below_threshold")
        if q_au < min_q_au:
            reasons.append("q_au_below_threshold")
        if item.validation_status == "unvalidated" and not allow_unvalidated:
            reasons.append("unvalidated_etno")

        if reasons:
            rejected.append(
                {
                    "name": item.name,
                    "a_au": item.a_au,
                    "q_au": q_au,
                    "validation_status": item.validation_status,
                    "reasons": reasons,
                }
            )
        else:
            selected.append(item)

    return selected, rejected

