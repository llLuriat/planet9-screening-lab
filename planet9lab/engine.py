from __future__ import annotations

import importlib.util
import logging
import math
from pathlib import Path
from typing import Any

from .artifacts import append_csv_row, read_csv_dicts
from .constants import DEG_TO_RAD, RAD_TO_DEG, earth_mass_to_solar_mass, normalize_degrees
from .metrics import (
    compute_branch_metrics,
    delta_pomega_instant,
    delta_pomega_stability,
    dynamic_score,
)
from .schemas import BudgetConfig, ETNORecord, GiantPlanetRecord, P9Candidate, SingleRunResult

logger = logging.getLogger("planet9lab.engine")

DRIFT_SERIES_FIELDS = [
    "t_years",
    "energy",
    "angular_momentum_norm",
    "energy_drift_rel",
    "angular_momentum_drift_rel",
]


class ReboundUnavailable(RuntimeError):
    pass


def rebound_available() -> bool:
    return importlib.util.find_spec("rebound") is not None


def vec_norm(vec: Any) -> float:
    return math.sqrt(float(vec.x) ** 2 + float(vec.y) ** 2 + float(vec.z) ** 2)


class ReboundEngine:
    def __init__(
        self,
        budget: BudgetConfig,
        seed: int,
        giants: list[GiantPlanetRecord],
        allow_analytical_fallback: bool = False,
    ):
        self.budget = budget
        self.seed = seed
        self.giants = giants
        self.allow_analytical_fallback = allow_analytical_fallback
        self.rebound_available = rebound_available()
        if not self.rebound_available and not allow_analytical_fallback:
            raise ReboundUnavailable(
                "REBOUND real is not installed. Install rebound or rerun with --allow-analytical-fallback; "
                "fallback runs are marked INVALID and are not physical screening."
            )

    @property
    def rebound_version(self) -> str:
        if not self.rebound_available:
            return "unavailable"
        import rebound

        return getattr(rebound, "__version__", "unknown")

    def run_control_pair(
        self,
        etnos: list[ETNORecord],
        candidate: P9Candidate,
        weights: dict,
        checkpoint_dir: str | Path | None = None,
    ) -> dict:
        without = self.run_branch(etnos, candidate, include_p9=False, checkpoint_dir=checkpoint_dir)
        with_p9 = self.run_branch(etnos, candidate, include_p9=True, checkpoint_dir=checkpoint_dir)
        with_score = dynamic_score(with_p9["metrics"], weights)
        without_score = dynamic_score(without["metrics"], weights)
        delta = round(with_score - without_score, 6)
        return {
            "candidate_id": candidate.candidate_id,
            "with_p9": with_p9,
            "without_p9": without,
            "control_type": "same_catalog_with_and_without_p9",
            "comparison": {
                "dynamic_score_with_p9": with_score,
                "dynamic_score_without_p9": without_score,
                "delta_dynamic_score": delta,
            },
            "delta_dynamic_score": delta,
        }

    def run_branch(
        self,
        etnos: list[ETNORecord],
        candidate: P9Candidate,
        include_p9: bool,
        checkpoint_dir: str | Path | None = None,
    ) -> dict:
        if not self.rebound_available:
            return self._run_analytical_invalid(etnos, candidate, include_p9)
        if self.budget.checkpoint_interval_years is not None and checkpoint_dir is not None:
            return self.run_branch_checkpointed(etnos, candidate, include_p9, checkpoint_dir)
        return self._run_rebound(etnos, candidate, include_p9)

    def _configure_sim(self, etnos: list[ETNORecord], candidate: P9Candidate, include_p9: bool):
        import rebound

        sim = rebound.Simulation()
        sim.units = ("yr", "AU", "Msun")
        sim.G = 4 * math.pi**2
        sim.add(m=1.0)
        for giant in self.giants:
            sim.add(
                m=giant.mass_solar,
                a=giant.a_au,
                e=giant.e,
                inc=giant.i_deg * DEG_TO_RAD,
                omega=giant.omega_deg * DEG_TO_RAD,
                Omega=giant.Omega_deg * DEG_TO_RAD,
                M=giant.mean_anomaly_deg * DEG_TO_RAD,
            )
        if include_p9:
            sim.add(
                m=earth_mass_to_solar_mass(candidate.mass_earth),
                a=candidate.a_au,
                e=candidate.e,
                inc=candidate.i_deg * DEG_TO_RAD,
                omega=candidate.omega_deg * DEG_TO_RAD,
                Omega=candidate.Omega_deg * DEG_TO_RAD,
                M=candidate.mean_anomaly_deg * DEG_TO_RAD,
            )
        for etno in etnos:
            sim.add(
                m=0.0,
                a=etno.a_au,
                e=etno.e,
                inc=etno.i_deg * DEG_TO_RAD,
                omega=etno.omega_deg * DEG_TO_RAD,
                Omega=etno.Omega_deg * DEG_TO_RAD,
                M=etno.mean_anomaly_deg * DEG_TO_RAD,
            )
        sim.move_to_com()
        sim.integrator = self.budget.integrator
        if self.budget.integrator == "whfast":
            sim.dt = self.budget.timestep_years
        return sim

    def _extract_final_orbits(
        self,
        sim: Any,
        etnos: list[ETNORecord],
        etno_start_index: int,
        failures: list[str],
    ) -> tuple[list[dict], list[str]]:
        final_orbits: list[dict] = []
        lost_etnos: list[str] = []
        for offset, etno in enumerate(etnos):
            particle = sim.particles[etno_start_index + offset]
            values = [particle.x, particle.y, particle.z, particle.vx, particle.vy, particle.vz]
            if not all(math.isfinite(float(value)) for value in values):
                failures.append(f"{etno.name}:nan_or_inf_state")
                lost_etnos.append(etno.name)
                continue
            try:
                orbit = particle.orbit(primary=sim.particles[0])
                a = float(orbit.a)
                e = float(orbit.e)
                if (not math.isfinite(a)) or (not math.isfinite(e)) or e >= 1 or abs(a) > 5000:
                    lost_etnos.append(etno.name)
                    failures.append(f"{etno.name}:lost_or_hyperbolic")
                    continue
                final_orbits.append(
                    {
                        "name": etno.name,
                        "a_au": a,
                        "e": e,
                        "i_deg": normalize_degrees(float(orbit.inc) * RAD_TO_DEG),
                        "omega_deg": normalize_degrees(float(orbit.omega) * RAD_TO_DEG),
                        "Omega_deg": normalize_degrees(float(orbit.Omega) * RAD_TO_DEG),
                        "mean_anomaly_deg": normalize_degrees(float(orbit.M) * RAD_TO_DEG),
                    }
                )
            except Exception as exc:
                logger.warning("orbit extraction failed for %s: %s", etno.name, exc, exc_info=True)
                failures.append(f"{etno.name}:orbit_exception:{type(exc).__name__}")
                lost_etnos.append(etno.name)
        return final_orbits, lost_etnos

    def _build_result(
        self,
        candidate: P9Candidate,
        include_p9: bool,
        final_orbits: list[dict],
        lost_etnos: list[str],
        failures: list[str],
        energy_drift_rel: float | None,
        angular_drift_rel: float | None,
        angular_available: bool,
        etnos: list[ETNORecord],
        delta_pomega_stability_result: dict | None = None,
    ) -> dict:
        survival_rate = (len(etnos) - len(set(lost_etnos))) / len(etnos) if etnos else 0.0
        metrics = compute_branch_metrics(
            final_orbits,
            candidate.model_dump() if include_p9 else None,
            survival_rate,
            energy_drift_rel,
            angular_drift_rel,
            failures,
        )
        stable_fraction = None
        series_points = 0
        if delta_pomega_stability_result is not None:
            stable_fraction = delta_pomega_stability_result["delta_pomega_stable_fraction"]
            series_points = max(
                (len(series) for series in delta_pomega_stability_result.get("_raw_series", {}).values()),
                default=0,
            )
        result = SingleRunResult(
            candidate_id=candidate.candidate_id,
            branch="with_p9" if include_p9 else "without_p9",
            operational_status="completed" if not failures else "failed",
            survival_rate=survival_rate,
            energy_drift_rel=energy_drift_rel,
            angular_momentum_drift_rel=angular_drift_rel,
            angular_momentum_available=angular_available,
            numerical_health_score=metrics["numerical_health_score"],
            apsidal_clustering_R=metrics["apsidal_clustering_R"],
            anti_alignment_score=metrics["anti_alignment_score"],
            stability_score=metrics["stability_score"],
            lost_etnos=sorted(set(lost_etnos)),
            numerical_failures=failures,
            rebound_used=True,
            delta_pomega_stable_fraction=stable_fraction,
            delta_pomega_series_points=series_points,
        )
        return {
            "result": result.model_dump(),
            "metrics": metrics,
            "final_orbits": final_orbits,
            "delta_pomega_stability": delta_pomega_stability_result,
            "health": {
                "rebound_used": True,
                "rebound_version": self.rebound_version,
                "integrator": self.budget.integrator,
                "energy_drift_rel": energy_drift_rel,
                "angular_momentum_drift_rel": angular_drift_rel,
                "angular_momentum_available": angular_available,
                "survival_rate": survival_rate,
                "numerical_failures": failures,
                "lost_etnos": sorted(set(lost_etnos)),
            },
        }

    def _run_rebound(
        self,
        etnos: list[ETNORecord],
        candidate: P9Candidate,
        include_p9: bool,
    ) -> dict:
        failures: list[str] = []
        sim = self._configure_sim(etnos, candidate, include_p9)
        etno_start_index = 1 + len(self.giants) + (1 if include_p9 else 0)
        energy_initial = sim.energy()
        angular_initial = sim.angular_momentum()
        angular_initial_norm = vec_norm(angular_initial)
        try:
            sim.integrate(self.budget.integration_years)
        except Exception as exc:
            logger.warning("integration failed: %s", exc, exc_info=True)
            failures.append(f"integration_exception:{type(exc).__name__}")
        energy_final = sim.energy()
        angular_final = sim.angular_momentum()
        energy_drift_rel = None
        if math.isfinite(energy_initial) and abs(energy_initial) > 0:
            energy_drift_rel = abs((energy_final - energy_initial) / energy_initial)
        angular_available = math.isfinite(angular_initial_norm) and angular_initial_norm > 0
        angular_drift_rel = None
        if angular_available:
            angular_drift_rel = abs((vec_norm(angular_final) - angular_initial_norm) / angular_initial_norm)
        final_orbits, lost_etnos = self._extract_final_orbits(sim, etnos, etno_start_index, failures)
        return self._build_result(
            candidate,
            include_p9,
            final_orbits,
            lost_etnos,
            failures,
            energy_drift_rel,
            angular_drift_rel,
            angular_available,
            etnos,
        )

    def run_branch_checkpointed(
        self,
        etnos: list[ETNORecord],
        candidate: P9Candidate,
        include_p9: bool,
        checkpoint_dir: str | Path,
    ) -> dict:
        """Gyr-scale integration with periodic checkpoints to disk.

        Every `budget.checkpoint_interval_years`, this: (1) appends a row with the
        current energy/angular-momentum drift to a CSV series (durable, streamed,
        never held only in memory), (2) appends a row per ETNO with its
        instantaneous Delta_pomega relative to the candidate (or omits this if
        include_p9=False, since there is no perihelion to compare to), and (3)
        appends a REBOUND SimulationArchive snapshot of the full N-body state.

        If `checkpoint_dir` already contains a snapshot for this candidate/branch,
        integration resumes from the last saved snapshot instead of restarting
        from t=0 - this is what makes multi-hour/multi-day integrations on modest
        hardware survivable across interruptions (crash, reboot, time limit).
        """
        if self.budget.checkpoint_interval_years is None:
            raise ValueError("budget.checkpoint_interval_years must be set to use checkpointed integration")
        import rebound

        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        branch = "with_p9" if include_p9 else "without_p9"
        base = f"{candidate.candidate_id}_{branch}"
        archive_path = checkpoint_dir / f"{base}.bin"
        drift_series_path = checkpoint_dir / f"{base}_drift_series.csv"
        pomega_series_path = checkpoint_dir / f"{base}_delta_pomega_series.csv"

        etno_start_index = 1 + len(self.giants) + (1 if include_p9 else 0)
        failures: list[str] = []
        resumed = archive_path.exists()

        if resumed:
            sim = rebound.Simulation(str(archive_path))
            drift_rows = read_csv_dicts(drift_series_path)
            energy_initial = float(drift_rows[0]["energy"])
            angular_initial_norm = float(drift_rows[0]["angular_momentum_norm"])
        else:
            sim = self._configure_sim(etnos, candidate, include_p9)
            energy_initial = sim.energy()
            angular_initial_norm = vec_norm(sim.angular_momentum())
            append_csv_row(
                drift_series_path,
                {
                    "t_years": 0.0,
                    "energy": energy_initial,
                    "angular_momentum_norm": angular_initial_norm,
                    "energy_drift_rel": 0.0,
                    "angular_momentum_drift_rel": 0.0,
                },
                DRIFT_SERIES_FIELDS,
            )
            sim.save_to_file(str(archive_path))

        angular_available = math.isfinite(angular_initial_norm) and angular_initial_norm > 0
        target = self.budget.integration_years
        interval = self.budget.checkpoint_interval_years
        energy_drift_rel = None
        angular_drift_rel = None

        while sim.t < target - 1e-9:
            t_next = min(sim.t + interval, target)
            try:
                sim.integrate(t_next, exact_finish_time=0)
            except Exception as exc:
                logger.warning("checkpointed integration failed: %s", exc, exc_info=True)
                failures.append(f"integration_exception:{type(exc).__name__}")
                break
            energy = sim.energy()
            angular_norm = vec_norm(sim.angular_momentum())
            energy_drift_rel = (
                abs((energy - energy_initial) / energy_initial)
                if math.isfinite(energy_initial) and abs(energy_initial) > 0
                else None
            )
            angular_drift_rel = (
                abs((angular_norm - angular_initial_norm) / angular_initial_norm) if angular_available else None
            )
            append_csv_row(
                drift_series_path,
                {
                    "t_years": sim.t,
                    "energy": energy,
                    "angular_momentum_norm": angular_norm,
                    "energy_drift_rel": energy_drift_rel,
                    "angular_momentum_drift_rel": angular_drift_rel,
                },
                DRIFT_SERIES_FIELDS,
            )
            if include_p9:
                instant_orbits, _ = self._extract_final_orbits(sim, etnos, etno_start_index, [])
                p9_particle = sim.particles[1 + len(self.giants)]
                p9_orbit = p9_particle.orbit(primary=sim.particles[0])
                p9_dict = {
                    "omega_deg": normalize_degrees(float(p9_orbit.omega) * RAD_TO_DEG),
                    "Omega_deg": normalize_degrees(float(p9_orbit.Omega) * RAD_TO_DEG),
                }
                instant = delta_pomega_instant(instant_orbits, p9_dict)
                if instant:
                    fieldnames = ["t_years"] + sorted(instant.keys())
                    row = {"t_years": sim.t, **instant}
                    append_csv_row(pomega_series_path, row, fieldnames)
            sim.save_to_file(str(archive_path))

        final_orbits, lost_etnos = self._extract_final_orbits(sim, etnos, etno_start_index, failures)

        delta_pomega_result = None
        if include_p9 and pomega_series_path.exists():
            series_rows = read_csv_dicts(pomega_series_path)
            series_by_etno: dict[str, list[float]] = {}
            for row in series_rows:
                for key, value in row.items():
                    if key == "t_years" or value == "":
                        continue
                    series_by_etno.setdefault(key, []).append(float(value))
            delta_pomega_result = delta_pomega_stability(series_by_etno)
            delta_pomega_result["_raw_series"] = series_by_etno

        return self._build_result(
            candidate,
            include_p9,
            final_orbits,
            lost_etnos,
            failures,
            energy_drift_rel,
            angular_drift_rel,
            angular_available,
            etnos,
            delta_pomega_stability_result=delta_pomega_result,
        )

    def _run_analytical_invalid(
        self,
        etnos: list[ETNORecord],
        candidate: P9Candidate,
        include_p9: bool,
    ) -> dict:
        failures = ["rebound_not_available"]
        final_orbits = [
            {
                "name": etno.name,
                "a_au": etno.a_au,
                "e": etno.e,
                "i_deg": etno.i_deg,
                "omega_deg": etno.omega_deg,
                "Omega_deg": etno.Omega_deg,
                "mean_anomaly_deg": etno.mean_anomaly_deg,
            }
            for etno in etnos
        ]
        metrics = compute_branch_metrics(
            final_orbits,
            candidate.model_dump() if include_p9 else None,
            1.0,
            None,
            None,
            failures,
        )
        result = SingleRunResult(
            candidate_id=candidate.candidate_id,
            branch="with_p9" if include_p9 else "without_p9",
            operational_status="invalid",
            survival_rate=1.0,
            energy_drift_rel=None,
            angular_momentum_drift_rel=None,
            angular_momentum_available=False,
            numerical_health_score=0.0,
            apsidal_clustering_R=metrics["apsidal_clustering_R"],
            anti_alignment_score=metrics["anti_alignment_score"],
            stability_score=metrics["stability_score"],
            lost_etnos=[],
            numerical_failures=failures,
            rebound_used=False,
        )
        return {
            "result": result.model_dump(),
            "metrics": metrics,
            "final_orbits": final_orbits,
            "health": {
                "rebound_used": False,
                "rebound_version": "unavailable",
                "integrator": "analytical_fallback_invalid",
                "energy_drift_rel": None,
                "angular_momentum_drift_rel": None,
                "angular_momentum_available": False,
                "survival_rate": 1.0,
                "numerical_failures": failures,
                "lost_etnos": [],
            },
        }

