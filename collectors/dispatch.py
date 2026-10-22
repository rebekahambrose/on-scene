"""Collectors for public fire/EMS dispatch feeds.

Each collector returns a list of calls as (lat, lon, group) for point sources or
(place_name, lat, lon, group) for area sources. Addresses, unit names and exact
times are read only long enough to do this and are never returned.
"""
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors.common import get, get_json, group

WINDOW = timedelta(hours=2)
PLACES = json.loads((Path(__file__).parent / "places.json").read_text())


def _socrata(base, time_field, since, extra_where=""):
    where = f"{time_field} > '{since}'" + (f" AND {extra_where}" if extra_where else "")
    q = urllib.parse.urlencode({"$where": where, "$limit": 5000})
    return get_json(f"{base}?{q}")


def seattle(now):
    since = (now - WINDOW).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%dT%H:%M:%S")
    rows = _socrata("https://data.seattle.gov/resource/kzjm-xkqj.json", "datetime", since)
    return [(float(r["latitude"]), float(r["longitude"]), group(r.get("type")))
            for r in rows if r.get("latitude")]


def austin_fire(now):
    since = (now - WINDOW).strftime("%Y-%m-%dT%H:%M:%S")
    rows = _socrata("https://data.austintexas.gov/resource/wpu4-x69d.json", "published_date", since)
    return [(float(r["latitude"]), float(r["longitude"]), group(r.get("issue_reported")))
            for r in rows if r.get("latitude")]


def austin_crashes(now):
    since = (now - WINDOW).strftime("%Y-%m-%dT%H:%M:%S")
    rows = _socrata("https://data.austintexas.gov/resource/dx9v-zd7x.json", "published_date", since)
    return [(float(r["latitude"]), float(r["longitude"]), "traffic")
            for r in rows if r.get("latitude") and re.search(r"crash|collision", r.get("issue_reported", ""), re.I)]


def pinellas(now):
    # Active calls. The county already places each call at its map-grid center.
    calls = get_json("https://911.pinellas.gov/files/Activity.json")["CallInfo"]
    return [(float(c["Lat"]), float(c["Lon"]), group(c.get("Type"))) for c in calls if c.get("Lat")]


def san_diego(now):
    # Gives streets but no coordinates, so calls count toward the city as a whole.
    calls = get_json("https://webapps.sandiego.gov/sdfiredispatch/api/v1/Incidents")
    lat, lon = PLACES["SAN DIEGO CITY, CA"]
    return [("San Diego, CA", lat, lon, group(c.get("CallType"))) for c in calls]


def _place(muni, state):
    key = f"{muni.strip().upper()}, {state}"
    if key in PLACES:
        lat, lon = PLACES[key]
        return key.title().replace(", Pa", ", PA"), lat, lon
    return None


def lancaster(now):
    rss = get("https://webcad.lcwc911.us/Pages/Public/LiveIncidentsFeed.aspx", accept="application/rss+xml")
    out = []
    for item in re.findall(r"<item>(.*?)</item>", rss, re.S):
        title = unescape(re.search(r"<title>(.*?)</title>", item, re.S).group(1))
        desc = unescape(re.search(r"<description>(.*?)</description>", item, re.S).group(1))
        if title.startswith("TRAINING"):
            continue
        p = _place(desc.split(";")[0], "PA")
        if p:
            out.append((*p, group(title)))
    return out


def dauphin(now):
    html = get("https://dpswebcad.dauphincounty.gov/webcad/", accept="text/html")
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 5 or not re.match(r"\d\d-\d\d-\d{4}", cells[0]):
            continue
        p = _place(cells[1], "PA")
        if p:
            out.append((*p, group(" ".join(cells[4:]))))
    return out


SOURCES = [
    # id, collector, display name, area, precision, link
    ("seattle", seattle, "Seattle Fire Department", "Seattle, WA", "hex", "https://data.seattle.gov/Public-Safety/Seattle-Real-Time-Fire-911-Calls/kzjm-xkqj"),
    ("austin-fire", austin_fire, "Austin Fire Department", "Austin, TX", "hex", "https://data.austintexas.gov/d/wpu4-x69d"),
    ("austin-crashes", austin_crashes, "Austin traffic crashes", "Austin, TX", "hex", "https://data.austintexas.gov/d/dx9v-zd7x"),
    ("pinellas", pinellas, "Pinellas County 911", "Pinellas County, FL", "hex", "https://911.pinellas.gov/"),
    ("san-diego", san_diego, "San Diego Fire-Rescue", "San Diego, CA", "area", "https://webapps.sandiego.gov/sdfiredispatch/"),
    ("lancaster", lancaster, "Lancaster County-Wide Communications", "Lancaster County, PA", "area", "https://www.lcwc911.us/live-incident-list"),
    ("dauphin", dauphin, "Dauphin County 911", "Dauphin County, PA", "area", "https://dpswebcad.dauphincounty.gov/webcad/"),
]
