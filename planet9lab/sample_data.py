from __future__ import annotations

from pathlib import Path

from .artifacts import write_csv, write_text

ROOT = Path(__file__).resolve().parent.parent

ETNOS = [
    {
        "name": "Sedna",
        "a_au": 506,
        "e": 0.855,
        "i_deg": 11.9,
        "omega_deg": 311.3,
        "Omega_deg": 144.5,
        "mean_anomaly_deg": 358.0,
        "epoch": "J2000",
        "frame": "heliocentric_ecliptic",
        "source": "example_fixture_from_initial_v1",
        "validation_status": "partial",
        "selection_included": True,
        "selection_reason": "a_au_gt_150_and_q_gt_30",
        "selection_notes": "Example ETNO migrated from fixture; values are simplified and require validation.",
    },
    {
        "name": "2012_VP113",
        "a_au": 266,
        "e": 0.69,
        "i_deg": 24.0,
        "omega_deg": 293.8,
        "Omega_deg": 90.8,
        "mean_anomaly_deg": 12.0,
        "epoch": "J2000",
        "frame": "heliocentric_ecliptic",
        "source": "example_fixture_from_initial_v1",
        "validation_status": "partial",
        "selection_included": True,
        "selection_reason": "a_au_gt_150_and_q_gt_30",
        "selection_notes": "Included by explicit V1 fixture criterion.",
    },
    {
        "name": "2015_TG387",
        "a_au": 1170,
        "e": 0.94,
        "i_deg": 11.7,
        "omega_deg": 118.2,
        "Omega_deg": 300.9,
        "mean_anomaly_deg": 4.0,
        "epoch": "J2000",
        "frame": "heliocentric_ecliptic",
        "source": "example_fixture_from_initial_v1",
        "validation_status": "partial",
        "selection_included": True,
        "selection_reason": "a_au_gt_150_and_q_gt_30",
        "selection_notes": "High-a ETNO fixture.",
    },
    {
        "name": "2014_SR349",
        "a_au": 290,
        "e": 0.84,
        "i_deg": 18.0,
        "omega_deg": 341.0,
        "Omega_deg": 34.8,
        "mean_anomaly_deg": 30.0,
        "epoch": "J2000",
        "frame": "heliocentric_ecliptic",
        "source": "example_fixture_from_initial_v1",
        "validation_status": "partial",
        "selection_included": True,
        "selection_reason": "a_au_gt_150_and_q_gt_30",
        "selection_notes": "Included to avoid hand-picking only favorable examples.",
    },
    {
        "name": "Pluto",
        "a_au": 39.5,
        "e": 0.249,
        "i_deg": 17.1,
        "omega_deg": 113.8,
        "Omega_deg": 110.3,
        "mean_anomaly_deg": 14.0,
        "epoch": "J2000",
        "frame": "heliocentric_ecliptic",
        "source": "example_fixture_from_initial_v1",
        "validation_status": "partial",
        "selection_included": False,
        "selection_reason": "a_au_below_etno_threshold",
        "selection_notes": "Excluded control example demonstrating transparent selection.",
    },
]

GIANTS = [
    {"name": "Jupiter", "mass_solar": 0.0009547919, "a_au": 5.2044, "e": 0.0489, "i_deg": 1.304, "omega_deg": 273.867, "Omega_deg": 100.464, "mean_anomaly_deg": 20.020, "epoch": "J2000"},
    {"name": "Saturn", "mass_solar": 0.0002858857, "a_au": 9.5826, "e": 0.0565, "i_deg": 2.485, "omega_deg": 339.392, "Omega_deg": 113.665, "mean_anomaly_deg": 317.020, "epoch": "J2000"},
    {"name": "Uranus", "mass_solar": 0.0000436624, "a_au": 19.2184, "e": 0.0463, "i_deg": 0.773, "omega_deg": 96.998, "Omega_deg": 74.006, "mean_anomaly_deg": 142.238, "epoch": "J2000"},
    {"name": "Neptune", "mass_solar": 0.0000515139, "a_au": 30.1104, "e": 0.0095, "i_deg": 1.770, "omega_deg": 273.187, "Omega_deg": 131.784, "mean_anomaly_deg": 256.228, "epoch": "J2000"},
]

CANDIDATES = [
    {"candidate_id": "p9_mid_mass_aligned", "mass_earth": 5.0, "a_au": 500, "e": 0.25, "i_deg": 20, "omega_deg": 150, "Omega_deg": 80, "mean_anomaly_deg": 0},
    {"candidate_id": "p9_high_mass_family", "mass_earth": 7.0, "a_au": 620, "e": 0.32, "i_deg": 25, "omega_deg": 145, "Omega_deg": 85, "mean_anomaly_deg": 30},
    {"candidate_id": "p9_low_mass_weak", "mass_earth": 2.0, "a_au": 450, "e": 0.18, "i_deg": 15, "omega_deg": 130, "Omega_deg": 70, "mean_anomaly_deg": 60},
    {"candidate_id": "p9_bad_geometry", "mass_earth": 6.0, "a_au": 500, "e": 0.2, "i_deg": 10, "omega_deg": 20, "Omega_deg": 30, "mean_anomaly_deg": 120},
    {"candidate_id": "p9_inner_unstable", "mass_earth": 8.0, "a_au": 260, "e": 0.45, "i_deg": 30, "omega_deg": 150, "Omega_deg": 80, "mean_anomaly_deg": 180},
]


def init_data() -> None:
    write_csv(ROOT / "data" / "etnos" / "catalog.csv", ETNOS)
    write_csv(ROOT / "data" / "solar_system" / "giants_epoch.csv", GIANTS)
    write_csv(ROOT / "data" / "candidates_example.csv", CANDIDATES)
    write_text(
        ROOT / "configs" / "candidates" / "mid_mass.yaml",
        "\n".join(
            [
                "candidate_id: p9_mid_mass_aligned",
                "mass_earth: 5.0",
                "a_au: 500",
                "e: 0.25",
                "i_deg: 20",
                "omega_deg: 150",
                "Omega_deg: 80",
                "mean_anomaly_deg: 0",
            ]
        )
        + "\n",
    )
