"""Hazards that injure people outdoors: wildfires, earthquakes and NWS storm reports. All public domain."""
import re
import urllib.parse
from datetime import timedelta

from collectors.common import get_json

INJURY = re.compile(r"injur|hurt|killed|fatal|death|died|struck by lightning|hospitali", re.I)


def wildfires(now):
    url = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Incident_Locations_Current/"
           "FeatureServer/0/query?" + urllib.parse.urlencode({
               "where": "IncidentSize >= 100 AND IncidentTypeCategory = 'WF'",
               "outFields": "IncidentName,IncidentSize,PercentContained", "f": "geojson"}))
    out = []
    for f in get_json(url)["features"]:
        p, g = f["properties"], f.get("geometry")
        if not g:
            continue
        lon, lat = g["coordinates"][:2]
        out.append({"kind": "wildfire", "lat": round(lat, 3), "lon": round(lon, 3),
                    "title": f"{(p.get('IncidentName') or 'Wildfire').title()} Fire",
                    "detail": f"{int(p.get('IncidentSize') or 0):,} acres" + (f", {int(p['PercentContained'])}% contained" if p.get("PercentContained") is not None else "")})
    return out


def earthquakes(now):
    data = get_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson")
    out = []
    for f in data["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        p = f["properties"]
        out.append({"kind": "earthquake", "lat": round(lat, 3), "lon": round(lon, 3),
                    "title": f"Magnitude {p['mag']:.1f} earthquake", "detail": p.get("place") or ""})
    return out


def storm_reports(now):
    """NWS Local Storm Reports from the past 6 hours, via Iowa Environmental Mesonet."""
    q = urllib.parse.urlencode({"sts": (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%MZ"),
                                "ets": now.strftime("%Y-%m-%dT%H:%MZ")})
    data = get_json(f"https://mesonet.agron.iastate.edu/geojson/lsr.geojson?{q}")
    out = []
    for f in data["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        injured = bool(INJURY.search(p.get("remark") or ""))
        out.append({"kind": "storm-injury" if injured else "storm", "lat": round(lat, 2), "lon": round(lon, 2),
                    "title": (p.get("typetext") or "Storm report").title() + (" (injuries reported)" if injured else ""),
                    "detail": f"{p.get('city', '').title()}, {p.get('st', '')}".strip(", ")})
    return out
