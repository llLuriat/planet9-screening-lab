from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from .artifacts import (  # noqa: F401 - write_csv reserved for the Step 5c artifact writer
    ensure_dir,
    write_csv,
    write_json,
)
from .config import load_yaml
from .loaders import ETNORecord, load_etnos, selected_etnos
from .metrics import normalize_degrees
from .robustness import merge_blocker, remove_blocker
from .run import ROOT, append_event, default_paths, read_manifest


class ObservationalBiasConfig(BaseModel):
    bias_model: str = "none"
    bias_model_level: int = 0
    blocker_if_none: bool = True
    max_evidence_level_without_bias_model: str = "weak"
    limiting_magnitude_v: float = 24.5
    sky_coverage_deg2: float = 20000.0
    min_tracking_arc_years: float = 2.0
    n_synthetic: int = 5000
    h_catalog_path: str = Field(
        default="data/etnos/h_values.csv",
        description="Path to CSV of real catalog H values (SBDB). Used as prior for synthetic population brightness when bias_model != 'none'.",
    )
    albedo_default: float = Field(
        default=0.10,
        description="Assumed geometric albedo for diameter estimation when no per-measurement value is available. Source: Sheppard & Trujillo (2016), AJ 152:221.",
    )

    @field_validator("albedo_default")
    @classmethod
    def _albedo_in_range(cls, value: float) -> float:
        if not (0.01 <= value <= 0.60):
            raise ValueError(f"albedo_default {value} outside plausible TNO range [0.01, 0.60]")
        return value


def load_bias_config(path: str | Path) -> ObservationalBiasConfig:
    """Load configs/science/observational_bias.yaml into a validated config.

    Missing optional keys fall back to the field defaults above, documented
    inline rather than duplicated in the YAML, so existing YAML files with
    only the original 4 keys keep working unchanged.
    """
    raw = load_yaml(path)
    return ObservationalBiasConfig.model_validate(raw)


def load_h_catalog(path: str | Path) -> list[tuple[str, float]]:
    """Load the real catalog H values from a CSV.

    Returns a list of (fullname, h_value) tuples. The CSV must have at least
    ``object`` and ``h`` columns; ``#``-prefixed comment lines and a header
    row are expected (see ``data/etnos/h_values.csv``).

    Used as the empirical prior for the synthetic population's brightness:
    each synthetic object draws its H from this list (with replacement), so
    the synthetic population replicates the real sample's magnitude
    distribution while its angles stay uniform-random.
    """
    h_values: list[tuple[str, float]] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(
            (line for line in handle if not line.startswith("#")),
        )
        for row in reader:
            try:
                h_values.append((row["object"], float(row["h"])))
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"each row in {path} must have non-empty 'object' and numeric 'h' columns: {row!r}"
                ) from exc
    if not h_values:
        raise ValueError(f"{path} contains no H values (after header + comments)")
    return h_values


def _depth_prob_from_h(h_value: float, limiting_magnitude_v: float) -> float:
    """Per-object depth probability derived from absolute magnitude H.

    Stand-in for a full distance + phase-function + albedo model: without a
    heliocentric distance per synthetic object (angle-only population), H is
    the only brightness handle available. The detection probability is the
    FIXED base probability (from the survey limiting magnitude) scaled by a
    factor that decreases as the object gets fainter than a reference H.

    Reference H = 6.5 (catalog median): objects at the median see the base
    probability unchanged; fainter objects are penalized; brighter objects
    are NOT boosted (conservative — no detection advantage beyond the
    survey's limiting magnitude).

    TODO: replace with apparent-magnitude computation V = H + 5 log10(r * Delta)
    once the synthetic population carries a heliocentric distance (requires
    a distance/size/albedo model — see LIMITACOES.md). Until then this is a
    documented linear stand-in, not a calibrated detection efficiency.
    """
    base = 1.0 - 0.15 * (24.5 - limiting_magnitude_v)
    base = min(1.0, max(0.0, base))
    # penalty: each magnitude fainter than reference H reduces probability by 0.12
    penalty = 0.12 * max(0.0, h_value - 6.5)
    return min(1.0, max(0.0, base - penalty))
    """Uniform-in-angle synthetic ETNO population (Napier et al. 2021 design):
    omega, Omega, mean_anomaly independently uniform in [0, 360) degrees.
    Does NOT touch a_au/e/i_deg - this module tests angular selection bias
    only, not orbit-fitting bias. No REBOUND integration involved.
    """
