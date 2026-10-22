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

from collectors.common import geocode, get, get_json, group

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


ZIPS = json.loads((Path(__file__).parent / "zips.json").read_text())


def _place(muni, state):
    base = muni.strip().upper()
    for key in (f"{base}, {state}", f"{base} TOWNSHIP, {state}", f"{base} BOROUGH, {state}", f"{base} CITY, {state}"):
        if key in PLACES:
            lat, lon = PLACES[key]
            return key.title()[:-2] + state, lat, lon
    return None


def _table_rows(html):
    """Yield the text of each <td> row in an HTML table page."""
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if cells:
            yield cells


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
    for cells in _table_rows(html):
        if len(cells) < 5 or not re.match(r"\d\d-\d\d-\d{4}", cells[0]):
            continue
        p = _place(cells[1], "PA")
        if p:
            out.append((*p, group(" ".join(cells[4:]))))
    return out


def montgomery_pa(now):
    # RSS items: title "EMS: FALL", description "STREET & CROSS; TOWNSHIP; time-Station".
    rss = get("https://webapp07.montcopa.org/eoc/cadinfo/livecadrss.asp", accept="application/rss+xml")
    out = []
    for item in re.findall(r"<item>(.*?)</item>", rss, re.S):
        title = unescape(re.search(r"<title>(.*?)</title>", item, re.S).group(1))
        desc = unescape(re.search(r"<description>(.*?)</description>", item, re.S).group(1)).split(";")
        if len(desc) > 1:
            p = _place(desc[1], "PA")
            if p:
                out.append((*p, group(title)))
    return out


def nashville(now):
    # Active Nashville Fire Department incidents. Only a ZIP code is published, so calls count by ZIP.
    url = ("https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
           "Nashville_Fire_Department_Active_Incidents_view/FeatureServer/0/query?where=1%3D1"
           "&outFields=incident_type_id,PostalCode&f=json")
    out = []
    for f in get_json(url)["features"]:
        a = f["attributes"]
        z = (a.get("PostalCode") or "").strip()[:5]
        if z in ZIPS:
            lat, lon = ZIPS[z]
            out.append((f"Nashville ZIP {z}", lat, lon, group(a.get("incident_type_id"))))
    return out


def houston(now):
    # Active fire, EMS and crash incidents. Streets have no house numbers, so calls count citywide.
    html = get("https://cohweb.houstontx.gov/ActiveIncidents/Combined.aspx", accept="text/html")
    lat, lon = PLACES["HOUSTON CITY, TX"]
    out = []
    for cells in _table_rows(html):
        if len(cells) != 7 or cells[0] not in ("FD", "PD"):
            continue
        g = group(cells[5])
        if cells[0] == "PD" and g != "traffic":
            continue  # police calls only count when they are crashes
        out.append(("Houston, TX", lat, lon, g))
    return out


def milwaukee(now):
    # Milwaukee Fire Department calls dispatched in the past 15-105 minutes.
    html = get("https://itmdapps.milwaukee.gov/MFDCallData/", accept="text/html")
    calls = [c for c in _table_rows(html) if len(c) >= 5 and c[0].startswith("F")]
    found = geocode([(re.sub(r"\s+MKE$", "", c[2]), "Milwaukee", "WI") for c in calls])
    city = PLACES["MILWAUKEE CITY, WI"]
    out = []
    for i, c in enumerate(calls):
        g = group(c[4])
        if i in found:
            out.append((*found[i], g))
        else:
            out.append(("Milwaukee, WI", *city, g))
    return out


def hernando(now):
    # Hernando County Sheriff active calls; keep Fire Rescue calls and injury crashes. County-level only.
    html = get("https://www.hernandosheriff.org/applications/cadinternetportal/ActiveCalls.aspx", accept="text/html")
    lat, lon = PLACES["HERNANDO COUNTY, FL"]
    out = []
    for cells in _table_rows(html):
        if len(cells) < 6:
            continue
        g = group(cells[1])
        if "Fire" in cells[2] or (g == "traffic" and "injur" in cells[1].lower()):
            out.append(("Hernando County, FL", lat, lon, g))
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
    ("montgomery-pa", montgomery_pa, "Montgomery County PA Public Safety", "Montgomery County, PA", "area", "https://www.montgomerycountypa.gov/departments/department-public-safety/webcad-active-incidents"),
    ("nashville", nashville, "Nashville Fire Department", "Nashville, TN", "area", "https://datanashvillegov-nashville.hub.arcgis.com/datasets/nashville-fire-department-active-incidents/about"),
    ("houston", houston, "City of Houston Active Incidents", "Houston, TX", "area", "https://www.houstontx.gov/activeincidents/"),
    ("milwaukee", milwaukee, "Milwaukee Fire Department", "Milwaukee, WI", "hex", "https://itmdapps.milwaukee.gov/MFDCallData/"),
    ("hernando", hernando, "Hernando County Sheriff (Fire Rescue calls)", "Hernando County, FL", "area", "https://www.hernandosheriff.org/applications/cadinternetportal/ActiveCalls.aspx"),
]
