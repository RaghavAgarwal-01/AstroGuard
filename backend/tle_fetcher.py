"""
tle_fetcher.py — Download and cache TLE data from CelesTrak.
Run this standalone first: python tle_fetcher.py
Saves data/tle_active.txt and data/tle_debris.txt
"""

import os
import requests
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# CelesTrak GP data API (returns TLE text) — most reliable endpoints
ACTIVE_URL = "https://celestrak.org/SOCRATES/query.php?OBJECT_NAME=ISS&LIMIT=25&DAYS=7&MAX_RISK_INTERVAL=4&FORMAT=tle"
# Fallback: use the well-known TLE groups
ACTIVE_GROUPS = [
    "https://celestrak.org/SOCRATES/query.php?FORMAT=tle",  # SOCRATES conjunction candidates
]

# Reliable active satellites endpoint (100 ISS + Starlink + weather)
RELIABLE_ACTIVE_URL = "https://celestrak.org/SOCRATES/query.php?OBJECT_NAME=ISS&LIMIT=30&FORMAT=tle"

# Best endpoints for our use case
TLE_SOURCES = {
    "active": "https://celestrak.org/pub/TLE/catalog.txt",        # Full catalog ~10k objects
    "stations": "https://celestrak.org/SOCRATES/query.php?FORMAT=tle",
    "visual": "https://celestrak.org/pub/TLE/visual.txt",          # ~150 brightest, great for demo
    "iss": "https://celestrak.org/SOCRATES/query.php?OBJECT_NAME=ISS&FORMAT=tle",
}

# We'll use these two for a good demo set (fast, ~200 objects total)
ACTIVE_DEMO_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
DEBRIS_DEMO_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=fengyun-1c-debris&FORMAT=tle"  # Fengyun-1C debris ~400 objects

def fetch_tle_text(url: str, timeout: int = 15) -> str | None:
    try:
        print(f"  Fetching: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/plain, */*",
            "Referer": "https://celestrak.org/",
        }
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return None


def parse_tle_text(raw_text: str) -> list[dict]:
    """
    Parse raw 3-line TLE text into structured dicts.
    Each TLE block is:
        Line 0: Object name
        Line 1: TLE line 1
        Line 2: TLE line 2
    Returns list of {"name": str, "line1": str, "line2": str}
    """
    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    satellites = []
    i = 0
    while i < len(lines) - 2:
        name_line = lines[i]
        line1 = lines[i + 1]
        line2 = lines[i + 2]
        # TLE lines start with '1 ' and '2 ' respectively
        if line1.startswith("1 ") and line2.startswith("2 "):
            satellites.append({
                "name": name_line.strip(),
                "line1": line1.strip(),
                "line2": line2.strip(),
            })
            i += 3
        else:
            i += 1  # skip malformed line
    return satellites


def save_tle_text(satellites: list[dict], filepath: Path) -> None:
    """Save satellites back as raw TLE text (3 lines per object)."""
    with open(filepath, "w") as f:
        for sat in satellites:
            f.write(f"{sat['name']}\n{sat['line1']}\n{sat['line2']}\n")
    print(f"  ✓ Saved {len(satellites)} objects → {filepath}")


def save_tle_json(satellites: list[dict], filepath: Path) -> None:
    """Save as JSON for easy loading in propagator."""
    with open(filepath, "w") as f:
        json.dump(satellites, f, indent=2)
    print(f"  ✓ Saved JSON → {filepath}")


def fetch_all():
    """Main function: download and save TLE data."""
    print("\n=== AstroGuard TLE Fetcher ===\n")

    # --- Active satellites ---
    print("[1/2] Fetching active satellites (visual + bright objects)...")
    active_raw = fetch_tle_text(ACTIVE_DEMO_URL)

    if not active_raw:
        print("  Primary URL failed, trying fallback...")
        active_raw = fetch_tle_text("https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle")

    if active_raw:
        active_sats = parse_tle_text(active_raw)
        # Limit to 150 for demo speed
        active_sats = active_sats[:150]
        save_tle_text(active_sats, DATA_DIR / "tle_active.txt")
        save_tle_json(active_sats, DATA_DIR / "satellites.json")
    else:
        print("  ✗ Could not fetch active TLEs. Using stub data.")
        active_sats = _stub_active_sats()
        save_tle_text(active_sats, DATA_DIR / "tle_active.txt")
        save_tle_json(active_sats, DATA_DIR / "satellites.json")

    # --- Debris ---
    print("\n[2/2] Fetching debris objects (Fengyun-1C cloud)...")
    debris_raw = fetch_tle_text(DEBRIS_DEMO_URL)

    if not debris_raw:
        debris_raw = fetch_tle_text("https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-33-debris&FORMAT=tle")

    if debris_raw:
        debris_sats = parse_tle_text(debris_raw)
        # Limit to 50 debris for demo
        debris_sats = debris_sats[:50]
        save_tle_text(debris_sats, DATA_DIR / "tle_debris.txt")
        save_tle_json(debris_sats, DATA_DIR / "debris.json")
    else:
        print("  ✗ Could not fetch debris TLEs. Using stub data.")
        debris_sats = []
        save_tle_json(debris_sats, DATA_DIR / "debris.json")

    total = len(active_sats) + (len(debris_sats) if debris_raw else 0)
    print(f"\n✓ Done. Total objects cached: {total}")
    print(f"  Files in {DATA_DIR}:")
    for f in DATA_DIR.iterdir():
        print(f"    {f.name} ({f.stat().st_size // 1024} KB)")


def _stub_active_sats() -> list[dict]:
    """Fallback: hardcoded 5 real TLEs for offline testing."""
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
            "name": "STARLINK-1007",
            "line1": "1 44713U 19074A   24001.50000000  .00002719  00000-0  18509-3 0  9990",
            "line2": "2 44713  53.0537 238.9414 0001390 103.6455 256.4822 15.06386979228456",
        },
    ]


if __name__ == "__main__":
    fetch_all()
