

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
load_dotenv(Path(__file__).parent / ".env")

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are AstroGuard, an orbital safety AI assistant.
Your job is to translate raw satellite conjunction data into clear, human-readable risk briefings for satellite operators.

Always respond with a JSON object in exactly this format:
{
  "summary": "2-sentence plain-English description of the risk event, what objects are involved, and when it occurs.",
  "recommendation": "one of: MONITOR | ALERT | REVIEW_MANEUVER",
  "explanation": "1 sentence explaining why you chose that recommendation."
}

Base your recommendation on:
- MONITOR: distance > 15 km, low urgency
- ALERT: distance 5–15 km, warrants attention
- REVIEW_MANEUVER: distance < 5 km, serious risk requiring maneuver assessment

Be factual, concise, and non-alarmist. Use UTC times. Do not invent data beyond what you're given."""


def generate_risk_summary(event: dict) -> dict:
    """
    Generate an AI risk summary for a single conjunction event.

    Args:
        event: {
            "id": int,
            "obj_a": str,
            "obj_b": str,
            "min_dist_km": float,
            "closest_time": str,
            "rel_velocity_kms": float,
            "risk_level": str
        }

    Returns:
        {
            "event_id": int,
            "summary": str,
            "recommendation": str,
            "explanation": str
        }
    """
    user_prompt = f"""Conjunction event data:
{json.dumps(event, indent=2)}

Generate a risk briefing for this event."""

    try:
        message = client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
        )

        raw = message.choices[0].message.content.strip()

        # Parse JSON response
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        result["event_id"] = event.get("id", 0)
        return result

    except json.JSONDecodeError:
        # If JSON parsing fails, return a structured fallback
        return _fallback_summary(event)
    except Exception as e:
        print(f"  Groq API error: {e}")
        return _fallback_summary(event)


def generate_bulk_summaries(events: list[dict], max_events: int = 10) -> dict[int, dict]:
    """
    Generate summaries for multiple events.
    Limits to top max_events by risk (closest distance) to avoid API overuse.

    Returns: {event_id: summary_dict}
    """
    # Sort by distance, take the most critical ones
    top_events = sorted(events, key=lambda e: e["min_dist_km"])[:max_events]

    summaries = {}
    for event in top_events:
        print(f"  Generating AI summary for event {event['id']}: {event['obj_a']} ↔ {event['obj_b']}...")
        summaries[event["id"]] = generate_risk_summary(event)

    return summaries


def _fallback_summary(event: dict) -> dict:
   
    dist = event.get("min_dist_km", 0)
    obj_a = event.get("obj_a", "Object A")
    obj_b = event.get("obj_b", "Object B")
    time = event.get("closest_time", "unknown time")
    vel = event.get("rel_velocity_kms", 0)

    if dist < 5:
        rec = "REVIEW_MANEUVER"
        summary = (
            f"At {time} UTC, {obj_a} will pass within {dist:.1f} km of {obj_b} "
            f"at a closing speed of {vel:.1f} km/s — a critical proximity event. "
            f"This distance is below the standard 5 km safety threshold and warrants immediate maneuver review."
        )
        explanation = "Distance below 5 km critical threshold."
    elif dist < 15:
        rec = "ALERT"
        summary = (
            f"At {time} UTC, {obj_a} is predicted to approach {obj_b} within {dist:.1f} km "
            f"at {vel:.1f} km/s relative velocity. "
            f"This conjunction warrants monitoring and potential notification to object operators."
        )
        explanation = "Distance between 5–15 km requires active monitoring."
    else:
        rec = "MONITOR"
        summary = (
            f"At {time} UTC, {obj_a} and {obj_b} will pass within {dist:.1f} km of each other "
            f"at {vel:.1f} km/s. "
            f"While within the flagging threshold, current distance does not indicate immediate risk."
        )
        explanation = "Distance above 15 km, standard monitoring recommended."

    return {
        "event_id": event.get("id", 0),
        "summary": summary,
        "recommendation": rec,
        "explanation": explanation,
    }


if __name__ == "__main__":
    # Test with a fake event
    test_event = {
        "id": 0,
        "obj_a": "ISS (ZARYA)",
        "obj_b": "FENGYUN 1C DEB",
        "min_dist_km": 4.2,
        "closest_time": "2026-06-14T18:32:00Z",
        "rel_velocity_kms": 7.1,
        "risk_level": "critical",
    }
    print("=== AI Summary Test ===\n")
    print(f"Event: {test_event['obj_a']} ↔ {test_event['obj_b']}, {test_event['min_dist_km']} km\n")
    result = generate_risk_summary(test_event)
    print(json.dumps(result, indent=2))
