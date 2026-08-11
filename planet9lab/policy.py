from __future__ import annotations

import math

from .schemas import ALLOWED_CLAIMS, EVIDENCE_LEVELS, PROHIBITED_CLAIMS


def observational_bias_blockers(bias_config: dict) -> list[dict]:
    if bias_config.get("bias_model") == "none" and bias_config.get("blocker_if_none", False):
        return [
            {
                "blocker_id": "no_observational_bias_model",
                "severity": "science_limit",
                "message": "Não há modelo completo de viés observacional nesta versão; portanto, o resultado é apenas screening exploratório.",
            }
        ]
    return []


def rebound_blockers(rebound_used: bool) -> list[dict]:
    if rebound_used:
        return []
    return [
        {
            "blocker_id": "rebound_not_available",
            "severity": "critical",
            "message": "REBOUND real não foi usado nesta execução; portanto, esta run não é screening físico validado.",
        }
    ]


def no_control_blocker() -> dict:
    return {
        "blocker_id": "no_control_run",
        "severity": "critical",
        "message": "Candidato não possui controle completo com e sem P9.",
    }


def evidence_cap_from_blockers(blocker_ids: list[str], bias_config: dict) -> str:
    if "rebound_not_available" in blocker_ids or "no_control_run" in blocker_ids:
        return "none"
    if "no_observational_bias_model" in blocker_ids and bias_config.get("bias_model") == "none":
        cap = bias_config.get("max_evidence_level_without_bias_model", "weak")
        return "weak" if cap == "weak" else "exploratory"
    return "moderate_requires_validation"


def apply_evidence_cap(raw_level: str, cap: str) -> str:
    order = ["none", "weak", "exploratory", "moderate_requires_validation"]
    if raw_level not in EVIDENCE_LEVELS:
        raw_level = "none"
    return order[min(order.index(raw_level), order.index(cap))]


def classify_candidate(
    delta: float | None,
    survival_rate: float | None,
    weights_config: dict,
    blockers: list[str] | None = None,
    control_complete: bool = True,
) -> tuple[str, str, str]:
    blockers = blockers or []
    if (not control_complete) or "no_control_run" in blockers:
        return "invalid", "missing_control_pair", "none"
    if delta is None or not math.isfinite(delta):
        return "invalid", "delta_dynamic_score_invalid", "none"
    if "rebound_not_available" in blockers:
        return "exploratory_screening_only", "rebound_not_available", "none"
    if survival_rate is None or not math.isfinite(survival_rate):
        return "invalid", "survival_rate_invalid", "none"
    if survival_rate < float(weights_config.get("min_survival_rate", 0.8)):
        return "rejected", "survival_rate_below_threshold", "none"
    if delta >= float(weights_config.get("min_delta_of_interest", 0.08)):
        return "candidate_of_interest", "delta_dynamic_score_above_threshold", "exploratory"
    if delta <= float(weights_config.get("bad_delta_threshold", 0.0)):
        return "rejected", "did_not_improve_control", "none"
    return "weak_candidate", "improvement_below_candidate_threshold", "weak"


def global_status(rows: list[dict], invalid: bool = False) -> str:
    if invalid:
        return "invalid_run"
    valid = [row for row in rows if row.get("scientific_status") != "invalid"]
    if not valid:
        return "invalid_run"
    interesting = [row for row in valid if row.get("scientific_status") == "candidate_of_interest"]
    if interesting:
        return "candidate_of_interest_within_protocol"
    if any(row.get("scientific_status") == "weak_candidate" for row in valid):
        return "inconclusive"
    return "no_candidate_found"


def claim_for_status(status: str) -> str:
    if status == "candidate_of_interest_within_protocol":
        return "candidate_of_interest_within_protocol"
    if status == "no_candidate_found":
        return "no_candidate_found"
    return "inconclusive"


def validate_claim_policy() -> None:
    forbidden_tokens = ["confirmed", "found", "proved", "discovered"]
    for claim in ALLOWED_CLAIMS:
        for token in forbidden_tokens:
            if claim == "no_candidate_found" and token == "found":
                continue
            if token in claim:
                raise ValueError(f"Allowed claim contains prohibited token: {claim}")
    if not PROHIBITED_CLAIMS.isdisjoint(ALLOWED_CLAIMS):
        raise ValueError("Prohibited claims overlap allowed claims")

