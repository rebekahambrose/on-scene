"""Air-ambulance helicopters in flight, from adsb.lol (ODbL, credit required).

Only helicopters on the FAA-derived air-ambulance list are kept. To avoid
pointing at an emergency scene, positions are rounded to about 1 km and an
aircraft is dropped once it is below 1,000 ft (landing or on the ground).
Tail numbers are not published.

adsb.lol allows 500 requests a day per address, so the whole list goes in one
request (288 a day at a 5-minute schedule).
"""
import json
import time
import urllib.error
from pathlib import Path

from collectors.common import get_json

HEMS = sorted(json.loads((Path(__file__).parent / "hems.json").read_text()))
MIN_ALT_FT = 1000


def _fetch():
    url = "https://api.adsb.lol/v2/hex/" + ",".join(HEMS)
    try:
        return get_json(url)
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        time.sleep(3)  # rate limited: wait once, then try again
        return get_json(url)


def emergencies(now):
    """Aircraft broadcasting the 7700 general-emergency code.

    Runs every other cycle (10 minutes) so adsb.lol requests stay under 500 a day.
    """
    if now.minute % 10 >= 5:
        return None  # skipped this cycle
    out = []
    for a in get_json("https://api.adsb.lol/v2/sqk/7700").get("ac", []):
        alt = a.get("alt_baro")
        if "lat" not in a or not isinstance(alt, (int, float)) or alt < MIN_ALT_FT:
            continue
        out.append({"lat": round(a["lat"], 2), "lon": round(a["lon"], 2), "alt": int(round(alt, -2)),
                    "track": int(a.get("track") or 0), "type": a.get("t") or "Aircraft"})
    return out


def helicopters(now):
    out = []
    for a in _fetch().get("ac", []):
        alt = a.get("alt_baro")
        if "lat" not in a or not isinstance(alt, (int, float)) or alt < MIN_ALT_FT:
            continue
        out.append({
            "lat": round(a["lat"], 2),
            "lon": round(a["lon"], 2),
            "alt": int(round(alt, -2)),
            "track": int(a.get("track") or 0),
            "type": a.get("t") or "Helicopter",
        })
    return out
