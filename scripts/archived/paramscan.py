"""ARCHIVED / DISCONTINUED.

This module was superseded by planet9lab/montecarlo.py (the implementation
actually wired to the CLI as `montecarlo-scan`). It is kept for reference
only, is not imported anywhere, and must not be re-introduced into the
package. Archived on 2026-08-11 after the post-audit correction session
(simulador_v2_doctor_fix); see docs/historico/CHANGELOG_V2.md.
"""

from __future__ import annotations

# Original module docstring (kept verbatim for reference; no longer the
# module docstring, since the ARCHIVED note above takes that role).
"""Statistical sampling of the P9 parameter space [M9, a9, e9, i9] (item 2 of
the V1->V2 plan), replacing prose-only claims about "reduction funnel" volume
percentages with numbers actually computed from sampled points.

Design decision, documented (not hidden): running full Gyr-scale N-body
integration on 1e4-1e5 sampled points is not computationally feasible on
commodity hardware (see scripts/benchmark_integration_cost.py - one candidate
control pair alone can take hours). So this funnel applies CHEAP, analytic/
proxy filters first to do the actual volume reduction, and only the small
surviving set should go on to full N-body validation via the `screen` command
and configs/budgets/secular.yaml. This mirrors how real screening pipelines
in this literature are built: cheap necessary conditions first, expensive
confirmation last. Two of the four filters described in the article
(secular Hamiltonian resonance criterion, IR/optical detectability limits)
are NOT implemented here - see NOT_IMPLEMENTED_FILTERS below - and are
marked explicitly as `not_implemented` in every output, per the plan's own
instruction, rather than being silently skipped or faked with an invented
formula/albedo/density assumption not otherwise justified anywhere in this
repository.
"""

from collections.abc import Iterable

from .metrics import anti_alignment_score

FILTER_ORDER = [
    "geometric_bounds",
    "apsidal_alignment_proxy",
    "secular_hamiltonian",
    "detectability_ir_optical",
]

# These two require either a derivation not yet done in this repository
# (secular Hamiltonian resonance criterion following e.g. Batygin & Morbidelli
# 2017) or new physical assumptions not documented anywhere in
# docs/MODELO_FISICO.md (an assumed albedo and bulk density to turn mass into
# a physical radius for reflected-light/thermal flux). Inventing either here
# would be exactly the kind of "invented result" this project's own rules
# forbid. They stay `not_implemented` until derived/documented for real.
NOT_IMPLEMENTED_FILTERS = {"secular_hamiltonian", "detectability_ir_optical"}

SCAN_FIELDS = [
    "point_id",
    "mass_earth",
    "a_au",
    "e",
    "i_deg",
    "omega_deg",
    "Omega_deg",
    "pass_geometric_bounds",
    "pass_apsidal_alignment_proxy",
    "pass_secular_hamiltonian",
    "pass_detectability_ir_optical",
    "survives_all_implemented_filters",
]


def halton_sequence(n: int, dim: int) -> list[list[float]]:
    """Pure-Python quasi-Monte Carlo (Halton, prime bases) low-discrepancy
    sequence. Used instead of plain `random.uniform` so the parameter space is
    covered more evenly for a given N - and instead of scipy's Sobol sampler,
    which is not installable in this offline environment (see AUDITORIA /
    LIMITACOES for why). If scipy becomes available, swapping in
    `scipy.stats.qmc.Sobol` is a drop-in replacement for this function.
    """
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    if dim > len(primes):
        raise ValueError(f"halton_sequence supports up to {len(primes)} dimensions, got {dim}")
    points = []
    for i in range(1, n + 1):
        point = []
        for d in range(dim):
            base = primes[d]
            f = 1.0
            r = 0.0
            k = i
            while k > 0:
                f = f / base
                r = r + f * (k % base)
                k = k // base
            point.append(r)
        points.append(point)
    return points


def sample_parameter_space(
    n: int,
    bounds: dict,
    method: str = "halton",
    seed: int = 0,
) -> list[dict]:
    """Sample n points over [mass_earth, a_au, e, i_deg], with omega/Omega
    drawn separately (uniform is fine for these, they are not part of the
    funnel's target 4D space per the plan's own [M9,a9,e9,i9] wording)."""
    dims = ["mass_earth_range", "a_au_range", "e_range", "i_deg_range"]
    for key in dims:
        if key not in bounds:
            raise ValueError(f"region bounds missing required key: {key}")

    if method == "halton":
        unit_points = halton_sequence(n, 4)
    elif method == "uniform":
        import random

        rng = random.Random(seed)
        unit_points = [[rng.random() for _ in range(4)] for _ in range(n)]
    else:
        raise ValueError(f"unknown sampling method: {method}")

    import random

    angle_rng = random.Random(seed + 1)
    points = []
    for idx, unit_point in enumerate(unit_points):
        scaled = []
        for value, key in zip(unit_point, dims):
            lo, hi = bounds[key]
            scaled.append(lo + value * (hi - lo))
        mass_earth, a_au, e, i_deg = scaled
        points.append(
            {
                "point_id": idx,
                "mass_earth": mass_earth,
                "a_au": a_au,
                "e": e,
                "i_deg": i_deg,
                "omega_deg": angle_rng.uniform(*bounds.get("omega_deg_range", [0.0, 360.0])),
                "Omega_deg": angle_rng.uniform(*bounds.get("Omega_deg_range", [0.0, 360.0])),
            }
        )
    return points


