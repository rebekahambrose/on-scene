"""Shared helpers: polite HTTP, call-type grouping, and the privacy step (hex snapping)."""
import json
import math
import urllib.request

USER_AGENT = "OnScene/0.1 (public-data map; github.com/rebekahambrose/on-scene)"
TIMEOUT = 30

# Hexes are laid out in Web Mercator meters. At US latitudes a 500 m mercator
# radius is roughly 380-440 m on the ground, so each hex is ~800 m across.
HEX_R = 500
EARTH_R = 6378137


def get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_json(url):
    return json.loads(get(url))


def geocode(addresses):
    """Census Bureau batch geocoder (free, public domain). Returns {index: (lat, lon)}.

    Addresses live only in memory for this call; nothing is cached or saved.
    Intersections and partial streets usually do not match and are left out.
    """
    if not addresses:
        return {}
    import csv
    import io
    import uuid

    buf = io.StringIO()
    w = csv.writer(buf)
    for i, (street, city, state) in enumerate(addresses):
        w.writerow([i, street, city, state, ""])
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"benchmark\"\r\n\r\nPublic_AR_Current\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"a.csv\"\r\n"
        f"Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        "https://geocoding.geo.census.gov/geocoder/locations/addressbatch", data=body,
        headers={"User-Agent": USER_AGENT, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    out = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 6 and row[2] == "Match":
            lon, lat = row[5].split(",")
            out[int(row[0])] = (float(lat), float(lon))
    return out


TRAFFIC_WORDS = ("mvi", "mva", "motor vehicle", "vehicle accident", "collision", "crash", "traffic / transportation",
                 "traffic/transportation", "traffic accident", "accident w/", "auto accident", "vehicle acc")
MEDICAL_WORDS = ("aid", "medic", "medical", "acuity", "overdose", "violence", "breath", "cardiac", "fall", "sick", "injur",
                 "uncons", "bls", "als", "ems", "assault", "bleed", "hemorr", "abdominal", "diabetic", "pain", "psych",
                 "chest", "stroke", "seizure", "allerg", "heat", "cold expos", "drown", "chok", "burn", "trauma", "lacerat",
                 "pregnan", "childbirth", "poison", "stab", "gunshot", "shot", "faint", "syncope", "headache", "back",
                 "lift assist", "person down", "convuls", "respiratory", "arrest", "cpr")


def group(call_type):
    """Collapse a dispatch call type into one of five broad groups."""
    s = (call_type or "").lower()
    if any(k in s for k in TRAFFIC_WORDS):
        return "traffic"
    if "rescue" in s or "extrication" in s or "entrapment" in s:
        return "rescue"
    if any(k in s for k in MEDICAL_WORDS):
        return "medical"
    if "fire" in s and "alarm" not in s:
        return "fire"
    return "other"


GROUPS = ("medical", "traffic", "fire", "rescue", "other")


def _to_merc(lat, lon):
    x = EARTH_R * math.radians(lon)
    y = EARTH_R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def _from_merc(x, y):
    lon = math.degrees(x / EARTH_R)
    lat = math.degrees(2 * math.atan(math.exp(y / EARTH_R)) - math.pi / 2)
    return lat, lon


def hex_id(lat, lon):
    """Snap a point to its hex. Only the hex id survives; the point is discarded."""
    x, y = _to_merc(lat, lon)
    q = (math.sqrt(3) / 3 * x - y / 3) / HEX_R
    r = (2 / 3 * y) / HEX_R
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def hex_polygon(q, r):
    cx = HEX_R * math.sqrt(3) * (q + r / 2)
    cy = HEX_R * 1.5 * r
    ring = []
    for k in range(7):
        a = math.radians(60 * (k % 6) - 30)
        lat, lon = _from_merc(cx + HEX_R * math.cos(a), cy + HEX_R * math.sin(a))
        ring.append([round(lon, 5), round(lat, 5)])
    return ring
