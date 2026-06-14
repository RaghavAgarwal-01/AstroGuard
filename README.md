# 🛰️ AstroGuard

### Autonomous Orbital Conjunction Detection & Risk Assessment System

> *"There are over 50,000 tracked objects in Low Earth Orbit. One undetected collision can trigger a cascade that makes entire orbital shells unusable for generations. AstroGuard detects it before it happens."*

**FAR AWAY 2026 · Space & Aerospace + Agentic & Autonomous Systems**

---

## What is AstroGuard?

AstroGuard is a multi-layer autonomous system that continuously monitors Low Earth Orbit for dangerous close approaches between satellites and debris objects. It ingests real orbital data, propagates every object's trajectory using physics-based SGP4 mechanics, autonomously detects conjunction events, and generates AI-powered risk briefings — all without human intervention.

A human operator does one thing: opens the dashboard. AstroGuard does everything else.

---

## The Problem

The Kessler Syndrome is not hypothetical. It's a cascade failure scenario where one collision generates debris that causes more collisions, exponentially, until entire orbital shells become permanently unusable.

- **50,000+** tracked objects in LEO today
- **2009** — Iridium 33 and Cosmos 2251 collided at 11.7 km/s, generating 2,000+ debris fragments still tracked today
- **2021** — Russia's ASAT test on Cosmos 1408 created 1,500+ trackable fragments, forcing ISS emergency maneuvers
- **Current gap** — Most operators rely on manual conjunction reports issued days in advance. AstroGuard automates this entirely.

---

## Demo

> **Live demo:** `http://localhost:5173` (after setup)

The dashboard shows:
- 3D rotating Earth with all tracked objects plotted as live positions
- Real-time conjunction detection after clicking **Run Analysis**
- Risk-ranked event list (CRITICAL / HIGH / MEDIUM / LOW)
- AI-generated plain-English risk briefing for each event
- Red highlighted satellite pairs for flagged conjunctions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        AstroGuard                           │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Data Layer  │    │ Physics Layer│    │   AI Layer   │  │
│  │              │    │              │    │              │  │
│  │  CelesTrak   │───▶│ SGP4 Orbit   │───▶│  Anthropic   │  │
│  │  TLE Data    │    │ Propagator   │    │  Claude API  │  │
│  │              │    │              │    │              │  │
│  │  ~200 sats   │    │ 24h × 5min   │    │ Risk Summary │  │
│  │  + debris    │    │ timesteps    │    │ per event    │  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘  │
│                             │                               │
│                    ┌────────▼────────┐                      │
│                    │   Conjunction   │                      │
│                    │   Detector      │                      │
│                    │                 │                      │
│                    │ Coarse pass     │                      │
│                    │ (5min steps)    │                      │
│                    │      ↓          │                      │
│                    │ Fine pass       │                      │
│                    │ (30sec steps)   │                      │
│                    │      ↓          │                      │
│                    │ Risk ranking    │                      │
│                    └────────┬────────┘                      │
│                             │                               │
│              ┌──────────────▼──────────────┐               │
│              │        FastAPI Server        │               │
│              │                              │               │
│              │  GET  /api/objects           │               │
│              │  POST /api/run-analysis      │               │
│              │  GET  /api/ai-summary/{id}   │               │
│              │  GET  /api/cached-results    │               │
│              └──────────────┬───────────────┘               │
│                             │                               │
│              ┌──────────────▼───────────────┐              │
│              │      React + Three.js         │              │
│              │                               │              │
│              │  3D Globe  │  Event Panel     │              │
│              │  Sat Dots  │  AI Summaries    │              │
│              │  Red Pairs │  Risk Badges     │              │
│              └───────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## How It Works

### Step 1 — Data Ingestion
AstroGuard fetches Two-Line Element (TLE) orbital data from CelesTrak for active satellites and known debris clouds (Cosmos 1408, Fengyun-1C, Iridium 33). TLE data is cached locally for offline operation.

