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
    # The county's active-incident map layer carries coordinates (at the intersection), so these snap to hexes.
    url = ("https://gis.montcopa.org/arcgis/rest/services/Hosted/Montgomery_County_Active_CAD_Incidents_View/"
           "FeatureServer/0/query?where=1%3D1&outFields=type,incidentsubtype,lat,lon&f=json")
    out = []
    for f in get_json(url)["features"]:
        a = f["attributes"]
        try:
            lat, lon = float(a["lat"]), float(a["lon"])
        except (TypeError, ValueError):
            continue
        kind = (a.get("type") or "").lower()
        g = "traffic" if kind == "traffic" else "medical" if kind == "ems" else group(f"{a.get('type')} {a.get('incidentsubtype') or ''}")
        out.append((lat, lon, g))
    return out


def las_vegas_crashes(now):
    # Las Vegas Metro Police traffic calls; only crashes with injuries, from the past 2 hours.
    # The layer already holds only current calls; the time check below keeps it to the past 2 hours.
    since = int((now - WINDOW).timestamp() * 1000)
    url = ("https://services.arcgis.com/jjSk6t82vIntwDbs/arcgis/rest/services/LVMPD_Traffic_CFS/FeatureServer/6/query?"
           + urllib.parse.urlencode({"where": "1=1", "outFields": "event_description,event_date,latitude,longitude", "f": "json"}))
    out = []
    for f in get_json(url).get("features", []):
        a = f["attributes"]
        desc = (a.get("event_description") or "").upper()
        if (a.get("event_date") or 0) < since:
            continue
        if ("INJUR" in desc or "FATAL" in desc) and a.get("latitude"):
            out.append((float(a["latitude"]), float(a["longitude"]), "traffic"))
    return out


MPDS = re.compile(r"^\d{1,2}[A-EΩO]\d{2}")  # medical dispatch codes like "21B01-HEMORRHAGE"


def oneida_ny(now):
    # Oneida County 911 live activity: keep EMS (medical dispatch codes), fire and crash calls; counted by town.
    html = get("https://oneidacountyny.gov/departments/emergency-services/911-center-live-activity-feed/", accept="text/html")
    out = []
    for cells in _table_rows(html):
        if len(cells) < 3 or not re.match(r"\d{4}-\d+", cells[0]):
            continue
        what = re.sub(r"^(In Progress|Dispatched|Pending|Enroute|On Scene|Arrived)\s+", "", cells[1], flags=re.I)
        g = group(what)
        if not (MPDS.match(what) or g in ("fire", "traffic", "rescue")) or "DISABLED" in what.upper():
            continue
        town = re.sub(r"\s*View On Map.*$", "", cells[2]).split(",")[-1].strip()
        p = _place(town, "NY")
        if p:
            out.append((*p, "medical" if MPDS.match(what) and g == "other" else g))
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


CHP_CENTERS = {
    "BFCC": ("Bakersfield", 35.37, -119.02), "BSCC": ("Barstow", 34.90, -117.02), "BICC": ("Bishop", 37.36, -118.39),
    "BCCC": ("San Diego", 32.72, -117.16), "CCCC": ("Sacramento", 38.58, -121.49), "CHCC": ("Chico", 39.73, -121.84),
    "ECCC": ("El Centro", 32.79, -115.56), "FRCC": ("Fresno", 36.74, -119.79), "GGCC": ("Oakland", 37.80, -122.27),
    "HMCC": ("Eureka", 40.80, -124.16), "ICCC": ("Indio", 33.72, -116.22), "INCC": ("San Bernardino", 34.11, -117.29),
    "LACC": ("Los Angeles", 34.05, -118.24), "MRCC": ("Merced", 37.30, -120.48), "MYCC": ("Salinas", 36.68, -121.66),
    "OCCC": ("Santa Ana", 33.75, -117.87), "RDCC": ("Redding", 40.59, -122.39), "SACC": ("Sacramento", 38.58, -121.49),
    "SLCC": ("San Luis Obispo", 35.28, -120.66), "SKCCSTCC": ("Stockton", 37.96, -121.29), "SUCC": ("Susanville", 40.42, -120.65),
    "TKCC": ("Truckee", 39.33, -120.18), "UKCC": ("Ukiah", 39.15, -123.21), "VTCC": ("Ventura", 34.27, -119.23),
    "YKCC": ("Yreka", 41.74, -122.63),
}
CHP_INJURY = re.compile(r"Inj|1141|Ambulance|Fatal", re.I)
CHP_NO_INJURY = re.compile(r"No Inj", re.I)


