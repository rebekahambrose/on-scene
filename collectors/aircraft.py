"""Aircraft layers.

Air-ambulance helicopters: from adsb.lol (ODbL, credit required), limited to the
FAA-derived air-ambulance list. Their type, operator and registration are
public, so they are shown. Where they take off and land is not: a landing
spot can be an emergency scene. So positions are rounded to about 1 km, an
aircraft is hidden below 1,000 ft, and the trail only keeps airborne points
from the last ~35 minutes.

Emergency aircraft (squawk 7700): an aircraft emergency, not a patient, so full
public flight information is shown: details from hexdb.io, the path flown so
far from OpenSky Network, and the airport it took off from (OurAirports).

adsb.lol allows 500 requests a day per address: the helicopter list goes in
one request every run (288 a day) and the 7700 check runs every other run.
"""
import json
import math
import time
import urllib.error
from datetime import datetime
from pathlib import Path

from collectors.common import get_json

HERE = Path(__file__).parent
FLEET = json.loads((HERE / "hems.json").read_text())
AIRPORTS = json.loads((HERE / "airports.json").read_text())
MIN_ALT_FT = 1000
TRAIL_POINTS = 7          # one point per run: about 35 minutes
TRAIL_MAX_GAP_MIN = 20    # drop a trail if the previous data is older than this


def _adsb(url):
    try:
        return get_json(url)
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        time.sleep(3)  # rate limited: wait once, then try again
        return get_json(url)


def _airborne(a):
    alt = a.get("alt_baro")
    return "lat" in a and isinstance(alt, (int, float)) and alt >= MIN_ALT_FT


def _previous_trails(previous, now):
    try:
        then = datetime.strptime(previous["generated"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=now.tzinfo)
        if (now - then).total_seconds() > TRAIL_MAX_GAP_MIN * 60:
            return {}
        return {f["properties"]["id"]: f["properties"].get("trail", [])
                for f in previous["aircraft"]["features"]}
    except (KeyError, TypeError, ValueError):
        return {}


def helicopters(now, previous):
    trails = _previous_trails(previous, now)
    out = []
    for a in _adsb("https://api.adsb.lol/v2/hex/" + ",".join(sorted(FLEET))).get("ac", []):
        if not _airborne(a):
            continue
        info = FLEET.get(a["hex"].lower(), {})
        point = [round(a["lon"], 2), round(a["lat"], 2)]
        trail = (trails.get(a["hex"], []) + [point])[-TRAIL_POINTS:]
        out.append({
            "id": a["hex"], "lat": point[1], "lon": point[0],
            "alt": int(round(a["alt_baro"], -2)), "speed": int(a.get("gs") or 0), "track": int(a.get("track") or 0),
            "reg": info.get("reg") or (a.get("r") or ""), "model": info.get("model") or a.get("t") or "Helicopter",
            "operator": info.get("operator", ""), "trail": trail,
        })
    return out


def _km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    h = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def _nearest_airport(lat, lon, within_km=8):
    best, dist = None, within_km
    for a_lat, a_lon, name, code in AIRPORTS:
        if abs(a_lat - lat) > 0.2 or abs(a_lon - lon) > 0.3:
            continue
        d = _km(lat, lon, a_lat, a_lon)
        if d < dist:
            best, dist = f"{name} ({code})", d
    return best


def _details(hex_code):
    try:
        d = get_json(f"https://hexdb.io/api/v1/aircraft/{hex_code}")
    except Exception:
        return {}
    model = " ".join(x for x in (d.get("Manufacturer"), d.get("Type")) if x)
    return {"reg": d.get("Registration") or "", "model": model, "operator": d.get("RegisteredOwners") or ""}


def _flight_path(hex_code):
    """Path flown so far and where it took off, from OpenSky (public, anonymous access)."""
    try:
        t = get_json(f"https://opensky-network.org/api/tracks/all?icao24={hex_code}&time=0")
    except Exception:
        return [], None, None
    pts = [p for p in (t.get("path") or []) if p[1] is not None and p[2] is not None]
    if not pts:
        return [], None, None
    step = max(1, len(pts) // 80)
    path = [[round(p[2], 3), round(p[1], 3)] for p in pts[::step]] + [[round(pts[-1][2], 3), round(pts[-1][1], 3)]]
    first = pts[0]
    origin = _nearest_airport(first[1], first[2]) if (first[3] or 0) < 1200 else None
    since = datetime.utcfromtimestamp(t["startTime"]).strftime("%H:%M UTC") if t.get("startTime") else None
    return path, origin, since


def emergencies(now):
    """Aircraft broadcasting 7700. Returns None on skipped cycles (rate limit)."""
    if now.minute % 10 >= 5:
        return None
    out = []
    for a in _adsb("https://api.adsb.lol/v2/sqk/7700").get("ac", []):
        if not _airborne(a):
            continue
        hex_code = a["hex"].lower()
        info = _details(hex_code)
        path, origin, since = _flight_path(hex_code)
        out.append({
            "id": hex_code, "lat": round(a["lat"], 3), "lon": round(a["lon"], 3),
            "alt": int(round(a["alt_baro"], -2)), "speed": int(a.get("gs") or 0), "track": int(a.get("track") or 0),
            "callsign": (a.get("flight") or "").strip(), "reg": info.get("reg") or a.get("r") or "",
            "model": info.get("model") or a.get("t") or "Aircraft", "operator": info.get("operator", ""),
            "origin": origin, "since": since, "path": path,
        })
    return out
