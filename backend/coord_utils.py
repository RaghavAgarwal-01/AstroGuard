"""
coord_utils.py — Coordinate system converters.
Shared utility used by propagator.py and consumed by P2's frontend via the API.

ECI (Earth-Centered Inertial) → ECEF → Geodetic (lat/lon/alt)
"""

import math
import numpy as np
from datetime import datetime, timezone


# WGS-84 ellipsoid constants
WGS84_A = 6378.137          # semi-major axis, km
WGS84_F = 1 / 298.257223563  # flattening
WGS84_B = WGS84_A * (1 - WGS84_F)          # semi-minor axis, km
WGS84_E2 = 1 - (WGS84_B / WGS84_A) ** 2   # eccentricity squared


def eci_to_ecef(x_km: float, y_km: float, z_km: float, dt: datetime) -> tuple[float, float, float]:
    """
    Convert ECI (Earth-Centered Inertial) to ECEF (Earth-Centered Earth-Fixed).
    Rotates by Earth's GMST (Greenwich Mean Sidereal Time).

    Args:
        x_km, y_km, z_km: ECI position in km
        dt: UTC datetime of the observation

    Returns:
        (x_ecef, y_ecef, z_ecef) in km
    """
    # GMST in radians — simplified formula (accurate to ~0.1 deg for demo)
    gmst = _gmst_radians(dt)
    cos_g = math.cos(gmst)
    sin_g = math.sin(gmst)

    x_ecef = cos_g * x_km + sin_g * y_km
    y_ecef = -sin_g * x_km + cos_g * y_km
    z_ecef = z_km

    return x_ecef, y_ecef, z_ecef


def ecef_to_geodetic(x_km: float, y_km: float, z_km: float) -> tuple[float, float, float]:
    """
    Convert ECEF (km) to geodetic (lat_deg, lon_deg, alt_km).
    Uses Bowring's iterative method — fast and accurate.

    Returns:
        (latitude_deg, longitude_deg, altitude_km)
    """
    lon_rad = math.atan2(y_km, x_km)
    p = math.sqrt(x_km**2 + y_km**2)  # distance from Z-axis

    # Iterative Bowring's method for latitude
    lat_rad = math.atan2(z_km, p * (1 - WGS84_E2))
    for _ in range(5):  # 5 iterations is always enough
        sin_lat = math.sin(lat_rad)
        N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat**2)  # radius of curvature
        lat_rad = math.atan2(z_km + WGS84_E2 * N * sin_lat, p)

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat**2)
    alt_km = p / cos_lat - N if abs(cos_lat) > 1e-10 else abs(z_km) / abs(sin_lat) - N * (1 - WGS84_E2)

    lat_deg = math.degrees(lat_rad)
    lon_deg = math.degrees(lon_rad)

    return lat_deg, lon_deg, alt_km


def eci_to_geodetic(x_km: float, y_km: float, z_km: float, dt: datetime) -> tuple[float, float, float]:
    """
    Full ECI → geodetic conversion.
    This is what propagator.py calls to produce lat/lon/alt for each satellite.

    Returns:
        (latitude_deg, longitude_deg, altitude_km)
    """
    x_ecef, y_ecef, z_ecef = eci_to_ecef(x_km, y_km, z_km, dt)
    return ecef_to_geodetic(x_ecef, y_ecef, z_ecef)


def eci_distance_km(pos_a: tuple, pos_b: tuple) -> float:
    """
    Euclidean distance between two ECI positions (x, y, z) in km.
    Used by conjunction detector.
    """
    return math.sqrt(
        (pos_a[0] - pos_b[0])**2 +
        (pos_a[1] - pos_b[1])**2 +
        (pos_a[2] - pos_b[2])**2
    )


def relative_velocity_kms(vel_a: tuple, vel_b: tuple) -> float:
    """
    Magnitude of relative velocity between two objects (km/s).
    vel_a, vel_b are (vx, vy, vz) in km/s.
    """
    return math.sqrt(
        (vel_a[0] - vel_b[0])**2 +
        (vel_a[1] - vel_b[1])**2 +
        (vel_a[2] - vel_b[2])**2
    )


# ─── Internal helper ──────────────────────────────────────────────────────────

def _gmst_radians(dt: datetime) -> float:
    """
    Compute Greenwich Mean Sidereal Time in radians.
    Accurate to ~0.1 degree — sufficient for our demo visualization.
    """
    # Julian date of J2000.0
    J2000 = 2451545.0

    # Convert datetime to Julian date
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jd = _datetime_to_julian(dt)

    T = (jd - J2000) / 36525.0  # Julian centuries from J2000

    # GMST in seconds (IAU formula)
    gmst_sec = (
        67310.54841
        + (876600 * 3600 + 8640184.812866) * T
        + 0.093104 * T**2
        - 6.2e-6 * T**3
    )

    # Convert to radians in [0, 2π]
    gmst_rad = math.fmod(gmst_sec * (2 * math.pi / 86400.0), 2 * math.pi)
    if gmst_rad < 0:
        gmst_rad += 2 * math.pi

    return gmst_rad


def _datetime_to_julian(dt: datetime) -> float:
    """Convert UTC datetime to Julian Date."""
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    jd = jdn + (dt.hour - 12) / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0
    return jd


# ─── Quick sanity test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ISS approximate ECI position for a test epoch
    test_dt = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)
    x, y, z = 6778.0, 0.0, 0.0  # rough position on equator at R=6778 km

    lat, lon, alt = eci_to_geodetic(x, y, z, test_dt)
    print(f"ECI ({x}, {y}, {z}) km at {test_dt}")
    print(f"  → Lat: {lat:.4f}°, Lon: {lon:.4f}°, Alt: {alt:.1f} km")
    print(f"  (ISS orbits at ~408 km alt — value should be close to 400 km)")