def generate_synthetic_population(
    rng: random.Random,
    n: int,
    h_prior_values: list[float] | None = None,
) -> list[dict]:
    """Uniform-in-angle synthetic ETNO population (Napier et al. 2021 design):
    omega, Omega, mean_anomaly independently uniform in [0, 360) degrees.
    Does NOT touch a_au/e/i_deg - this module tests angular selection bias
    only, not orbit-fitting bias. No REBOUND integration involved.

    When `h_prior_values` is provided (list of real catalog H values, e.g. from
    ``data/etnos/h_values.csv``), each synthetic object draws an H value with
    replacement from that list — so the synthetic population replicates the real
    sample's brightness distribution while its angles stay uniform-random.
    When None, the population has no H column and the selection function falls
    back to the angle-only approximation.
    """
    population: list[dict] = []
    for index in range(n):
        row = {
            "name": f"synthetic_{index:05d}",
            "omega_deg": rng.uniform(0, 360),
            "Omega_deg": rng.uniform(0, 360),
            "mean_anomaly_deg": rng.uniform(0, 360),
        }
        if h_prior_values:
            row["h_value"] = h_prior_values[rng.randrange(len(h_prior_values))]
        population.append(row)
    return population


def apply_selection_function(
    population: list[dict],
    rng: random.Random,
    limiting_magnitude_v: float,
    sky_coverage_deg2: float,
    min_tracking_arc_years: float,
) -> list[dict]:
    """Probabilistic detection-selection model (Napier et al. 2021 design,
    arXiv:2102.05601, Section 3): each synthetic object survives with a
    detection probability that is the PRODUCT of three independent factors.
    This is a simplified, documented approximation - not a full survey
    pointing/cadence simulator - suitable for testing whether the angular
    clustering seen in the real catalog could plausibly be a pure detection
    artifact, not for claiming a precise completeness fraction.

    Factor 1 - limiting magnitude (depth): when the synthetic population
    carries a per-object ``h_value`` (drawn from the real catalog's H prior),
    the per-object depth probability is computed by ``_depth_prob_from_h``,
    which applies a magnitude penalty fainter than the catalog median H=6.5.
    When ``h_value`` is absent (angle-only mode), this factor is approximated
    as a FIXED base detection probability derived from limiting_magnitude_v
    relative to a reference survey depth of V=24.5 (representative of
    DES/OSSOS-class surveys).

    Factor 2 - sky coverage: an object is only detectable if its ARGUMENT
    OF PERIHELION places its (simplified, ecliptic-plane) discovery position
    within the surveyed footprint. Approximated here as the fraction
    sky_coverage_deg2 / 41253 (total sky in deg2) applied as a survival
    probability per object, uniform over omega_deg (no real footprint
    geometry - documented simplification).

    Factor 3 - minimum tracking arc: shorter-period, faster-moving
    configurations are systematically easier to lose before a multi-year
    arc is secured. Approximated via a probability that decreases as
    min_tracking_arc_years increases (harder requirement, more discoveries
    lost to insufficient follow-up), independent of the individual
    object's angles (this factor does not depend on orbital elements not
    present in the angle-only population; it acts as a uniform survival
    penalty here - documented simplification).

    Returns the subset of `population` that "survives" all three factors,
    each evaluated independently as a Bernoulli draw from `rng`.
    """
    has_h = population and "h_value" in population[0]
    fixed_depth = min(1.0, max(0.0, 1.0 - 0.15 * (24.5 - limiting_magnitude_v)))
    sky_fraction = min(1.0, max(0.0, sky_coverage_deg2 / 41253.0))
    arc_survival_prob = min(1.0, max(0.0, 1.0 / (1.0 + 0.2 * min_tracking_arc_years)))

    survivors: list[dict] = []
    for row in population:
        if has_h:
            depth_prob = _depth_prob_from_h(row["h_value"], limiting_magnitude_v)
        else:
            depth_prob = fixed_depth
        if rng.random() > depth_prob:
            continue
        if rng.random() > sky_fraction:
            continue
        if rng.random() > arc_survival_prob:
            continue
        survivors.append(row)
    return survivors


def varpi_deg(row: dict) -> float:
    return normalize_degrees(row["omega_deg"] + row["Omega_deg"])


def real_catalog_varpis(etnos: list[ETNORecord]) -> list[float]:
    return [normalize_degrees(etno.omega_deg + etno.Omega_deg) for etno in etnos]


