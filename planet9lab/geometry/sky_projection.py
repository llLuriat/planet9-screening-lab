"""Orbital elements to RA/Dec sky projection for synthetic populations.

Provides orbital_elements_to_radec: given heliocentric ecliptic
J2000 orbital elements of an object, compute its geocentric equatorial
(RA, Dec) position at a fixed reference epoch.

Physics pipeline:
1. Object position via REBOUND.Particle (heliocentric ecliptic J2000).
2. Earth position via Keplerian elements (Meeus, no planetary perturbations).
3. Geocentric = object - Earth (still ecliptic J2000).
4. Rotate ecliptic to equatorial (IAU 2006 obliquity = 84381.406 arcsec).
5. Convert Cartesian to RA/Dec (degrees).
"""

import math

import rebound

# IAU 2006 mean obliquity of the ecliptic at J2000 (arcsec).
# Source: IAU 2006 precession-nutation model (Hilton et al. 2006), value
# quoted in the session plan as the Auditor's fixed constant.
OBLIQUITY_ARCSEC = 84381.406

# Keplerian mean orbital elements of the Earth at J2000.0 (ecliptic of date).
# Source: J. Meeus, "Astronomical Algorithms", 2nd ed. (1998), Ch. 25
# (Solar Coordinates): a = 1.000001018 AU, e = 0.0167086,
# omega (perihelion longitude) = 102.9373 deg, M (J2000) = 358.617 deg,
# n = 0.9856076686 deg/day. Approximation: no planetary perturbations;
# expected Earth position error ~1000 km (accepted Option A in the plan).
_EARTH_A = 1.000001018
_EARTH_E = 0.0167086
_EARTH_W_DEG = 102.9373
_EARTH_M_J2000_DEG = 358.617
_EARTH_N_DEG = 0.9856076686
DEFAULT_EPOCH_JD = 2456800.5


def _earth_heliocentric_ecliptic(jd):
    d = jd - 2451545.0
    M_deg = (_EARTH_M_J2000_DEG + _EARTH_N_DEG * d) % 360.0
    M_rad = math.radians(M_deg)
    E_rad = M_rad
    for _ in range(50):
        dE = (E_rad - _EARTH_E * math.sin(E_rad) - M_rad) / (1.0 - _EARTH_E * math.cos(E_rad))
        E_rad -= dE
        if abs(dE) < 1e-12:
            break
    nu_rad = 2.0 * math.atan(math.sqrt((1.0 + _EARTH_E) / (1.0 - _EARTH_E)) * math.tan(E_rad / 2.0))
    r = _EARTH_A * (1.0 - _EARTH_E * math.cos(E_rad))
    omega_rad = math.radians(_EARTH_W_DEG)
    x = r * math.cos(omega_rad + nu_rad)
    y = r * math.sin(omega_rad + nu_rad)
    z = 0.0
    return x, y, z


def orbital_elements_to_sky(a_au, e, i_deg, omega_deg, Omega_deg, M_deg, epoch_jd=DEFAULT_EPOCH_JD):
    """Full single-epoch sky state: ``(ra_deg, dec_deg, delta_au, r_au)``.

    Same physics pipeline as the module docstring (REBOUND heliocentric
    ecliptic J2000 -> Earth via Keplerian elements (Meeus, Ch. 25) ->
    geocentric vector -> IAU 2006 obliquity rotation -> RA/Dec), plus the two
    distances that are consistent with that SAME geometry at the SAME epoch:

    - ``r_au``   : heliocentric distance of the object, |obj - Sun|.
    - ``delta_au``: geocentric distance, |obj - Earth|, at ``epoch_jd``.

    Returning the distances alongside RA/Dec lets callers pair apparent
    magnitudes (V = H + 5 log10(r * Delta)) with the projected position
    coherently, instead of drawing an independent anomaly/offset for the
    distances (integrated into ``generate_synthetic_population`` 2026-09-26).
    """
    sim = rebound.Simulation()
    sim.add(m=1.0)
    sim.add(m=0.0, a=a_au, e=e, inc=math.radians(i_deg), omega=math.radians(omega_deg), Omega=math.radians(Omega_deg), M=math.radians(M_deg))
    p = sim.particles[1]
    x_obj, y_obj, z_obj = p.x, p.y, p.z
    r_au = math.sqrt(x_obj**2 + y_obj**2 + z_obj**2)
    x_earth, y_earth, z_earth = _earth_heliocentric_ecliptic(epoch_jd)
    x_geo = x_obj - x_earth
    y_geo = y_obj - y_earth
    z_geo = z_obj - z_earth
    delta_au = math.sqrt(x_geo**2 + y_geo**2 + z_geo**2)
    eps_rad = math.radians(OBLIQUITY_ARCSEC / 3600.0)
    cos_eps = math.cos(eps_rad)
    sin_eps = math.sin(eps_rad)
    x_eq = x_geo
    y_eq = y_geo * cos_eps - z_geo * sin_eps
    z_eq = y_geo * sin_eps + z_geo * cos_eps
    r = math.sqrt(x_eq**2 + y_eq**2 + z_eq**2)
    ra_deg = math.degrees(math.atan2(y_eq, x_eq)) % 360.0
    dec_deg = math.degrees(math.asin(max(-1.0, min(1.0, z_eq / r))))
    return ra_deg, dec_deg, delta_au, r_au


def orbital_elements_to_radec(a_au, e, i_deg, omega_deg, Omega_deg, M_deg, epoch_jd=DEFAULT_EPOCH_JD):
    """RA/Dec-only convenience wrapper around :func:`orbital_elements_to_sky`.

    Output is bit-identical to the original implementation (same operation
    order); the distances are simply discarded here.
    """
    ra_deg, dec_deg, _delta_au, _r_au = orbital_elements_to_sky(
        a_au, e, i_deg, omega_deg, Omega_deg, M_deg, epoch_jd=epoch_jd
    )
    return ra_deg, dec_deg
