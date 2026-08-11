"""Canonical V1 schemas and validation."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ValidationStatus = Literal["validated", "partial", "unvalidated"]
EvidenceLevel = Literal["none", "weak", "exploratory", "moderate_requires_validation"]
ScientificStatus = Literal[
    "invalid",
    "rejected",
    "weak_candidate",
    "candidate_of_interest",
    "needs_validation",
    "exploratory_screening_only",
    "no_candidate_found",
    "inconclusive",
    "candidate_of_interest_within_protocol",
]
OperationalStatus = Literal["pending", "running", "completed", "failed", "invalid"]


class OrbitalAnglesMixin(BaseModel):
    i_deg: float = Field(ge=0, le=180)
    omega_deg: float = Field(ge=0, lt=360)
    Omega_deg: float = Field(ge=0, lt=360)
    mean_anomaly_deg: float = Field(ge=0, lt=360)

    @field_validator("i_deg", "omega_deg", "Omega_deg", "mean_anomaly_deg")
    @classmethod
    def finite_angle(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("angle must be finite")
        return value


class P9Candidate(OrbitalAnglesMixin):
    candidate_id: str = Field(min_length=1)
    mass_earth: float = Field(gt=0)
    a_au: float = Field(gt=0)
    e: float = Field(ge=0, lt=1)


class ETNORecord(OrbitalAnglesMixin):
    name: str = Field(min_length=1)
    a_au: float = Field(gt=0)
    e: float = Field(ge=0, lt=1)
    epoch: str = Field(min_length=1)
    frame: str = Field(min_length=1)
    source: str = Field(min_length=1)
    validation_status: ValidationStatus
    selection_included: bool
    selection_reason: str = Field(min_length=1)
    selection_notes: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_fields(cls, data):
        if isinstance(data, dict):
            legacy = {"object_id", "inc_deg", "M_deg"}.intersection(data)
            if legacy:
                raise ValueError(f"legacy ETNO fields are not canonical: {sorted(legacy)}")
        return data


class GiantPlanetRecord(OrbitalAnglesMixin):
    name: str = Field(min_length=1)
    mass_solar: float = Field(gt=0)
    a_au: float = Field(gt=0)
    e: float = Field(ge=0, lt=1)
    epoch: str = Field(min_length=1)


class BudgetConfig(BaseModel):
    integration_years: float = Field(gt=0)
    timestep_years: float = Field(gt=0)
    seeds: list[int] = Field(min_length=1)
    integrator: Literal["whfast", "ias15"] = "whfast"
    max_candidates: int = Field(gt=0)
    checkpoint_interval_years: float | None = Field(default=None, gt=0)
    null_model_integration_years: float | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_budget_aliases(cls, data):
        if isinstance(data, dict):
            data = data.copy()
            if "integration_years" not in data and "screen_t_myr" in data:
                data["integration_years"] = float(data["screen_t_myr"]) * 1_000_000
            if "timestep_years" not in data and "screen_dt_years" in data:
                data["timestep_years"] = data["screen_dt_years"]
            if "max_candidates" not in data and "candidates" in data:
                data["max_candidates"] = data["candidates"]
            if "integrator" not in data and "screen_integrator" in data:
                data["integrator"] = data["screen_integrator"]
            if "null_model_integration_years" not in data and "null_model_t_myr" in data:
                data["null_model_integration_years"] = float(data["null_model_t_myr"]) * 1_000_000
        return data

    @model_validator(mode="after")
    def checkpoint_not_larger_than_run(self) -> BudgetConfig:
        if self.checkpoint_interval_years is not None and self.checkpoint_interval_years > self.integration_years:
            raise ValueError("checkpoint_interval_years cannot exceed integration_years")
        return self


class RunConfig(BaseModel):
    run_id: str
    seed: int
    budget: BudgetConfig
    allow_analytical_fallback: bool = False


class SingleRunResult(BaseModel):
    candidate_id: str
    branch: Literal["with_p9", "without_p9"]
    operational_status: OperationalStatus
    survival_rate: float = Field(ge=0, le=1)
    energy_drift_rel: float | None
    angular_momentum_drift_rel: float | None
    angular_momentum_available: bool
    numerical_health_score: float = Field(ge=0, le=1)
    apsidal_clustering_R: float = Field(ge=0, le=1)
    anti_alignment_score: float = Field(ge=0, le=1)
    stability_score: float = Field(ge=0, le=1)
    lost_etnos: list[str] = Field(default_factory=list)
    numerical_failures: list[str] = Field(default_factory=list)
    rebound_used: bool
    delta_pomega_stable_fraction: float | None = Field(default=None, ge=0, le=1)
    delta_pomega_series_points: int = 0


class ControlPairResult(BaseModel):
    candidate_id: str
    with_p9: SingleRunResult
    without_p9: SingleRunResult
    control_type: str = "same_catalog_with_and_without_p9"
    delta_dynamic_score: float
    comparison: dict


class CandidateClassification(BaseModel):
    candidate_id: str
    scientific_status: ScientificStatus
    operational_status: OperationalStatus
    classification_reason: str
    evidence_level: EvidenceLevel
    blockers: list[str] = Field(default_factory=list)


EVIDENCE_LEVELS = {"none", "weak", "exploratory", "moderate_requires_validation"}
ALLOWED_CLAIMS = {
    "exploratory_screening_only",
    "candidate_of_interest_within_protocol",
    "no_candidate_found",
    "inconclusive",
}
PROHIBITED_CLAIMS = {
    "confirmed_planet9",
    "planet9_found",
    "found_planet9",
    "real_orbit_confirmed",
    "validated_planet9",
    "discovered_planet9",
    "proved_planet9",
}

