"""
server.py — AstroGuard FastAPI backend.

Endpoints (matching the team contract):
  GET  /api/objects              → all satellite current positions
  POST /api/run-analysis         → run full pipeline, return conjunction events
  GET  /api/ai-summary/{event_id} → AI risk briefing for a specific event

Run with:
  uvicorn server:app --reload --port 8000
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Local modules
from propagator import propagate_all, get_current_positions, load_all_satellites
from conjunction import detect_conjunctions
from ai_summary import generate_risk_summary, _fallback_summary

# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AstroGuard API",
    description="AI-assisted satellite collision risk prediction",
    version="1.0.0",
)

# CORS — allow P2's frontend (React dev server on :5173) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "sample_results.json"

# In-memory cache so /api/ai-summary can look up events from the last analysis run
_last_events: list[dict] = []
_last_positions: list[dict] = []


# ─── Startup: pre-load cached results if available ────────────────────────────

@app.on_event("startup")
async def startup_event():
    global _last_events, _last_positions
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
            _last_events = cache.get("events", [])
            _last_positions = cache.get("objects", [])
            print(f"✓ Loaded cached results: {len(_last_events)} events, {len(_last_positions)} objects")
        except Exception as e:
            print(f"  Could not load cache: {e}")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "AstroGuard API is running", "version": "1.0.0", "time": datetime.now(tz=timezone.utc).isoformat()}


@app.get("/api/objects")
def get_objects(cached: bool = Query(False, description="Return cached positions if true")):
    """
    Returns current positions of all tracked satellites.

    Response shape (matches P2 contract):
    [{"name": str, "lat": float, "lon": float, "alt_km": float}, ...]
    """
    global _last_positions

    if cached and _last_positions:
        return JSONResponse(content=_last_positions)

    try:
        satellites = load_all_satellites()
        # Quick single-step propagation for current positions
        positions = get_current_positions(propagate_all(satellites, timestep_minutes=5, hours=1))
        _last_positions = positions
        return JSONResponse(content=positions)
    except Exception as e:
        if _last_positions:
            return JSONResponse(content=_last_positions)
        raise HTTPException(status_code=500, detail=f"Propagation failed: {str(e)}")


@app.post("/api/run-analysis")
def run_analysis(cached: bool = Query(False, description="Return pre-computed demo results")):
    """
    Runs the full pipeline: TLE load → propagation → conjunction detection.

    Response shape (matches P2 contract):
    [
      {
        "id": int,
        "obj_a": str,
        "obj_b": str,
        "min_dist_km": float,
        "closest_time": str,   # ISO-8601 UTC
        "rel_velocity_kms": float,
        "risk_level": str      # "critical" | "high" | "medium"
      }, ...
    ]
    """
    global _last_events, _last_positions

    # Serve cached results for demo safety net
    if cached:
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                cache = json.load(f)
            _last_events = cache.get("events", [])
            _last_positions = cache.get("objects", [])
            return JSONResponse(content={
                "events": _last_events,
                "objects": _last_positions,
                "cached": True,
                "analysis_time_s": 0,
            })
        elif _last_events:
            return JSONResponse(content={"events": _last_events, "cached": True})

    try:
        t_start = time.time()

        print("\n[Analysis] Loading satellites...")
        satellites = load_all_satellites()

        print("[Analysis] Propagating orbits (24 hours, 5-min steps)...")
        propagation = propagate_all(satellites, timestep_minutes=5, hours=24)

        print("[Analysis] Extracting current positions...")
        _last_positions = get_current_positions(propagation)

        print("[Analysis] Detecting conjunctions...")
        events = detect_conjunctions(propagation, threshold_km=200.0)

# ADD THESE 3 LINES:
        if len(events) == 0:
            print("[Analysis] No events at 200km, widening to 500km...")
            events = detect_conjunctions(propagation, threshold_km=500.0)


        _last_events = events

        elapsed = round(time.time() - t_start, 2)
        print(f"[Analysis] ✓ Done in {elapsed}s. Found {len(events)} conjunction events.")

        # Auto-save as cache
        _save_cache(events, _last_positions)

        return JSONResponse(content={
            "events": events,
            "objects": _last_positions,
            "cached": False,
            "analysis_time_s": elapsed,
            "total_objects": len(satellites),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Return cached if available
        if _last_events:
            return JSONResponse(content={"events": _last_events, "error": str(e), "cached": True})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/ai-summary/{event_id}")
def get_ai_summary(event_id: int):
    """
    Returns an AI-generated risk briefing for a specific conjunction event.

    Response shape (matches P2 contract):
    {
      "event_id": int,
      "summary": str,
      "recommendation": str,    # "MONITOR" | "ALERT" | "REVIEW_MANEUVER"
      "explanation": str
    }
    """
    global _last_events

    # Find the event
    event = next((e for e in _last_events if e["id"] == event_id), None)

    if event is None:
        # Try loading from cache
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                cache = json.load(f)
            _last_events = cache.get("events", [])
            event = next((e for e in _last_events if e["id"] == event_id), None)

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Event {event_id} not found. Run /api/run-analysis first."
        )

    summary = generate_risk_summary(event)
    return JSONResponse(content=summary)


# ─── Health + debug endpoints ─────────────────────────────────────────────────

@app.get("/api/health")
def health():
    """Quick health check — useful for P2 to verify server is up."""
    return {
        "status": "ok",
        "cached_events": len(_last_events),
        "cached_objects": len(_last_positions),
        "cache_file": str(CACHE_FILE),
        "cache_exists": CACHE_FILE.exists(),
        "groq_key_set": bool(os.environ.get("GROQ_API_KEY")),
    }


@app.get("/api/events")
def list_events():
    """List all events from the last analysis run (useful for P2 debugging)."""
    return JSONResponse(content=_last_events)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _save_cache(events: list[dict], objects: list[dict]):
    """Save pipeline results to disk for the demo safety net."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({"events": events, "objects": objects, "saved_at": datetime.now(tz=timezone.utc).isoformat()}, f, indent=2)
        print(f"  ✓ Cache saved → {CACHE_FILE}")
    except Exception as e:
        print(f"  ✗ Cache save failed: {e}")


# ─── Run directly ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
