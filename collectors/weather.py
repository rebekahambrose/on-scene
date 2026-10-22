"""Active National Weather Service alerts that affect people outdoors (public domain)."""
from collectors.common import get_json

KEEP = (
    "Excessive Heat", "Extreme Heat", "Heat Advisory", "Severe Thunderstorm", "Tornado", "Flash Flood",
    "Flood Warning", "Extreme Wind", "High Wind", "Dust Storm", "Red Flag", "Fire Warning",
    "Air Quality", "Winter Storm", "Blizzard", "Ice Storm", "Extreme Cold", "Hurricane", "Tropical Storm",
)


def _round(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 3), round(coords[1], 3)]
    return [_round(c) for c in coords]


def alerts(now):
    data = get_json("https://api.weather.gov/alerts/active?status=actual")
    out = []
    for f in data["features"]:
        p = f["properties"]
        if not f.get("geometry") or not any(k in p["event"] for k in KEEP):
            continue
        geom = f["geometry"]
        out.append({
            "type": "Feature",
            "geometry": {"type": geom["type"], "coordinates": _round(geom["coordinates"])},
            "properties": {"event": p["event"], "severity": p.get("severity"), "headline": p.get("headline"), "ends": p.get("ends") or p.get("expires")},
        })
    return out
