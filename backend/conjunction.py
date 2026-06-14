"""
conjunction.py — Close-approach (conjunction) detection engine.

Two-pass algorithm:
  1. Coarse pass: every 5-min timestep → find candidate pairs < threshold
  2. Fine pass: refine each candidate with 30-sec interpolation

Output: list of conjunction event dicts matching P2's contract.
"""

import math
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from itertools import combinations

from sgp4.api import Satrec, jday

DATA_DIR = Path(__file__).parent / "data"

# ─── Configurable thresholds ──────────────────────────────────────────────────
CONJUNCTION_THRESHOLD_KM = 25.0     # flag if closer than this
FINE_PASS_WINDOW_MINUTES = 15       # refine ±15 min around coarse closest approach
FINE_PASS_STEP_SECONDS = 30         # 30-second steps for fine refinement


def detect_conjunctions(
    propagation: dict,
    threshold_km: float = CONJUNCTION_THRESHOLD_KM,
) -> list[dict]:
    """
    Find all close-approach events in a propagation result.

    Args:
        propagation: output of propagator.propagate_all()
                     {sat_name: [{"ts":str, "x":f, "y":f, "z":f, "vx":f,...}, ...]}
        threshold_km: flag pairs that come closer than this

    Returns:
        List of conjunction events sorted by min_dist_km ascending:
        [
          {
            "id": int,
            "obj_a": str,
            "obj_b": str,
            "min_dist_km": float,
            "closest_time": str,   # ISO-8601 UTC
            "rel_velocity_kms": float,
            "risk_level": str      # "critical" / "high" / "medium"
          }, ...
        ]
    """
    sat_names = list(propagation.keys())
    n = len(sat_names)
    print(f"  Checking {n} objects → {n*(n-1)//2} pairs...")

    events = []
    checked = 0
    flagged = 0

    for name_a, name_b in combinations(sat_names, 2):
        if _same_object_family(name_a, name_b):
            continue
        track_a = propagation[name_a]
        track_b = propagation[name_b]

        # Both tracks must have the same number of timesteps
        min_len = min(len(track_a), len(track_b))
        if min_len < 2:
            continue

        # ── Coarse pass ──────────────────────────────────────────────────────
        min_dist = float("inf")
        min_idx = 0

        for i in range(min_len):
            pa = (track_a[i]["x"], track_a[i]["y"], track_a[i]["z"])
            pb = (track_b[i]["x"], track_b[i]["y"], track_b[i]["z"])
            d = _dist(pa, pb)
            if d < min_dist:
                min_dist = d
                min_idx = i

        checked += 1
        if min_dist >= threshold_km:
            continue

        flagged += 1

        # ── Fine pass — refine around coarse closest approach ─────────────
        coarse_ts_str = track_a[min_idx]["ts"]
        coarse_dt = datetime.strptime(coarse_ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

        fine_result = _fine_pass(
            name_a, name_b,
            sat_a_tle=_get_tle(name_a),
            sat_b_tle=_get_tle(name_b),
            around_dt=coarse_dt,
        )

        if fine_result:
            min_dist_km, closest_time, rel_vel = fine_result
        else:
            # Fall back to coarse values
            va = (track_a[min_idx]["vx"], track_a[min_idx]["vy"], track_a[min_idx]["vz"])
            vb = (track_b[min_idx]["vx"], track_b[min_idx]["vy"], track_b[min_idx]["vz"])
            rel_vel = _dist(
                (va[0]-vb[0], va[1]-vb[1], va[2]-vb[2]),
                (0, 0, 0)
            )
            min_dist_km = min_dist
            closest_time = coarse_ts_str

        events.append({
            "id": len(events),
            "obj_a": name_a,
            "obj_b": name_b,
            "min_dist_km": round(min_dist_km, 3),
            "closest_time": closest_time if isinstance(closest_time, str) else closest_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rel_velocity_kms": round(rel_vel, 3),
            "risk_level": _risk_level(min_dist_km),
        })
        if min_dist_km >= threshold_km:
            continue

    print(f"  ✓ Checked {checked} pairs, found {flagged} conjunctions below {threshold_km} km")
    events.sort(key=lambda e: e["min_dist_km"])

    # Re-assign IDs after sort
    for i, ev in enumerate(events):
        ev["id"] = i

    return events


def _fine_pass(
    name_a: str,
    name_b: str,
    sat_a_tle: dict | None,
    sat_b_tle: dict | None,
    around_dt: datetime,
    window_minutes: int = FINE_PASS_WINDOW_MINUTES,
    step_seconds: int = FINE_PASS_STEP_SECONDS,
) -> tuple | None:
    """
    Re-propagate both satellites at fine time steps around the coarse closest approach.
    Returns (min_dist_km, closest_dt, rel_velocity_kms) or None if TLEs unavailable.
    """
    if sat_a_tle is None or sat_b_tle is None:
        return None

    try:
        sat_a = Satrec.twoline2rv(sat_a_tle["line1"], sat_a_tle["line2"])
        sat_b = Satrec.twoline2rv(sat_b_tle["line1"], sat_b_tle["line2"])
    except Exception:
        return None

    start = around_dt - timedelta(minutes=window_minutes)
    end = around_dt + timedelta(minutes=window_minutes)

    min_dist = float("inf")
    best_dt = around_dt
    best_rel_vel = 0.0

    current = start
    dt_step = timedelta(seconds=step_seconds)

    while current <= end:
        jd, fr = jday(current.year, current.month, current.day,
                      current.hour, current.minute,
                      current.second + current.microsecond / 1e6)

        e1, r1, v1 = sat_a.sgp4(jd, fr)
        e2, r2, v2 = sat_b.sgp4(jd, fr)

        if e1 == 0 and e2 == 0:
            d = _dist(r1, r2)
            if d < min_dist:
                min_dist = d
                best_dt = current
                # relative velocity magnitude
                best_rel_vel = _dist(
                    (v1[0]-v2[0], v1[1]-v2[1], v1[2]-v2[2]),
                    (0, 0, 0)
                )

        current += dt_step

    return min_dist, best_dt, best_rel_vel


def _dist(a: tuple, b: tuple) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)


