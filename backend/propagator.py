"""
propagator.py — SGP4 orbit propagation engine.
Reads TLE files, computes positions for every object over the next 24 hours.

Output: dict {sat_name: [(ts_iso, x, y, z, vx, vy, vz, lat, lon, alt), ...]}
"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sgp4.api import Satrec, jday
from coord_utils import eci_to_geodetic, eci_distance_km

DATA_DIR = Path(__file__).parent / "data"

# Configurable constants (override via .env or function args)
TIMESTEP_MINUTES = 5          # position sample interval
PROPAGATION_HOURS = 24        # how far ahead to propagate


def load_tle_file(filepath: Path) -> list[dict]:
    """Load TLE data from a 3-line text file."""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    satellites = []
    i = 0
    while i < len(lines) - 2:
        name = lines[i]
        l1 = lines[i + 1]
        l2 = lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            satellites.append({"name": name, "line1": l1, "line2": l2})
            i += 3
        else:
            i += 1
    return satellites


def load_all_satellites() -> list[dict]:
    """Load active + debris TLEs. Falls back to JSON if text files missing."""
    sats = []

    active_txt = DATA_DIR / "tle_active.txt"
    debris_txt = DATA_DIR / "tle_debris.txt"
    active_json = DATA_DIR / "satellites.json"
    debris_json = DATA_DIR / "debris.json"

    if active_txt.exists():
        sats += load_tle_file(active_txt)
    elif active_json.exists():
        with open(active_json) as f:
            sats += json.load(f)

    if debris_txt.exists():
        sats += load_tle_file(debris_txt)
    elif debris_json.exists():
        with open(debris_json) as f:
            sats += json.load(f)

    if not sats:
        print("  ⚠ No TLE files found. Using stub data.")
        sats = _stub_satellites()

    print(f"  Loaded {len(sats)} objects from TLE files.")
    return sats


def propagate_all(
    satellites: list[dict] | None = None,
    timestep_minutes: int = TIMESTEP_MINUTES,
    hours: int = PROPAGATION_HOURS,
) -> dict:
    """
    Propagate all satellites forward in time.

    Returns:
        {
          "sat_name": [
            {
              "ts": "2026-06-14T12:00:00Z",
              "x": float, "y": float, "z": float,   # ECI km
              "vx": float, "vy": float, "vz": float, # km/s
              "lat": float, "lon": float, "alt_km": float
            }, ...
          ],
          ...
        }
    """
    if satellites is None:
        satellites = load_all_satellites()

    start_dt = datetime.now(tz=timezone.utc)
    steps = int(hours * 60 / timestep_minutes)
    timestamps = [start_dt + timedelta(minutes=i * timestep_minutes) for i in range(steps)]

    results = {}
    errors = 0

    print(f"  Propagating {len(satellites)} objects × {steps} timesteps...")

    for sat_info in satellites:
        name = sat_info["name"]
        try:
            sat = Satrec.twoline2rv(sat_info["line1"], sat_info["line2"])
        except Exception:
            errors += 1
            continue

        track = []
        for dt in timestamps:
            # sgp4 needs Julian date split into day + fraction
            jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
            error_code, r, v = sat.sgp4(jd, fr)

            if error_code != 0:
                continue  # skip bad propagation step (object decayed, etc.)

            x, y, z = r       # km ECI
            vx, vy, vz = v    # km/s ECI

            try:
                lat, lon, alt = eci_to_geodetic(x, y, z, dt)
            except Exception:
                lat, lon, alt = 0.0, 0.0, 0.0

            track.append({
                "ts": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "x": round(x, 3),
                "y": round(y, 3),
                "z": round(z, 3),
                "vx": round(vx, 6),
                "vy": round(vy, 6),
                "vz": round(vz, 6),
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "alt_km": round(alt, 2),
            })

        if track:
            results[name] = track

    print(f"  ✓ Propagated {len(results)} objects ({errors} skipped due to errors)")
    return results


def get_current_positions(propagation: dict | None = None) -> list[dict]:
    """
    Extract the CURRENT position (first timestep) for each satellite.
    This is what GET /api/objects returns.

    Returns:
        [{"name": str, "lat": float, "lon": float, "alt_km": float}, ...]
    """
    if propagation is None:
        propagation = propagate_all()

    positions = []
    for name, track in propagation.items():
        if track:
            first = track[0]
            positions.append({
                "name": name,
                "lat": first["lat"],
                "lon": first["lon"],
                "alt_km": first["alt_km"],
            })

    return positions


def _stub_satellites() -> list[dict]:
    """Minimal stub for offline development/testing."""
    return [
        {
            "name": "ISS (ZARYA)",
            "line1": "1 25544U 98067A   24001.50000000  .00020137  00000-0  36336-3 0  9990",
            "line2": "2 25544  51.6406  78.6043 0001899 323.6994  36.4163 15.49999786429637",
        },
        {
            "name": "HUBBLE",
            "line1": "1 20580U 90037B   24001.50000000  .00000760  00000-0  34258-4 0  9990",
            "line2": "2 20580  28.4698 240.8024 0002545 285.3050  74.7694 15.09350456344748",
        },
        {
            "name": "DEBRIS-TEST",
            "line1": "1 25730U 99025DEB 24001.50000000  .00000100  00000-0  20000-4 0  9990",
            "line2": "2 25730  98.5200 240.0000 0010000  90.0000 270.0000 14.20000000100000",
        },
    ]


if __name__ == "__main__":
    print("=== AstroGuard Propagator Test ===\n")
    results = propagate_all()
    print(f"\nFirst satellite: {list(results.keys())[0]}")
    first_track = list(results.values())[0]
    print(f"  First position: {first_track[0]}")
    print(f"  Track length: {len(first_track)} timesteps")
