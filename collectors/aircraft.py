"""Air-ambulance helicopters in flight, from adsb.lol (ODbL, credit required).

Only helicopters on the FAA-derived air-ambulance list are kept. To avoid
pointing at an emergency scene, positions are rounded to about 1 km and an
aircraft is dropped once it is below 1,000 ft (landing or on the ground).
Tail numbers are not published.
"""
import json
from pathlib import Path

from collectors.common import get_json

HEMS = set(json.loads((Path(__file__).parent / "hems.json").read_text()))
# ICAO type codes common in US air-medical fleets.
TYPES = ["EC35", "EC45", "B407", "B429", "AS50", "AS65", "A109", "A119", "A169", "A139", "S76", "BK17", "EC30", "B412", "EC55"]
MIN_ALT_FT = 1000


def helicopters(now):
    seen = {}
    for t in TYPES:
        for a in get_json(f"https://api.adsb.lol/v2/type/{t}").get("ac", []):
            if a.get("hex", "").lower() not in HEMS or "lat" not in a:
                continue
            alt = a.get("alt_baro")
            if not isinstance(alt, (int, float)) or alt < MIN_ALT_FT:
                continue
            seen[a["hex"]] = {
                "lat": round(a["lat"], 2),
                "lon": round(a["lon"], 2),
                "alt": int(round(alt, -2)),
                "track": int(a.get("track") or 0),
                "type": t,
            }
    return list(seen.values())