def _risk_level(dist_km: float) -> str:
    if dist_km <= 5:
        return "high"
    elif dist_km < 25:
        return "medium"
    else:
        return "low"


# ─── TLE cache (loaded lazily so we don't re-read on every pair) ──────────────
_tle_cache: dict[str, dict] = {}


def _get_tle(name: str) -> dict | None:
    """Look up a satellite's TLE by name from the cached files."""
    global _tle_cache
    if not _tle_cache:
        _load_tle_cache()
    return _tle_cache.get(name)

def _same_object_family(name_a: str, name_b: str) -> bool:
    """Skip pairs that are modules of the same station."""
    ISS_MODULES = {"ISS (ZARYA)", "ISS (UNITY)", "ISS (ZVEZDA)", "ISS (DESTINY)", 
                   "ISS (QUEST)", "ISS (PIRS)", "ISS (HARMONY)", "ISS (TRANQUILITY)",
                   "ISS (SERENITY)", "ISS (KUPOLA)", "ISS (RASSVET)", "ISS (NAUKA)"}
    if name_a in ISS_MODULES and name_b in ISS_MODULES:
        return True
    # General rule: if both names start with the same word, skip
    prefix_a = name_a.split()[0]
    prefix_b = name_b.split()[0]
    return prefix_a == prefix_b and len(prefix_a) > 2

def _load_tle_cache():
    """Load all TLEs into memory once."""
    global _tle_cache
    for fname in ["tle_active.txt", "tle_debris.txt"]:
        fpath = DATA_DIR / fname
        if not fpath.exists():
            continue
        lines = [l.strip() for l in fpath.read_text(errors="ignore").splitlines() if l.strip()]
        i = 0
        while i < len(lines) - 2:
            name = lines[i]
            l1, l2 = lines[i+1], lines[i+2]
            if l1.startswith("1 ") and l2.startswith("2 "):
                _tle_cache[name] = {"name": name, "line1": l1, "line2": l2}
                i += 3
            else:
                i += 1

    # Also try JSON
    for fname in ["satellites.json", "debris.json"]:
        fpath = DATA_DIR / fname
        if fpath.exists():
            try:
                with open(fpath) as f:
                    for s in json.load(f):
                        _tle_cache.setdefault(s["name"], s)
            except Exception:
                pass

    print(f"  TLE cache: {len(_tle_cache)} objects loaded")


if __name__ == "__main__":
    from propagator import propagate_all
    print("=== AstroGuard Conjunction Detector Test ===\n")
    prop = propagate_all()
    events = detect_conjunctions(prop, threshold_km=25.0)
    print(f"\nConjunction events found: {len(events)}")
    for e in events[:5]:
        print(f"  [{e['risk_level'].upper()}] {e['obj_a']} ↔ {e['obj_b']}: {e['min_dist_km']} km at {e['closest_time']}")
