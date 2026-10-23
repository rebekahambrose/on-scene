"""Hazards that injure people outdoors: wildfires, earthquakes and NWS storm reports. All public domain."""
import re
import urllib.parse
from datetime import timedelta

from collectors.common import get, get_json

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


def hurricanes(now):
    """Active tropical systems from the National Hurricane Center."""
    data = get_json("https://www.nhc.noaa.gov/CurrentStorms.json")
    kinds = {"HU": "Hurricane", "MH": "Major hurricane", "TS": "Tropical storm", "TD": "Tropical depression",
             "STS": "Subtropical storm", "STD": "Subtropical depression", "PTC": "Potential tropical cyclone",
             "PC": "Post-tropical cyclone", "TY": "Typhoon"}
    out = []
    for s in data.get("activeStorms", []):
        mph = round(int(s.get("intensity") or 0) * 1.15078)
        out.append({"kind": "hurricane", "lat": s["latitudeNumeric"], "lon": s["longitudeNumeric"],
                    "title": f"{kinds.get(s.get('classification'), 'Tropical system')} {s.get('name', '')}".strip(),
                    "detail": f"Winds {mph} mph" + (f", moving {s['movementDir']}° at {round(int(s['movementSpeed']) * 1.15078)} mph"
                                                    if s.get("movementDir") is not None and s.get("movementSpeed") else "")})
    return out


FLOOD_LABEL = {"minor": "Minor flooding", "moderate": "Moderate flooding", "major": "Major flooding"}


def floods(now):
    """River gauges currently at minor, moderate or major flood stage (NOAA National Water Prediction Service).

    This feed is large and slow, so the bot refreshes it every 30 minutes (see collect.py) and asks
    region by region; a nationwide request often times out on NOAA's side.
    """
    regions = [(-125, 24, -105, 50), (-105, 24, -90, 50), (-90, 24, -80, 50), (-80, 24, -66, 50),
               (-180, 50, -129, 72), (-161, 15, -154, 23), (-68, 17, -64, 19)]  # 4 CONUS slices, Alaska, Hawaii, Puerto Rico
    gauges, failed = [], 0
    for x0, y0, x1, y1 in regions:
        try:
            data = get_json(f"https://api.water.noaa.gov/nwps/v1/gauges?bbox.xmin={x0}&bbox.ymin={y0}"
                            f"&bbox.xmax={x1}&bbox.ymax={y1}&srid=EPSG_4326", timeout=120)
            gauges += data.get("gauges", [])
        except Exception:
            failed += 1
    if failed > len(regions) // 2:
        raise RuntimeError(f"{failed} of {len(regions)} regions failed")
    out = []
    for g in gauges:
        obs = (g.get("status") or {}).get("observed") or {}
        cat = obs.get("floodCategory")
        if cat in FLOOD_LABEL:
            out.append({"kind": "flood", "lat": round(g["latitude"], 3), "lon": round(g["longitude"], 3),
                        "title": FLOOD_LABEL[cat], "detail": f"{g.get('name', '')}, {g.get('state', {}).get('abbreviation', '')}"})
    return out


AQI_ORDER = ["Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "Hazardous"]


def air_quality(now):
    """Reporting areas where current air quality is unhealthy for sensitive groups or worse (EPA AirNow).

    These are the conditions that change outdoor practice and game decisions.
    """
    text = get("https://files.airnowtech.org/airnow/today/reportingarea.dat", accept="text/plain")
    best = {}
    for line in text.splitlines():
        f = line.split("|")
        if len(f) < 15 or f[5] != "O" or f[6] != "Y" or not f[12].isdigit():
            continue
        aqi = int(f[12])
        if aqi < 101:
            continue
        key = (f[7], f[8])
        if key not in best or aqi > best[key]["aqi"]:
            best[key] = {"kind": "air", "lat": round(float(f[9]), 3), "lon": round(float(f[10]), 3), "aqi": aqi,
                         "title": f"Air quality: {f[13]}", "detail": f"AQI {aqi} ({f[11]}) in {f[7]}, {f[8]}"}
    return list(best.values())


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
