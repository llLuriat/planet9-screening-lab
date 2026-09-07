"""Side-by-side circular-statistics report over an existing run.

READ-ONLY: this module never writes to the run directory and never changes
the classification of any candidate. It only derives, for each candidate of
an existing run, the Rayleigh uniformity p-value from the already-stored
`apsidal_clustering_R` (Z = n * R^2, n from the run's data manifest) and
compares it against the current ad-hoc classification. It also reports the
Rayleigh and Kuiper p-values of the observed ETNO catalog used by that run,
and a sample-size power analysis.

If the comparison ever suggests that a circular-statistics test should become
the default screening criterion, that is a Categoria B decision: stop and
ask for explicit authorization before changing any default behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

from .circular_tests import (
    kuiper_v,
    rayleigh_from_resultant_length,
    rayleigh_z,
    required_n_for_rayleigh_power,
)
from .loaders import load_etnos

DEFAULT_POWER_RHOS = (0.3, 0.5, 0.7)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def circular_stats_report(run_dir: str | Path, alpha: float = 0.05) -> dict:
    run = Path(run_dir)
    cache = _read_json(run / "candidates_results_cache.json")
    manifest = _read_json(run / "data_manifest.json")

    included_names = list(manifest.get("included_etnos", []))
    n = len(included_names)

    per_candidate = []
    current_interest = 0
    for candidate_id in sorted(cache):
        entry = cache[candidate_id]
        row = entry["metrics_row"]
        with_p9_r = row.get("apsidal_clustering_R_with_p9")
        without_p9_r = row.get("apsidal_clustering_R_without_p9")
        with_p9 = (
            rayleigh_from_resultant_length(float(with_p9_r), n) if with_p9_r is not None else None
        )
        without_p9 = (
            rayleigh_from_resultant_length(float(without_p9_r), n)
            if without_p9_r is not None
            else None
        )
        classification = row.get("scientific_status")
        if classification == "candidate_of_interest":
            current_interest += 1
        per_candidate.append(
            {
                "candidate_id": candidate_id,
                "scientific_status": classification,
                "classification_reason": row.get("classification_reason"),
                "apsidal_clustering_R_with_p9": with_p9_r,
                "apsidal_clustering_R_without_p9": without_p9_r,
                "rayleigh_with_p9": with_p9,
                "rayleigh_without_p9": without_p9,
                "significant_by_rayleigh_with_p9": bool(
                    with_p9 is not None and with_p9["p"] <= alpha
                ),
                "significant_by_rayleigh_without_p9": bool(
                    without_p9 is not None and without_p9["p"] <= alpha
                ),
            }
        )

    catalog_input = manifest.get("input_files", {}).get("etno_catalog")
    if catalog_input:
        catalog_path = Path(catalog_input)
        if not catalog_path.exists():
            fallback = run.parent.parent / "data" / "etnos" / Path(catalog_input).name
            if fallback.exists():
                catalog_path = fallback
    else:
        catalog_path = run.parent.parent / "data" / "etnos" / "catalog.csv"
    catalog_available = catalog_path.exists()
    observed = None
    if catalog_available:
        observed_angles = [
            float(record.omega_deg + record.Omega_deg)
            for record in load_etnos(catalog_path)
            if record.name in included_names
        ]
        observed = {
            "catalog_path": str(catalog_path),
            "catalog_etno_count": len(observed_angles),
            "manifest_etno_count": n,
            "sample_matches_manifest": len(observed_angles) == n and n > 0,
            "rayleigh": rayleigh_z(observed_angles),
            "kuiper": kuiper_v(observed_angles),
            "significant_by_rayleigh": bool(
                observed_angles and rayleigh_z(observed_angles)["p"] <= alpha
            ),
            "significant_by_kuiper": bool(
                observed_angles and kuiper_v(observed_angles)["p"] <= alpha
            ),
        }

    power = [
        required_n_for_rayleigh_power(rho, alpha, 0.80, seed=12345)
        for rho in DEFAULT_POWER_RHOS
    ]

    rayleigh_significant_count = sum(
        item["significant_by_rayleigh_with_p9"] for item in per_candidate
    )
    return {
        "run_dir": str(run),
        "etno_count_from_manifest": n,
        "alpha": alpha,
        "per_candidate": per_candidate,
        "comparison_summary": {
            "candidates_classified_candidate_of_interest": current_interest,
            "candidates_significant_by_rayleigh_with_p9": rayleigh_significant_count,
            "note": (
                "Read-only comparison. Nothing was reclassified; promoting "
                "Rayleigh/Kuiper to the default criterion would be a Categoria B "
                "decision requiring explicit authorization."
            ),
        },
        "observed_catalog": observed,
        "power_analysis": {
            "target_power": 0.80,
            "required_n_by_rho": {str(rho): entry for rho, entry in zip(DEFAULT_POWER_RHOS, power)},
            "note": (
                "Smallest n for which the estimated Rayleigh power reaches 0.80 "
                "at the given alpha (asymptotic noncentral-chi-square approximation)."
            ),
        },
    }