def chp(now):
    """California Highway Patrol incidents with injuries or an ambulance en route, statewide.

    The page shows one dispatch center at a time, so this asks for each of the 25.
    Calls are placed at the city of the CHP area office handling them.
    """
    import http.cookiejar
    import urllib.error
    import urllib.request
    from collectors.common import USER_AGENT

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [("User-Agent", USER_AGENT)]
    url = "https://cad.chp.ca.gov/Traffic.aspx"
    fresh = lambda: opener.open(url, timeout=40).read().decode("utf-8", errors="replace")
    page = fresh()
    out, failed = [], 0
    for code, (center, c_lat, c_lon) in CHP_CENTERS.items():
        form = dict(re.findall(r'name="(__[A-Z]+)"[^>]*value="([^"]*)"', page))
        form.update({"__EVENTTARGET": "ddlComCenter", "__EVENTARGUMENT": "", "ddlComCenter": code,
                     "ddlSearches": "Choose One", "ddlResources": "Choose One"})
        try:
            page = opener.open(url, data=urllib.parse.urlencode(form).encode(), timeout=40).read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError:
            failed += 1  # one center failing should not lose the rest; start over from a clean page
            page = fresh()
            continue
        for cells in _table_rows(page):
            if len(cells) < 7 or not re.match(r"\d{4}$", cells[1]):
                continue
            kind = cells[3]
            if not CHP_INJURY.search(kind) or CHP_NO_INJURY.search(kind):
                continue
            area = cells[6]
            key = f"{area.upper()}, CA"
            if key in PLACES:
                lat, lon = PLACES[key]
                out.append((f"{area}, CA (CHP)", lat, lon, "traffic"))
            else:
                out.append((f"{center} area, CA (CHP)", c_lat, c_lon, "traffic"))
    if failed == len(CHP_CENTERS):
        raise RuntimeError("every CHP dispatch center failed")
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
    ("montgomery-pa", montgomery_pa, "Montgomery County PA Public Safety", "Montgomery County, PA", "hex", "https://www.montgomerycountypa.gov/departments/department-public-safety/webcad-active-incidents"),
    ("las-vegas-crashes", las_vegas_crashes, "Las Vegas Metro Police (injury crashes)", "Las Vegas, NV", "hex", "https://services.arcgis.com/jjSk6t82vIntwDbs/arcgis/rest/services/LVMPD_Traffic_CFS/FeatureServer/6"),
    ("oneida-ny", oneida_ny, "Oneida County 911 (EMS, fire, crashes)", "Oneida County, NY", "area", "https://oneidacountyny.gov/departments/emergency-services/911-center-live-activity-feed/"),
    ("nashville", nashville, "Nashville Fire Department", "Nashville, TN", "area", "https://datanashvillegov-nashville.hub.arcgis.com/datasets/nashville-fire-department-active-incidents/about"),
    ("houston", houston, "City of Houston Active Incidents", "Houston, TX", "area", "https://www.houstontx.gov/activeincidents/"),
    ("milwaukee", milwaukee, "Milwaukee Fire Department", "Milwaukee, WI", "hex", "https://itmdapps.milwaukee.gov/MFDCallData/"),
    ("chp", chp, "California Highway Patrol (injury crashes)", "California highways", "area", "https://cad.chp.ca.gov/Traffic.aspx"),
    ("hernando", hernando, "Hernando County Sheriff (Fire Rescue calls)", "Hernando County, FL", "area", "https://www.hernandosheriff.org/applications/cadinternetportal/ActiveCalls.aspx"),
]
