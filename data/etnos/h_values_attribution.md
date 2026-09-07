# H Values — Absolute Magnitudes for the 16-ETNO Catalog

Source file: `data/etnos/h_values.csv`

## Source

All values retrieved from the **JPL Small-Body Database (SBDB) API**
(NASA/JPL SSD/CNEOS): `https://ssd-api.jpl.nasa.gov/sbdb.api`

Query pattern: `sbdb.api?sstr=<designation>&phys-par=1` (SBDB API v1.3,
`phys-par=1` requests the physical-parameters section containing `H`).

Queried: 2026-09-07.

Each `H` is the absolute magnitude (V-band, at 1 AU from Sun and observer)
with the SBDB solution reference identifier in the `ref` column.

## Why a separate file

`data/etnos/catalog_validated.csv` has no `H` column — it carries only the
six classical orbital elements plus metadata. These H values are used as the
**prior for the synthetic population's brightness** in the observational bias
model (`bias_model: h_prior_from_catalog` in
`configs/science/observational_bias.yaml`). The synthetic population replicates
the real sample's brightness distribution while angles stay uniform-random.

## Usage in code

- `planet9lab/selection_bias.py::load_h_catalog()` reads this file.
- `generate_synthetic_population()` draws H values with replacement.
- `apply_selection_function()` uses per-object H to compute depth survival
  probability (brighter objects survive more often), replacing the old
  fixed-probability approximation.

## Albedo

The standard albedo used elsewhere in the pipeline is **0.10** (Sheppard &
Trujillo 2016, AJ 152:221 — moderate albedo adopted in that paper to estimate
ETNO diameters from H in the absence of direct measurement).

- Published version: https://iopscience.iop.org/article/10.3847/1538-3881/152/6/221
- Preprint: https://arxiv.org/pdf/1608.08772

## Granular albedo by dynamical class (optional refinement)

If per-class albedo granularity is needed, use the median measured albedos by
dynamical class published in **Johnston's Archive**:
https://www.johnstonsarchive.net/astro/tnoslist.html

The SDO class median (which includes EDD/ESDO/Sednoid objects in our catalog)
is 0.124.
