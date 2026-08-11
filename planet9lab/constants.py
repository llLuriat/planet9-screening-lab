"""Physical constants and small unit helpers used by Planet9 Screening Lab."""

from __future__ import annotations

import math

AU_M = 149_597_870_700.0
DAY_S = 86_400.0
YEAR_DAYS = 365.25
YEAR_S = YEAR_DAYS * DAY_S
SOLAR_MASS_KG = 1.98847e30
EARTH_MASS_KG = 5.9722e24
G_SI = 6.67430e-11
GAUSSIAN_K = 0.01720209895
MU_SUN_AU3_DAY2 = GAUSSIAN_K * GAUSSIAN_K
DEG_TO_RAD = math.pi / 180.0
RAD_TO_DEG = 180.0 / math.pi


def deg_to_rad(value: float) -> float:
    return value * DEG_TO_RAD


def rad_to_deg(value: float) -> float:
    return value * RAD_TO_DEG


def normalize_degrees(value: float) -> float:
    return value % 360.0


def wrap_degrees(value: float) -> float:
    return normalize_degrees(value)


def au_to_m(value: float) -> float:
    return value * AU_M


def m_to_au(value: float) -> float:
    return value / AU_M


def earth_mass_to_solar(value: float) -> float:
    return value * EARTH_MASS_KG / SOLAR_MASS_KG


def earth_mass_to_solar_mass(value: float) -> float:
    return earth_mass_to_solar(value)


def orbital_period_years(a_au: float) -> float:
    return math.sqrt(a_au**3)
