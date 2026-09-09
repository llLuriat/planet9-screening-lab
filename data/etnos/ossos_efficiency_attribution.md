# OSSOS Efficiency Curve Parameters

Source file: `data/etnos/ossos_efficiency_attribution.md`

## Functional form

The detection efficiency η(m) as a function of r-band magnitude follows the
quadratic-logistic form from **Bannister et al. (2016a)**, ApJ 831:94, §2:

    η(m) = (eff_max − c·(m − 21)²) / (1 + exp((m − m₀) / σ))

- **numerator**: quadratic roll-off from a peak efficiency `eff_max` at m ≈ 21,
  with curvature `c` (how quickly efficiency drops for fainter objects).
- **denominator**: logistic transition centered at `m₀` (magnitude at ~50%
  efficiency) with width `σ` (how sharp the drop is).

## Parameter values

Default values used in `planet9lab/selection_bias.py` (`_DEFAULT_OSSOS_EFFICIENCY_PARAMS`):

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `eff_max` | 0.887741923 | Peak efficiency at m ≈ 21 |
| `c` | 2.76305359e-02 | Quadratic curvature |
| `m₀` | 24.1423416 | Magnitude at 50% efficiency |
| `σ` | 0.153656587 | Logistic transition width |

## Sources

1. **Bannister et al. 2016a**, ApJ 831:94 — "OSSOS. II. The Science Input Catalog"
   introduces the functional form and the `eff_max`, `c`, `m₀`, `σ` parameters
   for the 2013AE block. Used by the OSSOS SurveySimulator code
   (`H:\_tmp_ossos_survey\fortran\F95\effut.f95`, READ-ONLY reference).

2. **Bannister et al. 2018**, ApJS 236:18, arXiv:1805.11740 — "OSSOS. VII. A
   Comparison of the Orbital Distribution of Classical and Resonant TNOs"
   (§5.2) confirms the efficiency curve parameters and reports a survey
   footprint of 155 deg² for the 2013AE block.

3. **OSSOS SurveySimulator** (READ-ONLY reference at
   `H:\_tmp_ossos_survey\fortran\F95\SS_Input_Formats\2013AE.eff`) — the actual
   `.eff` input file used by the Fortran `effut.f95` routine. Three 2013AE
   blocks with per-block parameters:
   - block 1: eff_max=0.8877, c=2.763e-2, m0=24.142, sig=0.1537
   - block 2: eff_max=0.8956, c=2.311e-2, m0=24.005, sig=0.1571
   - block 3: eff_max=0.8658, c=2.122e-2, m0=23.881, sig=0.1555

The default values are the mean across the three blocks, used in the absence
of per-block footprint geometry.

## Scope and limitations

- Valid for r-band magnitudes ~21–25 and TNO sky-plane rates 0.50–8.00 arcsec/hour.
- Does not model the phase-function, trailing losses, or per-night weather.
- The pipeline uses this curve to evaluate **per-object detection probability**
  at the apparent magnitude V = H + 5 log10(r·Δ), where r and Δ are the
  heliocentric and geocentric distances of each synthetic object.

## OSSOS filling factor (sky-coverage acceptance probability)

The OSSOS survey simulator applies a per-block `filling_factor` as a Monte
Carlo acceptance probability — the probability that a synthetic TNO's
sky-plane position falls within the actual survey-pointing footprint
(Bannister et al. 2016a, survey simulator logic). Since our synthetic
population is **angle-only** (uniform random on the sphere, no per-object
sky-plane position to test against real footprint polygons), we apply this
as a single uniform per-object survival probability.

- **2013A-E block**: filling_factor = 0.9079
- **2013A-O block**: filling_factor = 0.9055
- **Arithmetic mean (used here)**: (0.9079 + 0.9055) / 2 = **0.9067**

These values are copied verbatim from the OSSOS SurveySimulator
`pointings.list` reference file at
`H:\_tmp_ossos_survey\fortran\F95\pointings.list` (READ-ONLY clone of the
OSSOS SurveySimulator, commit a1fcf1bfc). See §5.2 of Bannister et al.
2018, ApJS 236:18 (arXiv:1805.11740) for the footprint description (155 deg²
covered across 5 pointings of the 2013AE block).
## OSSOS 2013A footprint block geometry (point-in-polygon positional filter)

As of the footprint integration, the **real OSSOS 2013A sky-block geometry**
is available as a positional filter in `apply_selection_function`:

- Geometry source: `planet9lab/data/ossos_2013a_blocks.py` (blocks
  `2013A-E` and `2013A-O`), extracted from the OSSOS SurveySimulator
  `pointings.list` / `.eff` files (Bannister et al. 2018, ApJS 236:18,
  Fig. 1; read-only reference clone at `H:\_tmp_ossos_survey`, commit
  a1fcf1bfc146b7b72654d65d6789c59790e3cbb4).
- Filter implementation: `_sky_position_in_footprint()` in
  `planet9lab/selection_bias.py` uses `create_poly` + `point_in_polygon`
  from `planet9lab/geometry/poly_footprint.py` (faithful port of the
  OSSOS SurveySimulator Fortran `poly_lib.f95`), reconstructing each
  block's polygon from `center_ra_deg` / `center_dec_deg` /
  `corner_offsets_deg` and testing the synthetic object's `(ra_deg,
  dec_deg)` in degrees (converted to radians at the call site, per the
  radians convention documented in `poly_footprint.py`).

### Activation (explicit opt-in)

The filter is **opt-in** via `use_ossos_footprint: true` in
`configs/science/observational_bias.yaml` (default `false`). It is OFF by
default on purpose: the synthetic population's sky positions are
uniform-random RA/Dec proxies — not a full orbital→sky projection — and
the OSSOS 2013A footprint covers only ~0.07% of the celestial sphere, so
auto-enabling it would collapse the surviving synthetic sample to a
handful of objects and make the R comparison degenerate. See
`docs/LIMITACOES.md` for the full limitation statement.

### Behavior when enabled

1. Objects outside every OSSOS block polygon are rejected outright
   (real point-in-polygon test).
2. Survivors then pass the per-block Monte Carlo acceptance
   `ossos_filling_factor` (0.9067 mean of 2013A-E/2013A-O) applied as a
   per-object survival probability, matching the SurveySimulator logic.
3. `selection_bias_check` reports `ossos_footprint_mode`:
   `"real_footprint_polygons"` when enabled, `"uniform_filling_factor"`
   otherwise.
