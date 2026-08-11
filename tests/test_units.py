import math

from planet9lab.constants import deg_to_rad, earth_mass_to_solar_mass, normalize_degrees
from planet9lab.metrics import angular_distance_deg


def test_earth_mass_to_solar_mass_positive():
    assert 2.9e-6 < earth_mass_to_solar_mass(1) < 3.1e-6


def test_deg_to_rad_half_turn():
    assert abs(deg_to_rad(180) - math.pi) < 1e-12


def test_wrap_degrees_normalizes_negative():
    assert normalize_degrees(-30) == 330


def test_angular_distance_wraps():
    assert angular_distance_deg(350, 10) == 20