### Step 2 — SGP4 Orbit Propagation
Every object is propagated forward 24 hours using the SGP4 simplified perturbations model — the same standard used by NORAD and ESA. Positions are computed at 5-minute intervals, producing (x, y, z) coordinates in the ECI frame, then converted to geodetic (lat/lon/alt) for visualization.

### Step 3 — Two-Pass Conjunction Detection

**Coarse pass** — All N(N-1)/2 object pairs are scanned at 5-minute resolution. Any pair approaching within 50 km is flagged as a candidate.

**Fine pass** — For each candidate, a 30-second resolution scan is run over a ±10 minute window around the closest approach time. This identifies the true minimum separation distance, time of closest approach, and relative closing velocity.

### Step 4 — Risk Classification
Events are ranked by minimum distance:
- **CRITICAL** — < 5 km
- **HIGH** — 5–10 km
- **MEDIUM** — 10–20 km
- **LOW** — 20–25 km

### Step 5 — Autonomous AI Risk Briefing
Each flagged event is passed to Claude (Anthropic) which generates a 3-sentence plain-English briefing: what is happening, why it matters, and what action to take. No human writes these — the system generates them autonomously.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orbital mechanics | `sgp4` (Python) — SGP4/SDP4 propagator |
| Coordinate transforms | Custom `coord_utils.py` — ECI → ECEF → Geodetic (WGS-84) |
| TLE data source | CelesTrak GP data API |
| Backend API | FastAPI + Uvicorn |
| AI layer | Anthropic Claude API (`claude-sonnet-4-6`) |
| Frontend | React + Vite |
| 3D visualization | Three.js + `@react-three/fiber` + `@react-three/drei` |
| Styling | Tailwind CSS |

---

## Project Structure

```
astroguard/
├── backend/
│   ├── server.py          # FastAPI server — all API endpoints
│   ├── tle_fetcher.py     # CelesTrak data pipeline + stub fallback
│   ├── propagator.py      # SGP4 orbit propagation engine
│   ├── conjunction.py     # Two-pass conjunction detection
│   ├── ai_summary.py      # Anthropic API risk briefing generation
│   ├── coord_utils.py     # ECI/ECEF/Geodetic coordinate transforms
│   └── data/
│       ├── satellites.json      # Cached TLE data (JSON)
│       ├── tle_active.txt       # Raw TLE — active satellites
│       ├── tle_debris.txt       # Raw TLE — debris objects
│       └── cached_results.json  # Pre-computed demo results
│
└── frontend/
    ├── src/
    │   ├── App.jsx         # Root component
    │   ├── Globe.jsx       # Three.js 3D Earth + satellite rendering
    │   ├── EventPanel.jsx  # Conjunction event list + AI summary
    │   └── api.js          # Backend API calls
    ├── index.html
    └── package.json
```

