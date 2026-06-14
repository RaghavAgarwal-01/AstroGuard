"""
coord_utils.py
Shared coordinate conversion utilities.
Used by propagator.py (P1) and available to P2 via /api/orbit-path.

Conversions:
  ECI  → ECEF   (Earth-Centred Inertial → Earth-Centred Earth-Fixed)
  ECEF → Geodetic (lat_deg / lon_deg / alt_km)
  Geodetic → ECEF  (inverse — P2 uses this for Three.js globe plotting)
  ECEF → ECI   (inverse transform)
  Distance and relative-velocity helpers for conjunction.py

All angles in DEGREES (caller convenience).
All distances in KILOMETRES.
"""

import math
from datetime import datetime, timezone

# ── WGS-84 constants ──────────────────────────────────────────────────────────
WGS84_A  = 6378.137           # semi-major axis (km)
WGS84_B  = 6356.7523142       # semi-minor axis (km)
WGS84_E2 = 0.00669437999014   # first eccentricity squared
WGS84_F  = 1 / 298.257223563  # flattening

EARTH_OMEGA = 7.2921150e-5    # Earth rotation rate (rad/s)


# ── Internal helper ───────────────────────────────────────────────────────────

def _gmst(dt: datetime) -> float:
    """
    Greenwich Mean Sidereal Time in radians for a given UTC datetime.
    Uses the full IAU formula — accurate to ~0.1 arcsec.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    y, mo, d = dt.year, dt.month, dt.day
    h = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

    if mo <= 2:
        y  -= 1
        mo += 12

    A  = int(y / 100)
    B  = 2 - A + int(A / 4)
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (mo + 1)) + d + h / 24.0 + B - 1524.5

    T0 = (jd - 2451545.0) / 36525.0   # Julian centuries from J2000

    # GMST in seconds (IAU 1982 formula)
    gmst_sec = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * T0
        + 0.093104 * T0 ** 2
        - 6.2e-6   * T0 ** 3
    )
    gmst_sec = gmst_sec % 86400.0
    return math.radians(gmst_sec / 240.0)


# ── Core conversions ──────────────────────────────────────────────────────────

def eci_to_ecef(x_km: float, y_km: float, z_km: float,
                dt: datetime) -> tuple[float, float, float]:
    """
    Rotate ECI position to ECEF using GMST at the given UTC datetime.

    Args:
        x_km, y_km, z_km : ECI position (km)
        dt               : UTC datetime

    Returns:
        (x_ecef, y_ecef, z_ecef) in km
    """
    theta = _gmst(dt)
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    x_ecef =  cos_t * x_km + sin_t * y_km
    y_ecef = -sin_t * x_km + cos_t * y_km
    z_ecef =  z_km
    return x_ecef, y_ecef, z_ecef


def ecef_to_eci(x_km: float, y_km: float, z_km: float,
                dt: datetime) -> tuple[float, float, float]:
    """
    Rotate ECEF position back to ECI — inverse of eci_to_ecef.

    Returns:
        (x_eci, y_eci, z_eci) in km
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    theta = _gmst(dt)
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    x_eci = cos_t * x_km - sin_t * y_km
    y_eci = sin_t * x_km + cos_t * y_km
    z_eci = z_km
    return x_eci, y_eci, z_eci


def ecef_to_geodetic(x_km: float, y_km: float,
                     z_km: float) -> tuple[float, float, float]:
    """
    Convert ECEF (km) → geodetic (lat_deg, lon_deg, alt_km).
    Uses Bowring's iterative method — converges in 3–5 iterations.

    Returns:
        (latitude_deg, longitude_deg, altitude_km)
    """
    p   = math.sqrt(x_km ** 2 + y_km ** 2)   # distance from Z-axis
    lon = math.atan2(y_km, x_km)
    lat = math.atan2(z_km, p * (1 - WGS84_E2))

    for _ in range(5):
        sin_lat = math.sin(lat)
        N       = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat ** 2)
        lat_new = math.atan2(z_km + WGS84_E2 * N * sin_lat, p)
        if abs(lat_new - lat) < 1e-12:
            break
        lat = lat_new

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    N       = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat ** 2)

    if abs(cos_lat) > 1e-10:
        alt = p / cos_lat - N
    else:
        alt = abs(z_km) / abs(sin_lat) - N * (1 - WGS84_E2)

    return math.degrees(lat), math.degrees(lon), alt