def filter_geometric_bounds(point: dict, giants: list, max_a_au: float = 5000.0) -> bool:
    """Cheap necessary condition, no integration required: the candidate's
    perihelion must clear the outermost giant planet's aphelion (otherwise it
    is orbit-crossing with a known giant and could not plausibly be a
    long-term stable, undiscovered distant planet), and its semi-major axis
    must be finite/bounded (guards against degenerate sampled points)."""
    if not giants:
        raise ValueError("filter_geometric_bounds requires at least one giant planet record")
    outermost_aphelion = max(g.a_au * (1.0 + g.e) for g in giants)
    perihelion = point["a_au"] * (1.0 - point["e"])
    return bool(perihelion > outermost_aphelion and 0 < point["a_au"] <= max_a_au)


def filter_apsidal_alignment_proxy(
    point: dict,
    etno_pomega_deg: Iterable[float],
    threshold: float = 0.3,
) -> bool:
    """Cheap geometric proxy for apsidal anti-alignment: does NOT integrate
    anything. It just checks whether the candidate's current longitude of
    perihelion is roughly anti-aligned with the CURRENT clustering of the
    observed ETNO catalog's longitudes of perihelion (reusing the same
    anti_alignment_score used elsewhere in this codebase for consistency).
    This is a necessary-condition prefilter, not proof of long-term secular
    stability of that alignment - that still requires the real N-body
    integration in `screen` (see docs/LIMITACOES.md)."""
    pomega = (point["omega_deg"] + point["Omega_deg"]) % 360.0
    score = anti_alignment_score(list(etno_pomega_deg), pomega)
    return bool(score >= threshold)


def run_reduction_funnel(
    points: list[dict],
    giants: list,
    etno_pomega_deg: Iterable[float],
) -> list[dict]:
    """Apply filters sequentially (each layer only evaluated on survivors of
    the previous one, matching how a real reduction funnel narrows volume),
    and record a boolean per filter per point so every percentage in the
    output is directly auditable from results/parameter_space_scan.csv."""
    etno_pomega_deg = list(etno_pomega_deg)
    rows = []
    for point in points:
        row = dict(point)
        alive = True
        pass_geo = filter_geometric_bounds(point, giants)
        row["pass_geometric_bounds"] = pass_geo
        alive = alive and pass_geo

        if alive:
            pass_apsidal = filter_apsidal_alignment_proxy(point, etno_pomega_deg)
        else:
            pass_apsidal = None  # not evaluated: point already excluded upstream
        row["pass_apsidal_alignment_proxy"] = pass_apsidal
        alive = alive and bool(pass_apsidal)

        row["pass_secular_hamiltonian"] = "not_implemented"
        row["pass_detectability_ir_optical"] = "not_implemented"
        row["survives_all_implemented_filters"] = alive
        rows.append(row)
    return rows


def build_reduction_funnel_summary(rows: list[dict]) -> dict:
    """Compute volume-remaining percentages directly from the boolean columns
    in `rows` - never hardcoded. Layers marked not_implemented report their
    survivor counts as null with an explicit note, instead of a fabricated
    percentage."""
    total = len(rows)
    layers = []
    remaining_mask = [True] * total

    def apply_layer(name: str, column: str, implemented: bool):
        nonlocal remaining_mask
        if not implemented:
            layers.append(
                {
                    "filter": name,
                    "implemented": False,
                    "survivors": None,
                    "percent_of_total_remaining": None,
                    "percent_of_previous_layer": None,
                    "note": "not_implemented: see NOT_IMPLEMENTED_FILTERS docstring in paramscan.py",
                }
            )
            return
        previous_count = sum(remaining_mask)
        new_mask = [
            remaining_mask[i] and bool(rows[i][column]) if remaining_mask[i] else False for i in range(total)
        ]
        survivors = sum(new_mask)
        layers.append(
            {
                "filter": name,
                "implemented": True,
                "survivors": survivors,
                "percent_of_total_remaining": round(100.0 * survivors / total, 4) if total else None,
                "percent_of_previous_layer": round(100.0 * survivors / previous_count, 4)
                if previous_count
                else None,
            }
        )
        remaining_mask = new_mask

    apply_layer("geometric_bounds", "pass_geometric_bounds", True)
    apply_layer("apsidal_alignment_proxy", "pass_apsidal_alignment_proxy", True)
    apply_layer("secular_hamiltonian", "pass_secular_hamiltonian", False)
    apply_layer("detectability_ir_optical", "pass_detectability_ir_optical", False)

    return {
        "total_sampled_points": total,
        "layers": layers,
        "final_survivors_among_implemented_filters": sum(remaining_mask),
        "note": (
            "Only geometric_bounds and apsidal_alignment_proxy are implemented "
            "and reduce volume here; secular_hamiltonian and "
            "detectability_ir_optical are not_implemented and do not remove "
            "any points in this summary. Any 'volume restante' claim in the "
            "article for those two layers is NOT supported by this scan and "
            "must not be presented as computed."
        ),
    }
