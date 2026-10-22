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

from collectors import aircraft, dispatch, weather
from collectors.common import GROUPS, hex_id, hex_polygon

OUT = Path(__file__).parent / "site" / "data" / "live.json"


def run(fn, now):
    try:
        return fn(now), None
    except Exception as e:  # one broken source must not stop the others
        traceback.print_exc()
        return [], f"{type(e).__name__}: {e}"[:200]


def main():
    now = datetime.now(timezone.utc)
    sources, hexes, areas = [], defaultdict(Counter), defaultdict(Counter)
    area_pos, hex_src, area_src = {}, {}, {}

    for sid, fn, name, area, precision, link in dispatch.SOURCES:
        calls, err = run(fn, now)
        for c in calls:
            if precision == "hex":
                lat, lon, g = c
                h = hex_id(lat, lon)  # the exact point is dropped here
                hexes[h][g] += 1
                hex_src[h] = sid
            else:
                place, lat, lon, g = c
                areas[place][g] += 1
                area_pos[place] = (lat, lon)
                area_src[place] = sid
        sources.append({"id": sid, "name": name, "area": area, "kind": "dispatch", "precision": precision,
                        "url": link, "ok": err is None, "count": len(calls), "error": err})
        print(f"{sid:15} {'ok ' if err is None else 'ERR'} {len(calls):4} calls")

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

    heli, err = run(aircraft.helicopters, now)
    sources.append({"id": "air-ambulance", "name": "Air-ambulance helicopters (adsb.lol)", "area": "United States",
                    "kind": "aircraft", "precision": "~1 km", "url": "https://www.adsb.lol/", "ok": err is None,
                    "count": len(heli), "error": err})
    print(f"{'air-ambulance':15} {'ok ' if err is None else 'ERR'} {len(heli):4} in flight")

    wx, err = run(weather.alerts, now)
    sources.append({"id": "nws-alerts", "name": "National Weather Service alerts", "area": "United States",
                    "kind": "weather", "precision": "alert area", "url": "https://www.weather.gov/", "ok": err is None,
                    "count": len(wx), "error": err})
    print(f"{'nws-alerts':15} {'ok ' if err is None else 'ERR'} {len(wx):4} alerts")

    out = {
        "generated": now.strftime("%Y-%m-%dT%H:%MZ"),
        "window_minutes": int(dispatch.WINDOW.total_seconds() // 60),
        "sources": sources,
        "dispatch": {"type": "FeatureCollection", "features": features},
        "aircraft": {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [a["lon"], a["lat"]]},
             "properties": {"alt": a["alt"], "track": a["track"], "type": a["type"]}} for a in heli]},
        "alerts": {"type": "FeatureCollection", "features": wx},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