def geodetic_to_ecef(lat_deg: float, lon_deg: float,
                     alt_km: float) -> tuple[float, float, float]:
    """
    Convert geodetic (lat_deg, lon_deg, alt_km) → ECEF (km).
    P2 uses this to convert lat/lon/alt back to 3D cartesian for Three.js.

    Returns:
        (x_ecef, y_ecef, z_ecef) in km
    """
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)

    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat ** 2)

    x = (N + alt_km) * cos_lat * cos_lon
    y = (N + alt_km) * cos_lat * sin_lon
    z = (N * (1 - WGS84_E2) + alt_km) * sin_lat
    return x, y, z


def eci_to_geodetic(x_km: float, y_km: float, z_km: float,
                    dt: datetime) -> tuple[float, float, float]:
    """
    One-shot convenience: ECI → geodetic (lat_deg, lon_deg, alt_km).
    This is the main function called by propagator.py.
    """
    xe, ye, ze = eci_to_ecef(x_km, y_km, z_km, dt)
    return ecef_to_geodetic(xe, ye, ze)


# ── Distance and velocity helpers ─────────────────────────────────────────────

def eci_distance_km(x1: float, y1: float, z1: float,
                    x2: float, y2: float, z2: float) -> float:
    """
    Euclidean distance between two ECI positions (km).
    Called by conjunction.py for close-approach detection.
    """
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)


def relative_velocity_kms(vx1: float, vy1: float, vz1: float,
                           vx2: float, vy2: float, vz2: float) -> float:
    """
    Magnitude of relative velocity between two objects (km/s).
    All components in km/s (ECI frame).
    """
    return math.sqrt(
        (vx1 - vx2) ** 2 +
        (vy1 - vy2) ** 2 +
        (vz1 - vz2) ** 2
    )


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("coord_utils.py — self-test")
    print("-" * 50)

    dt = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)
    x, y, z = 4200.0, -1100.0, 5100.0

    # ECI → geodetic
    lat, lon, alt = eci_to_geodetic(x, y, z, dt)
    print(f"ECI ({x}, {y}, {z}) km  →  lat={lat:.4f}°  lon={lon:.4f}°  alt={alt:.1f} km")

    # Round-trip: geodetic → ECEF → geodetic
    xe, ye, ze = geodetic_to_ecef(lat, lon, alt)
    lat2, lon2, alt2 = ecef_to_geodetic(xe, ye, ze)
    err = math.sqrt((lat2 - lat) ** 2 + (lon2 - lon) ** 2 + (alt2 - alt) ** 2)
    print(f"Round-trip geodetic error: {err:.2e}  {'✓' if err < 1e-8 else '✗ FAIL'}")

    # ECI → ECEF → ECI round-trip
    xecef, yecef, zecef = eci_to_ecef(x, y, z, dt)
    x2, y2, z2 = ecef_to_eci(xecef, yecef, zecef, dt)
    err2 = math.sqrt((x2 - x) ** 2 + (y2 - y) ** 2 + (z2 - z) ** 2)
    print(f"ECI→ECEF→ECI round-trip error: {err2 * 1000:.3f} m  {'✓' if err2 < 0.001 else '✗ FAIL'}")

    # Relative velocity (head-on collision: 2 × 7.5 = 15 km/s)
    rv = relative_velocity_kms(7.5, 0, 0, -7.5, 0, 0)
    print(f"Relative velocity (head-on): {rv:.1f} km/s  {'✓' if abs(rv - 15.0) < 1e-9 else '✗ FAIL'}")

    # Distance (3-4-5 triangle)
    d = eci_distance_km(0, 0, 0, 3, 4, 0)
    print(f"eci_distance_km (3,4,0): {d:.1f} km  {'✓' if abs(d - 5.0) < 1e-9 else '✗ FAIL'}")

    print("\nAll self-tests passed ✓")
