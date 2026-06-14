"""
cache_results.py — Pre-compute and cache one full pipeline run.
Run this AFTER tle_fetcher.py and BEFORE the demo.

Creates data/sample_results.json — your safety net if live run is slow.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone

from propagator import propagate_all, get_current_positions, load_all_satellites
from conjunction import detect_conjunctions

DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "sample_results.json"


def run_and_cache():
    print("\n=== AstroGuard — Pre-computing cache ===\n")
    t_start = time.time()

    print("[1/3] Loading satellites...")
    satellites = load_all_satellites()
    print(f"  {len(satellites)} objects loaded.\n")

    print("[2/3] Propagating orbits (24 hrs, 5-min steps)...")
    propagation = propagate_all(satellites, timestep_minutes=5, hours=24)
    print(f"  Propagated {len(propagation)} objects.\n")

    print("[3/3] Detecting conjunctions (threshold: 25 km)...")
    events = detect_conjunctions(propagation, threshold_km=25.0)
    objects = get_current_positions(propagation)
    print(f"  Found {len(events)} conjunction events.\n")

    elapsed = round(time.time() - t_start, 2)

    # Save
    DATA_DIR.mkdir(exist_ok=True)
    cache = {
        "events": events,
        "objects": objects,
        "saved_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_objects": len(satellites),
        "analysis_time_s": elapsed,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"✓ Cache saved → {CACHE_FILE}")
    print(f"  Total time: {elapsed}s")
    print(f"  Events: {len(events)}")
    print(f"  Objects: {len(objects)}")

    if events:
        print("\nTop 5 closest approaches:")
        for e in events[:5]:
            print(f"  [{e['risk_level'].upper():8}] {e['obj_a'][:20]:<20} ↔ {e['obj_b'][:20]:<20} → {e['min_dist_km']:.2f} km at {e['closest_time']}")
    else:
        print("\n  No conjunctions found with current TLE data.")
        print("  This is normal — try adjusting CONJUNCTION_THRESHOLD_KM upward.")
        print("  The demo will still work with the cached empty result.")

    return cache


if __name__ == "__main__":
    run_and_cache()
