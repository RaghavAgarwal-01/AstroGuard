"""
tle_fetcher.py
Downloads and caches TLE orbital data from CelesTrak.

Run once before starting the server:
    python tle_fetcher.py

Outputs:
    data/satellites.json   — combined active + debris as JSON list
    data/tle_active.txt    — raw TLE text for active satellites
    data/tle_debris.txt    — raw TLE text for debris objects

Note: CelesTrak rate-limits automated servers. If you see 403 errors,
run this from your local machine — it will work fine there.
"""

import json
import os
import time
import requests
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

MAX_ACTIVE = 150   # Keep demo fast — enough for real conjunctions
MAX_DEBRIS = 50    # Supplement with known high-risk debris clouds

# Browser-like headers — avoids most bot blocks
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept":  "text/plain, */*",
    "Referer": "https://celestrak.org/",
}

# CelesTrak GP endpoint — most reliable, returns clean 3-line TLE format
# Ordered by reliability (most stable first, fallbacks after)
ACTIVE_URLS = [
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
]

# Debris sources — ordered by scientific interest (most impactful first)
DEBRIS_URLS = [
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=cosmos-1408-debris&FORMAT=tle",   # 2021 ASAT test
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=fengyun-1c-debris&FORMAT=tle",    # 2007 ASAT test
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-33-debris&FORMAT=tle",    # 2009 collision
]


# ── Core helpers ──────────────────────────────────────────────────────────────

def fetch_tle_text(url: str, label: str, timeout: int = 20) -> str:
    """
    Download raw TLE text from a CelesTrak URL.
    Returns raw text on success, empty string on failure.
    """
    print(f"  [fetch] {label} ← {url}")
    try:
        resp = requests.get(url, timeout=timeout, headers=HEADERS)
        resp.raise_for_status()
        text = resp.text.strip()
        lines = len(text.splitlines())
        print(f"  [fetch] ✓ {label}: {lines} lines ({lines // 3} objects)")
        return text
    except requests.RequestException as e:
        print(f"  [fetch] ✗ {label}: {e}")
        return ""


def fetch_with_fallback(urls: list[str], label: str) -> str:
    """
    Try each URL in order, return first successful response.
    Adds a polite 1-second delay between attempts.
    """
    for i, url in enumerate(urls):
        text = fetch_tle_text(url, f"{label} (attempt {i+1})")
        if text and len(text.splitlines()) >= 3:
            return text
        if i < len(urls) - 1:
            time.sleep(1)
    return ""


def parse_tle_text(raw_text: str) -> list[dict]:
    """
    Parse a block of 3-line TLE text into a list of dicts.
    Each dict: {"name": str, "line1": str, "line2": str}
    Silently skips malformed triplets.
    """
    satellites = []
    lines = [ln.rstrip() for ln in raw_text.splitlines() if ln.strip()]
    i = 0
    while i + 2 < len(lines):
        name  = lines[i].strip()
        line1 = lines[i + 1].strip()
        line2 = lines[i + 2].strip()
        if line1.startswith("1 ") and line2.startswith("2 "):
            satellites.append({"name": name, "line1": line1, "line2": line2})
            i += 3
        else:
            i += 1   # skip malformed line, try to resync
    return satellites


def save_tle_text(satellites: list[dict], filename: str) -> None:
    """Save satellite list back to raw 3-line TLE text format."""
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        for s in satellites:
            f.write(f"{s['name']}\n{s['line1']}\n{s['line2']}\n")
    print(f"  [save] ✓ {filename}  ({len(satellites)} objects)")


def save_json(data: list[dict], filename: str) -> None:
    """Save satellite list as JSON."""
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  [save] ✓ {filename}  ({len(data)} records)")


# ── Stub data ─────────────────────────────────────────────────────────────────

def get_stub_data() -> tuple[list[dict], list[dict]]:
    """
    Comprehensive hardcoded TLE fallback — used when CelesTrak is unreachable.
    Covers ISS, Hubble, Starlink cluster, Tiangong, major debris clouds.
    Enough objects to produce real conjunction events for the demo.
    """
    active = parse_tle_text("""\
ISS (ZARYA)
1 25544U 98067A   24001.50000000  .00020137  00000-0  36336-3 0  9990
2 25544  51.6406  78.6043 0001899 323.6994  36.4163 15.49999786429637
HUBBLE SPACE TELESCOPE
1 20580U 90037B   24001.50000000  .00000760  00000-0  34258-4 0  9990
2 20580  28.4698 240.8024 0002545 285.3050  74.7694 15.09350456344748
TIANGONG
1 48274U 21035A   24001.50000000  .00015600  00000-0  95432-3 0  9998
2 48274  41.4700 310.5670 0006780  56.7890 303.3450 15.60123456789012
TERRA
1 25994U 99068A   24001.50000000  .00000038  00000-0  23291-4 0  9993
2 25994  98.2110  48.8432 0001401  86.1823 274.0000 14.57114959287033
AQUA
1 27424U 02022A   24001.50000000  .00000073  00000-0  35180-4 0  9992
2 27424  98.2182 236.6161 0001428  94.6694 265.4633 14.57114959287034
NOAA 15
1 25338U 98030A   24001.50000000  .00000117  00000-0  15432-4 0  9998
2 25338  98.7200 310.4560 0011230  56.7890 303.4560 14.25678901234567
NOAA 18
1 28654U 05018A   24001.50000000  .00000098  00000-0  13210-4 0  9995
2 28654  98.8900 350.1230 0013450  45.6780 314.5670 14.10123456789012
SENTINEL-1A
1 39634U 14016A   24001.50000000  .00000067  00000-0  98765-5 0  9997
2 39634  98.1800 295.6780 0001123  90.1230 270.0120 14.59876543210987
SENTINEL-2A
1 40697U 15028A   24001.50000000  .00000078  00000-0  11234-4 0  9996
2 40697  98.5700 270.4560 0001345 100.5670 259.5670 14.30987654321098
LANDSAT 8
1 39084U 13008A   24001.50000000  .00000089  00000-0  12987-4 0  9994
2 39084  98.2200 272.3450 0001234 100.5670 259.5670 14.57654321098765
STARLINK-1007
1 44713U 19074A   24001.50000000  .00002719  00000-0  18509-3 0  9990
2 44713  53.0537 238.9414 0001390 103.6455 256.4822 15.06386979228456
STARLINK-1008
1 44714U 19074B   24001.50000000  .00002700  00000-0  18400-3 0  9990
2 44714  53.0537 240.4414 0001380 104.6455 255.4822 15.06390000228456
STARLINK-1009
1 44715U 19074C   24001.50000000  .00002680  00000-0  18300-3 0  9990
2 44715  53.0537 241.9414 0001370 105.6455 254.4822 15.06393000228456
STARLINK-2030
1 47529U 21012AK  24001.50000000  .00002340  00000-0  16234-3 0  9998
2 47529  53.0500  50.1230 0001210  95.0120 265.1230 15.06234567890123
STARLINK-2031
1 47530U 21012AL  24001.50000000  .00002320  00000-0  16123-3 0  9997
2 47530  53.0500  51.6780 0001200  96.0120 264.1230 15.06245678901234
""")

    debris = parse_tle_text("""\
COSMOS 1408 DEB A
1 49271U 71105RR  24001.50000000  .00001234  00000-0  10000-3 0  9991
2 49271  82.5500  98.4560 0023450  45.6780 314.5670 14.98765432109876
COSMOS 1408 DEB B
1 49358U 71105SF  24001.50000000  .00001189  00000-0  16234-3 0  9993
2 49358  82.5600  99.1230 0024560  46.7890 313.4560 14.97654321098765
COSMOS 1408 DEB C
1 49445U 71105UA  24001.50000000  .00001145  00000-0  15678-3 0  9992
2 49445  82.5400  97.7890 0022340  44.5670 315.6780 14.96543210987654
FENGYUN 1C DEB A
1 29228U 99025AGK 24001.50000000  .00000134  00000-0  19876-4 0  9991
2 29228  98.6500 210.5670 0023450  67.8900 292.3450 14.21234567890123
FENGYUN 1C DEB B
1 29456U 99025BCK 24001.50000000  .00000125  00000-0  18543-4 0  9993
2 29456  98.6600 211.8900 0022340  68.9010 291.2340 14.20123456789012
IRIDIUM 33 DEB A
1 33442U 97051CE  24001.50000000  .00000289  00000-0  41234-4 0  9992
2 33442  86.4000  80.1230 0098760  12.3450 347.7890 14.38901234567890
IRIDIUM 33 DEB B
1 33521U 97051DL  24001.50000000  .00000278  00000-0  39876-4 0  9994
2 33521  86.4100  81.4560 0097650  13.4560 346.6780 14.37890123456789
COSMOS 2251 DEB A
1 33753U 93036SX  24001.50000000  .00000321  00000-0  45678-4 0  9994
2 33753  74.0500 120.4560 0143210  45.6780 315.6780 14.34567890123456
COSMOS 2251 DEB B
1 33795U 93036TL  24001.50000000  .00000312  00000-0  44321-4 0  9995
2 33795  74.0600 121.7890 0142100  46.7890 314.5670 14.33456789012345
""")

    return active, debris


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run():
    print("\n" + "=" * 60)
    print("  AstroGuard — TLE Fetcher")
    print("=" * 60 + "\n")

    # ── Step 1: Active satellites ──────────────────────────────────
    print("[1/2] Fetching active satellites...")
    active_raw = fetch_with_fallback(ACTIVE_URLS, "active")
    time.sleep(1)   # polite delay between requests

    # ── Step 2: Debris ────────────────────────────────────────────
    print("\n[2/2] Fetching debris objects...")
    debris_raw = fetch_with_fallback(DEBRIS_URLS, "debris")

    # ── Step 3: Parse or fall back to stubs ───────────────────────
    if active_raw and len(active_raw.splitlines()) >= 3:
        active_sats = parse_tle_text(active_raw)[:MAX_ACTIVE]
        print(f"\n  Parsed {len(active_sats)} active satellites from live data")
    else:
        print("\n  Live fetch failed — using embedded stub data")
        active_sats, _ = get_stub_data()

    if debris_raw and len(debris_raw.splitlines()) >= 3:
        debris_sats = parse_tle_text(debris_raw)[:MAX_DEBRIS]
        print(f"  Parsed {len(debris_sats)} debris objects from live data")
    else:
        _, debris_sats = get_stub_data()
        print(f"  Using {len(debris_sats)} embedded debris objects")

    # Deduplicate by name (in case of overlap between groups)
    seen: set[str] = set()
    all_sats: list[dict] = []
    for s in active_sats + debris_sats:
        if s["name"] not in seen:
            seen.add(s["name"])
            all_sats.append(s)

    # ── Step 4: Save ──────────────────────────────────────────────
    print(f"\nSaving {len(all_sats)} total objects...")
    save_tle_text(active_sats, "tle_active.txt")
    save_tle_text(debris_sats, "tle_debris.txt")
    save_json(all_sats, "satellites.json")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  Done. Total objects saved: {len(all_sats)}")
    print(f"  Files in {DATA_DIR}/:")
    for f in sorted(DATA_DIR.iterdir()):
        size_kb = f.stat().st_size // 1024
        print(f"    {f.name:<30}  {size_kb:>5} KB")
    print(f"{'=' * 60}\n")
    print("You can now run: uvicorn server:app --reload")


if __name__ == "__main__":
    run()
