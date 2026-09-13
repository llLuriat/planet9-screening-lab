import math

from planet9lab.geometry.sky_projection import (
    DEFAULT_EPOCH_JD,
    OBLIQUITY_ARCSEC,
    _earth_heliocentric_ecliptic,
    orbital_elements_to_radec,
)


class TestEarthPosition:
    def test_earth_distance_at_catalog_epoch(self):
        xe, ye, ze = _earth_heliocentric_ecliptic(DEFAULT_EPOCH_JD)
        r = math.sqrt(xe**2 + ye**2 + ze**2)
        assert abs(r - 1.0126) < 0.001, f"Earth r={r:.6f}, expected ~1.0126 AU"

    def test_earth_in_ecliptic_plane(self):
        _, _, ze = _earth_heliocentric_ecliptic(DEFAULT_EPOCH_JD)
        assert abs(ze) < 1e-10, f"Earth z={ze}, expected ~0 (ecliptic plane)"

    def test_earth_distance_reasonable(self):
        xe, ye, ze = _earth_heliocentric_ecliptic(2451545.0)
        r = math.sqrt(xe**2 + ye**2 + ze**2)
        assert 0.98 < r < 1.02, f"Earth r={r:.6f}, expected near 1 AU"


class TestOrbitalToRadec:
    def test_ra_in_range(self):
        for i_deg in [0, 15, 30, 60, 89]:
            ra, _ = orbital_elements_to_radec(100.0, 0.3, i_deg, 45.0, 120.0, 60.0)
            assert 0.0 <= ra < 360.0, f"ra={ra} out of range for i={i_deg}"

    def test_dec_in_range(self):
        for i_deg in [0, 15, 30, 60, 89]:
            _, dec = orbital_elements_to_radec(100.0, 0.3, i_deg, 45.0, 120.0, 60.0)
            assert -90.0 <= dec <= 90.0, f"dec={dec} out of range for i={i_deg}"

    def test_distant_object_near_origin(self):
        ra, dec = orbital_elements_to_radec(1000.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert abs(ra) < 1.0 or abs(ra - 360.0) < 1.0, f"ra={ra}, expected ~0"
        assert abs(dec) < 1.0, f"dec={dec}, expected ~0"

    def test_high_inclination_offsets_dec(self):
        _, dec_eq = orbital_elements_to_radec(100.0, 0.0, 0.0, 90.0, 0.0, 0.0)
        _, dec_hi = orbital_elements_to_radec(100.0, 0.0, 60.0, 90.0, 0.0, 0.0)
        assert abs(dec_hi) > abs(dec_eq), "higher inclination should offset dec"

    def test_obliquity_value(self):
        assert OBLIQUITY_ARCSEC == 84381.406

    def test_default_epoch(self):
        assert DEFAULT_EPOCH_JD == 2456800.5
