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
    heli, err = run(lambda t: aircraft.helicopters(t, previous), now)
    heli = heli or []
    sources.append(status("air-ambulance", "Air-ambulance helicopters (adsb.lol + FAA registry)", "United States",
                          "aircraft", "~1 km", "https://www.adsb.lol/", len(heli), err))
    emerg, err = run(aircraft.emergencies, now)
    if emerg is None and err is None:  # skipped this cycle to respect the rate limit: keep the last result
        old_paths = {f["properties"]["id"]: f["geometry"]["coordinates"]
                     for f in previous.get("tracks", {}).get("features", []) if f["properties"].get("kind") == "emergency"}
        emerg = [{"lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1], **f["properties"],
                  "path": old_paths.get(f["properties"].get("id"), [])}
                 for f in previous.get("emergency_aircraft", {}).get("features", [])]
    emerg = emerg or []
    sources.append(status("squawk-7700", "Aircraft declaring an emergency (adsb.lol, OpenSky, hexdb.io)", "Worldwide",
                          "aircraft", "exact", "https://www.adsb.lol/", len(emerg), err))
    tracks = [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": h["trail"]},
               "properties": {"id": h["id"], "kind": "heli"}} for h in heli if len(h["trail"]) > 1]
    tracks += [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": e["path"] + [[e["lon"], e["lat"]]]},
                "properties": {"id": e["id"], "kind": "emergency"}} for e in emerg if e.get("path")]

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
        ("hurricanes", hazards.hurricanes, "Tropical storms and hurricanes (NHC)", "https://www.nhc.noaa.gov/"),
        ("air-quality", hazards.air_quality, "Unhealthy air quality (EPA AirNow)", "https://www.airnow.gov/"),
        ("floods", hazards.floods, "Rivers and coasts at flood stage (NOAA)", "https://water.noaa.gov/"),
    ):
        had_floods = any(s.get("id") == "floods" and s.get("ok") for s in previous.get("sources", []))
        if sid == "floods" and had_floods and now.minute % 30 >= 5:
            # slow feed: refresh every 30 minutes, reuse the last result in between
            items = [{"lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1], **f["properties"]}
                     for f in previous.get("hazards", {}).get("features", []) if f["properties"].get("kind") == "flood"]
            err = None
        else:
            items, err = run(fn, now)
            if err and sid == "floods":  # keep the last good flood map rather than blanking it
                items = [{"lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1], **f["properties"]}
                         for f in previous.get("hazards", {}).get("features", []) if f["properties"].get("kind") == "flood"]
            items = items or []
        hz += items
        sources.append(status(sid, name, "United States", "hazard", "as reported", link, len(items), err))

    # --- sports ---
    nfl, err = run(sports.nfl, now)
    nfl = nfl or {"week": None, "teams": []}
    sources.append(status("nfl-injuries", f"NFL official injury report, week {nfl['week']}", "NFL", "sports",
                          "team stadium", "https://www.nfl.com/injuries/", sum(len(t["players"]) for t in nfl["teams"]), err))
    nba, err = run(sports.nba, now)
    nba = nba or {"teams": []}
    sources.append(status("nba-injuries", "NBA official injury report", "NBA", "sports", "team arena",
                          nba.get("url") or "https://official.nba.com/nba-injury-report/",
                          sum(len(t["players"]) for t in nba["teams"]), err))
    games, err = run(lambda t: sports.games(t, nba.get("tokens")), now)
    games = games or []
    sources.append(status("games", "NFL and NBA games now and today", "NFL, NBA", "sports", "venue",
                          "https://github.com/nflverse/nfldata", len(games), err))

    out = {
        "generated": now.strftime("%Y-%m-%dT%H:%MZ"),
        "window_minutes": int(dispatch.WINDOW.total_seconds() // 60),
        "sources": sources,
        "dispatch": {"type": "FeatureCollection", "features": features},
        "aircraft": points(heli, ("id", "alt", "speed", "track", "reg", "model", "operator", "trail")),
        "emergency_aircraft": points(emerg, ("id", "alt", "speed", "track", "callsign", "reg", "model", "operator",
                                             "origin", "since")),
        "tracks": {"type": "FeatureCollection", "features": tracks},
        "alerts": {"type": "FeatureCollection", "features": wx},
        "hazards": points(hz, ("kind", "title", "detail", "aqi")),
        "games": points(games, ("league", "state", "title", "venue", "start")),
        "sideline": {"week": nfl["week"], "teams": nfl["teams"] + nba["teams"]},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
