"""The On Scene bot. Run every 5 minutes.

Pulls every source, applies the privacy step, and writes one file the map reads:
site/data/live.json. A source that fails is reported as down and skipped; the
rest still publish.

    python3 collect.py
"""
import json
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from collectors import aircraft, dispatch, hazards, sports, weather
from collectors.common import GROUPS, get_json, hex_id, hex_polygon

OUT = Path(__file__).parent / "site" / "data" / "live.json"
PREVIOUS = "https://raw.githubusercontent.com/rebekahambrose/on-scene/data/live.json"


def run(fn, now):
    try:
        return fn(now), None
    except Exception as e:  # one broken source must not stop the others
        traceback.print_exc()
        return None, f"{type(e).__name__}: {e}"[:200]


def status(sid, name, area, kind, precision, url, count, err):
    print(f"{sid:16} {'ok ' if err is None else 'ERR'} {count:5}")
    return {"id": sid, "name": name, "area": area, "kind": kind, "precision": precision,
            "url": url, "ok": err is None, "count": count, "error": err}


def points(items, keys):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [i["lon"], i["lat"]]},
         "properties": {k: i[k] for k in keys if k in i}} for i in items]}


def main():
    now = datetime.now(timezone.utc)
    try:
        previous = get_json(PREVIOUS)
    except Exception:
        previous = {}
    sources = []

    # --- 911 dispatch: snap to hexes, or count by town/ZIP/city ---
    hexes, areas = defaultdict(Counter), defaultdict(Counter)
    area_pos, hex_src, area_src = {}, {}, {}
    for sid, fn, name, area, precision, link in dispatch.SOURCES:
        calls, err = run(fn, now)
        calls = calls or []
        for c in calls:
            if len(c) == 3:
                lat, lon, g = c
                h = hex_id(lat, lon)  # the exact point is dropped here
                hexes[h][g] += 1
                hex_src[h] = sid
            else:
                place, lat, lon, g = c
                areas[place][g] += 1
                area_pos[place] = (lat, lon)
                area_src[place] = sid
        sources.append(status(sid, name, area, "dispatch", precision, link, len(calls), err))

    features = []
    for (q, r), by in hexes.items():
        features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [hex_polygon(q, r)]},
                         "properties": {"n": sum(by.values()), "top": by.most_common(1)[0][0], "src": hex_src[(q, r)],
                                        **{g: by[g] for g in GROUPS}}})
    for place, by in areas.items():
        lat, lon = area_pos[place]
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                         "properties": {"n": sum(by.values()), "top": by.most_common(1)[0][0], "src": area_src[place],
                                        "place": place, **{g: by[g] for g in GROUPS}}})

    # --- aircraft ---
    heli, err = run(aircraft.helicopters, now)
    heli = heli or []
    sources.append(status("air-ambulance", "Air-ambulance helicopters (adsb.lol)", "United States", "aircraft",
                          "~1 km", "https://www.adsb.lol/", len(heli), err))
    emerg, err = run(aircraft.emergencies, now)
    if emerg is None and err is None:  # skipped this cycle to respect the rate limit: keep the last result
        emerg = [{"lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1], **f["properties"]}
                 for f in previous.get("emergency_aircraft", {}).get("features", [])]
    emerg = emerg or []
    sources.append(status("squawk-7700", "Aircraft declaring an emergency (adsb.lol)", "Worldwide", "aircraft",
                          "~1 km", "https://www.adsb.lol/", len(emerg), err))

    # --- weather and hazards ---
    wx, err = run(weather.alerts, now)
    wx = wx or []
    sources.append(status("nws-alerts", "National Weather Service alerts", "United States", "weather",
                          "alert area", "https://www.weather.gov/", len(wx), err))
    hz = []
    for sid, fn, name, link in (
        ("wildfires", hazards.wildfires, "Wildfires 100+ acres (NIFC)", "https://data-nifc.opendata.arcgis.com/"),
        ("earthquakes", hazards.earthquakes, "Earthquakes M2.5+, past day (USGS)", "https://earthquake.usgs.gov/"),
        ("storm-reports", hazards.storm_reports, "NWS storm reports, past 6 hours", "https://mesonet.agron.iastate.edu/request/gis/lsrs.phtml"),
    ):
        items, err = run(fn, now)
        items = items or []
        hz += items
        sources.append(status(sid, name, "United States", "hazard", "as reported", link, len(items), err))

    # --- sports ---
    nfl, err = run(sports.nfl, now)
    nfl = nfl or {"week": None, "teams": []}
    sources.append(status("nfl-injuries", f"NFL official injury report, week {nfl['week']}", "NFL", "sports",
                          "team stadium", "https://www.nfl.com/injuries/", sum(len(t["players"]) for t in nfl["teams"]), err))

    out = {
        "generated": now.strftime("%Y-%m-%dT%H:%MZ"),
        "window_minutes": int(dispatch.WINDOW.total_seconds() // 60),
        "sources": sources,
        "dispatch": {"type": "FeatureCollection", "features": features},
        "aircraft": points(heli, ("alt", "track", "type")),
        "emergency_aircraft": points(emerg, ("alt", "track", "type")),
        "alerts": {"type": "FeatureCollection", "features": wx},
        "hazards": points(hz, ("kind", "title", "detail")),
        "sideline": {"week": nfl["week"], "teams": nfl["teams"]},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