def selection_bias_check(
    real_etnos: list[ETNORecord],
    config: ObservationalBiasConfig,
    seed: int,
) -> dict:
    """Compare the angular distribution (varpi = omega + Omega) of the real
    16-ETNO catalog against a synthetic uniform population passed through
    the same selection function. If the surviving synthetic population is
    ALSO clustered in varpi (not uniform anymore), that is evidence the
    real catalog's clustering could be a pure selection artifact, not a
    real dynamical signal - and this must be reported plainly either way,
    per configs/science/conclusion_policy.yaml (no upgrading evidence level
    on a favorable result, no hiding an unfavorable one).

    Uses a simple circular-uniformity check (resultant vector length R,
    Rayleigh-style) on the surviving synthetic varpi values, compared
    against the real catalog's R, both computed the same way for a fair
    comparison. This module does NOT reuse the exact apsidal_clustering_R
    from metrics.py to avoid a hidden coupling to the physical screening
    pipeline; it only needs a simple, well-documented circular concentration
    statistic here from the population it built for this diagnostic.
    """
    rng = random.Random(seed)
    real_varpis = real_catalog_varpis(real_etnos)
    n_real = len(real_varpis)

    h_values: list[float] | None = None
    h_catalog_source: str | None = None
    if config.bias_model != "none":
        h_catalog = load_h_catalog(config.h_catalog_path)
        h_values = [h for _, h in h_catalog]
        h_catalog_source = config.h_catalog_path

    synthetic = generate_synthetic_population(rng, config.n_synthetic, h_prior_values=h_values)
    surviving = apply_selection_function(
        synthetic, rng, config.limiting_magnitude_v, config.sky_coverage_deg2, config.min_tracking_arc_years
    )

    def resultant_length(angles_deg: list[float]) -> float:
        if not angles_deg:
            return 0.0
        import math
        sum_cos = sum(math.cos(math.radians(a)) for a in angles_deg)
        sum_sin = sum(math.sin(math.radians(a)) for a in angles_deg)
        return math.hypot(sum_cos, sum_sin) / len(angles_deg)

    surviving_varpis = [varpi_deg(row) for row in surviving]
    real_r = resultant_length(real_varpis)
    surviving_r = resultant_length(surviving_varpis)

    h_prior_stats: dict[str, float] | None
    if h_values:
        sorted_h = sorted(h_values)
        n = len(sorted_h)
        median_h = sorted_h[n // 2] if n % 2 else 0.5 * (sorted_h[n // 2 - 1] + sorted_h[n // 2])
        h_prior_stats = {
            "h_prior_n": n,
            "h_prior_mean": round(sum(h_values) / n, 4),
            "h_prior_median": round(median_h, 4),
            "h_prior_min": min(h_values),
            "h_prior_max": max(h_values),
        }
    else:
        h_prior_stats = None

    return {
        "bias_model": config.bias_model,
        "n_real_catalog": n_real,
        "n_synthetic_generated": config.n_synthetic,
        "n_synthetic_surviving": len(surviving),
        "surviving_fraction": round(len(surviving) / config.n_synthetic, 6) if config.n_synthetic else 0.0,
        "real_catalog_resultant_length_R": round(real_r, 6),
        "surviving_synthetic_resultant_length_R": round(surviving_r, 6),
        "real_exceeds_synthetic_R": real_r > surviving_r,
        "h_prior_source": h_catalog_source,
        "h_prior_stats": h_prior_stats,
        "interpretation": (
            "O catalogo real tem concentracao angular (R) maior que a populacao "
            "sintetica sujeita ao mesmo modelo de selecao — o clustering real NAO "
            "e trivialmente explicado por vies de selecao neste modelo simplificado."
            if real_r > surviving_r
            else
            "O catalogo real NAO tem concentracao angular (R) maior que a populacao "
            "sintetica sujeita ao mesmo modelo de selecao — este modelo simplificado "
            "de vies de selecao NAO PODE descartar que o clustering observado seja um "
            "artefato de selecao, nao um sinal dinamico real. Isto e uma limitacao "
            "que deve ser reportada explicitamente, nao suavizada."
        ),
        "caveats": [
            "Modelo angle-only (omega, Omega, M): nao modela geometria de footprint real nem cadencia real do survey.",
            "H-prior from catalog (SBDB): per-object depth probability uses a linear stand-in (H penalty relative to median H=6.5), not calibrated detection efficiency.",
            "Resultado NAO deve ser citado como probabilidade de deteccao calibrada - e um teste de plausibilidade qualitativo.",
        ],
    }


def _resolve_run_etno_catalog(run_dir: Path) -> tuple[Path, list[str]]:
    """Resolve the exact ETNO catalog used by THIS run, from <run>/data_manifest.json.

    audit/run_manifest.json (what read_manifest reads) does not record the
    catalog path; the run-root data_manifest.json written by execute_run does,
    under input_files.etno_catalog. The stored value may be absolute (defaults
    resolved on the machine that created the run) or relative exactly as typed
    on the command line (e.g. --etnos data/etnos/catalog_validated.csv), so the
    resolution order mirrors circular_report.py's provenance fallback: stored
    path as-is, then project-root-relative, then the sibling data/etnos
    directory used when a runs/ tree is copied between machines. Also returns
    the run's included_etnos list so the caller can verify the sample matches.

    Deliberately raises instead of falling back to default_paths(): a silent
    default would make the check run against a DIFFERENT sample than the one
    the run screened - insufficient provenance must fail loudly (documented
    limitation), not be papered over with a default catalog.
    """
    data_manifest_path = run_dir / "data_manifest.json"
    if not data_manifest_path.exists():
        raise FileNotFoundError(
            f"{data_manifest_path} not found: this run does not record enough catalog provenance "
            "to run a selection-bias check against the exact catalog it screened."
        )
    data_manifest = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    stored = data_manifest.get("input_files", {}).get("etno_catalog")
    if not stored:
        raise FileNotFoundError(
            f"{data_manifest_path} has no input_files.etno_catalog entry: catalog provenance is "
            "insufficient for a selection-bias check (no default fallback is applied by design)."
        )
    candidates = [
        Path(stored),
        ROOT / stored,
        run_dir.parent.parent / "data" / "etnos" / Path(stored).name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate, list(data_manifest.get("included_etnos", []))
    raise FileNotFoundError(
        f"ETNO catalog recorded by this run ({stored!r}) does not exist at any known location: "
        "catalog provenance is broken for this run."
    )


def run_selection_bias_check(run_dir: str | Path, bias_config_path: str = "configs/science/observational_bias.yaml") -> Path:
    """Run selection_bias_check against the run's ETNO catalog and write
    <run>/diagnostics/selection_bias.json, then reconcile the run's
    audit/blockers.json with the outcome:

    - real_exceeds_synthetic_R is False: merges the specific
      selection_bias_not_ruled_out blocker. The older generic
      no_observational_bias_model blocker (from
      configs/science/observational_bias.yaml, blocker_if_none: true) is
      deliberately KEPT - the specific blocker already covers the same
      ground, and removal is reserved for a favorable result.
    - real_exceeds_synthetic_R is True: removes no_observational_bias_model
      from the run's blockers if present - this module IS the bias model
      that generic blocker was standing in for, and the check just ran
      successfully. Runs that never call this command keep the blocker.
    """
    run_dir = Path(run_dir)
    manifest = read_manifest(run_dir)
    config = load_bias_config(bias_config_path)
    paths = default_paths()
    etno_path, included_etnos = _resolve_run_etno_catalog(run_dir)
    etnos, _rejected = selected_etnos(load_etnos(etno_path), load_yaml(paths["etno_selection_config"]))
    if included_etnos and sorted(etno.name for etno in etnos) != sorted(included_etnos):
        raise ValueError(
            f"ETNO catalog at {etno_path} does not reproduce the sample recorded in this run's "
            f"data_manifest.json ({len(etnos)} selected vs {len(included_etnos)} included_etnos); "
            "refusing to run the selection-bias check against a different sample than the one screened."
        )
    result = {"etno_catalog_path": str(etno_path), **selection_bias_check(etnos, config, seed=manifest["seed"])}
    out_dir = ensure_dir(run_dir / "diagnostics")
    write_json(out_dir / "selection_bias.json", result)
    append_event(run_dir, "selection_bias_check_completed", real_exceeds_synthetic_R=result["real_exceeds_synthetic_R"])
    if not result["real_exceeds_synthetic_R"]:
        merge_blocker(
            run_dir,
            {
                "blocker_id": "selection_bias_not_ruled_out",
                "severity": "science_limit",
                "message": "O modelo simplificado de vies de selecao NAO conseguiu descartar que o clustering angular observado seja um artefato de selecao, nao um sinal dinamico real.",
            },
        )
    else:
        # Favorable result: this module IS the bias model that the generic
        # config blocker was standing in for, so retire it for this run.
        # On an unfavorable result it is kept on purpose - the specific
        # selection_bias_not_ruled_out blocker already covers the case.
        if remove_blocker(run_dir, "no_observational_bias_model"):
            append_event(run_dir, "no_observational_bias_model_blocker_removed")
    return out_dir / "selection_bias.json"