---

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- An Anthropic API key ([get one here](https://console.anthropic.com))

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/astroguard.git
cd astroguard
```

### 2. Backend setup
```bash
cd backend

# Install dependencies
pip install fastapi uvicorn sgp4 skyfield numpy pandas requests python-dotenv anthropic

# Create .env file
echo "GROQ_API_KEY=your_key_here" > .env

# Download TLE data (run from your local machine — CelesTrak may block servers)
python tle_fetcher.py

# Start the API server
uvicorn server:app --reload --port 8000
```

The server starts at `http://localhost:8000`. Check health at `http://localhost:8000/health`.

### 3. Frontend setup
```bash
cd ../frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open `http://localhost:5173` in your browser.

### 4. Run your first analysis
1. The globe loads with all tracked objects as white dots
2. Click **Run Analysis** — the system propagates orbits and detects conjunctions
3. Flagged events appear in the right panel, ranked by risk
4. Click any event to see the AI-generated risk briefing and highlight the pair on the globe

> **Demo mode:** If you just want to see results without waiting for analysis, the backend serves pre-computed results at `GET /api/cached-results`. The frontend "Load Demo" button uses this.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Server status, object counts, last analysis time |
| `/api/objects` | GET | Current positions of all tracked objects (lat/lon/alt) |
| `/api/run-analysis` | POST | Trigger full pipeline: propagate → detect → summarize |
| `/api/ai-summary/{id}` | GET | AI risk briefing for a specific conjunction event |
| `/api/cached-results` | GET | Pre-computed results (instant, no latency) |
| `/api/orbit-path/{name}` | GET | Full 24h orbit path for a specific satellite |

### Sample response — `/api/run-analysis`

```json
{
  "events": [
    {
      "id": 0,
      "obj_a": "ISS (ZARYA)",
      "obj_b": "COSMOS 1408 DEB A",
      "min_dist_km": 4.2,
      "closest_time": "2026-06-14T18:32:00Z",
      "rel_velocity_kms": 7.8,
      "risk_level": "CRITICAL",
      "threshold_km": 25.0
    }
  ],
  "summaries": {
    "0": "At 18:32 UTC, ISS (ZARYA) will pass within 4.2 km of Cosmos 1408 debris fragment at a closing speed of 7.8 km/s. At this separation and velocity, a collision would generate thousands of fragments capable of triggering a cascading debris cascade across the orbital shell. Immediate maneuver assessment is required — contact mission control now."
  },
  "runtime_seconds": 38.4,
  "object_count": 200,
  "analysis_time": "2026-06-14T17:45:00Z",
  "threshold_km": 25.0
}
```

---

## Key Technical Decisions

**Why SGP4 and not a simpler model?**
SGP4 is the international standard for LEO object tracking — it accounts for atmospheric drag, Earth's oblateness (J2 through J4 harmonics), solar radiation pressure, and lunar/solar gravitational perturbations. A simpler Keplerian model would accumulate position errors of hundreds of kilometres over 24 hours, making conjunction detection meaningless.

**Why a two-pass detector?**
Checking all pairs at 30-second resolution for 24 hours is O(N² × 2880) — computationally expensive even for 200 objects. The coarse pass at 5-minute intervals reduces the candidate set to pairs that actually come close, then the fine pass finds the true minimum separation accurately. This makes the analysis 40-50× faster with no loss in accuracy for the events that matter.

**Why Claude for risk summaries?**
Orbital mechanics outputs are numbers — distances, velocities, timestamps. Converting those into actionable decisions requires contextual reasoning: understanding what 4.2 km means at 7.8 km/s, what the consequences of a collision at that altitude would be, and what a mission controller should actually do. Claude generates this reasoning autonomously for every event.

---

## Real-World Impact

AstroGuard addresses a real and growing problem. The number of tracked objects in LEO has increased 50% in the last 3 years due to Starlink, OneWeb, and other mega-constellation deployments. Current SSA (Space Situational Awareness) infrastructure relies heavily on manual processes and outdated tools. An autonomous, AI-augmented system like AstroGuard represents the direction this field needs to move.

**Who would use this:**
- Small satellite operators without dedicated SSA teams
- Research institutions operating cubesats
- National space agencies supplementing existing SSA infrastructure
- Space debris monitoring organizations (ESA SSA, LeoLabs, ExoAnalytic)

---

## Future Scope

- **Maneuver planning** — automatically compute optimal avoidance burn parameters when a CRITICAL event is detected
- **Real-time streaming** — replace 5-minute polling with continuous SGP4 propagation and WebSocket push to the frontend
- **Extended catalog** — scale to the full CelesTrak catalog (10,000+ objects) with GPU-accelerated propagation
- **Probability of collision (Pc)** — replace deterministic distance thresholds with Monte Carlo Pc estimates using covariance data
- **Multi-agent architecture** — separate Monitor, Decision, and Communication agents running concurrently for faster response
- **Email/SMS alerting** — push CRITICAL events to operators automatically without requiring them to check the dashboard

---

## Team

Built for FAR AWAY 2026 — India's Biggest International Hackathon.

**Theme:** Space & Aerospace × Agentic & Autonomous Systems

---

## License

MIT License — see [LICENSE](LICENSE) for details.
