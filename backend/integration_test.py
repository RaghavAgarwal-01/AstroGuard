"""
integration_test.py — Person C (Data & Glue)
Run this at merge time (Hour 5) to confirm the full stack is working end-to-end.

Usage:
    python integration_test.py [--base-url http://localhost:8000]

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed (details printed).
"""

import argparse
import json
import sys
import time

import requests

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_BASE = "http://localhost:8000"

PASS = "✓"
FAIL = "✗"


# ── Test helpers ──────────────────────────────────────────────────────────────
def check(name: str, result: bool, detail: str = "") -> bool:
    icon = PASS if result else FAIL
    line = f"  [{icon}] {name}"
    if detail:
        line += f"  —  {detail}"
    print(line)
    return result


def get(base: str, path: str, timeout: int = 15) -> tuple[int, any]:
    try:
        r = requests.get(base + path, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    except requests.RequestException as e:
        return 0, str(e)


def post(base: str, path: str, timeout: int = 90) -> tuple[int, any]:
    try:
        r = requests.post(base + path, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    except requests.RequestException as e:
        return 0, str(e)


# ── Individual checks ─────────────────────────────────────────────────────────
def test_server_reachable(base: str) -> bool:
    print("\n── 1. Server reachability ──")
    code, _ = get(base, "/api/objects", timeout=5)
    return check("Server is up", code != 0, f"HTTP {code}")


def test_objects_endpoint(base: str) -> tuple[bool, list]:
    print("\n── 2. GET /api/objects ──")
    results = []
    code, data = get(base, "/api/objects")
    results.append(check("Status 200", code == 200, f"got {code}"))

    if code != 200 or not isinstance(data, list):
        results.append(check("Response is a list", False, str(data)[:80]))
        return all(results), []

    results.append(check("Response is a list", True, f"{len(data)} objects"))
    results.append(check("Has ≥ 10 objects", len(data) >= 10, f"found {len(data)}"))

    if data:
        obj = data[0]
        for field in ("name", "lat", "lon", "alt_km"):
            results.append(check(f'Object has "{field}"', field in obj))
        results.append(check("lat in range [-90, 90]",  -90 <= obj.get("lat", 999) <= 90))
        results.append(check("lon in range [-180,180]", -180 <= obj.get("lon", 999) <= 180))
        results.append(check("alt_km > 0",              obj.get("alt_km", -1) > 0,
                              f"alt={obj.get('alt_km')} km"))

    return all(results), data


def test_run_analysis(base: str) -> tuple[bool, list]:
    print("\n── 3. POST /api/run-analysis ──")
    results = []
    print("     (this may take up to 90 s — running the full pipeline)")
    code, data = post(base, "/api/run-analysis", timeout=120)
    results.append(check("Status 200", code == 200, f"got {code}"))

    if code != 200 or not isinstance(data, list):
        results.append(check("Response is a list", False, str(data)[:80]))
        return all(results), []

    results.append(check("Response is a list", True, f"{len(data)} conjunction events"))

    if data:
        ev = data[0]
        for field in ("id", "obj_a", "obj_b", "min_dist_km", "closest_time", "rel_velocity_kms"):
            results.append(check(f'Event has "{field}"', field in ev))
        results.append(check("min_dist_km ≥ 0",   ev.get("min_dist_km", -1) >= 0))
        results.append(check("rel_velocity_kms > 0", ev.get("rel_velocity_kms", 0) > 0))

    return all(results), data


def test_cached_analysis(base: str) -> bool:
    print("\n── 4. POST /api/run-analysis?cached=true ──")
    results = []
    code, data = post(base, "/api/run-analysis?cached=true", timeout=10)
    results.append(check("Status 200", code == 200, f"got {code}"))
    results.append(check("Response is a list", isinstance(data, list),
                          f"got {type(data).__name__}"))
    if isinstance(data, list):
        results.append(check("Has events", len(data) > 0, f"{len(data)} events"))
    return all(results)


def test_ai_summary(base: str, event_id: int = 0) -> bool:
    print(f"\n── 5. GET /api/ai-summary/{event_id} ──")
    results = []
    code, data = get(base, f"/api/ai-summary/{event_id}", timeout=30)
    results.append(check("Status 200", code == 200, f"got {code}"))

    if not isinstance(data, dict):
        results.append(check("Response is a dict", False, str(data)[:80]))
        return all(results)

    results.append(check('Has "summary" key', "summary" in data))
    summary = data.get("summary", "")
    results.append(check("Summary is non-empty", bool(summary.strip()),
                          f"{len(summary)} chars"))
    results.append(check("Summary ≥ 30 chars", len(summary) >= 30))
    return all(results)


def test_cors_headers(base: str) -> bool:
    print("\n── 6. CORS headers ──")
    results = []
    try:
        r = requests.options(
            base + "/api/objects",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
            timeout=5,
        )
        acao = r.headers.get("Access-Control-Allow-Origin", "")
        results.append(check(
            "Access-Control-Allow-Origin present",
            bool(acao),
            f'value: "{acao}"',
        ))
    except requests.RequestException as e:
        results.append(check("CORS OPTIONS request succeeded", False, str(e)))
    return all(results)


def test_coord_utils() -> bool:
    """Test coord_utils independently (doesn't need the server)."""
    print("\n── 7. coord_utils.py unit checks ──")
    results = []
    try:
        import math
        from datetime import datetime, timezone

        from coord_utils import (
            eci_to_ecef,
            ecef_to_geodetic,
            eci_to_geodetic,
            geodetic_to_ecef,
            relative_velocity_kms,
        )

        dt = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)

        # ISS-like ECI
        x, y, z = 4200.0, -1100.0, 5100.0
        xe, ye, ze = eci_to_ecef(x, y, z, dt)
        results.append(check("eci_to_ecef runs", True))

        lat, lon, alt = ecef_to_geodetic(xe, ye, ze)
        results.append(check("lat in [-90, 90]", -90 <= lat <= 90, f"{lat:.2f}°"))
        results.append(check("lon in [-180,180]", -180 <= lon <= 180, f"{lon:.2f}°"))
        results.append(check("alt > 0 km", alt > 0, f"{alt:.1f} km"))

        # Round-trip
        x2, y2, z2 = geodetic_to_ecef(lat, lon, alt)
        err = math.sqrt((x2 - xe)**2 + (y2 - ye)**2 + (z2 - ze)**2)
        results.append(check("Round-trip error < 1 m", err < 0.001, f"{err*1000:.4f} m"))

        # One-shot
        lat2, lon2, _ = eci_to_geodetic(x, y, z, dt)
        results.append(check("eci_to_geodetic matches", abs(lat2 - lat) < 1e-6))

        # Relative velocity
        rv = relative_velocity_kms(7.5, 0, 0, -7.5, 0, 0)
        results.append(check("Head-on rel. velocity = 15 km/s", abs(rv - 15.0) < 1e-9))

    except ImportError as e:
        results.append(check("coord_utils import", False, str(e)))
    except Exception as e:
        results.append(check("coord_utils runtime", False, str(e)))

    return all(results)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AstroGuard integration tester")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="FastAPI server base URL")
    parser.add_argument("--skip-server", action="store_true",
                        help="Skip all server tests (only test local utilities)")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print("=" * 60)
    print("  AstroGuard — Integration Test Suite (Person C)")
    print(f"  Target: {base}")
    print("=" * 60)

    all_pass = True

    # Local unit tests (no server needed)
    all_pass &= test_coord_utils()

    if not args.skip_server:
        # Server must be running for the rest
        reachable = test_server_reachable(base)
        all_pass &= reachable

        if reachable:
            _, objects  = test_objects_endpoint(base)
            all_pass   &= bool(objects)

            ok, events  = test_run_analysis(base)
            all_pass   &= ok

            all_pass   &= test_cached_analysis(base)

            if events:
                all_pass &= test_ai_summary(base, event_id=events[0].get("id", 0))
            else:
                print("\n── 5. GET /api/ai-summary/<id> ── SKIPPED (no events)")

            all_pass &= test_cors_headers(base)
        else:
            print("\n  [!] Server not reachable — skipping server tests.")
            print("      Start with: uvicorn server:app --reload")

    print("\n" + "=" * 60)
    if all_pass:
        print(f"  {PASS} ALL CHECKS PASSED — ready to merge and record!")
    else:
        print(f"  {FAIL} SOME CHECKS FAILED — fix issues above before merging.")
    print("=" * 60)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
