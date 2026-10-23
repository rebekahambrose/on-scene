"""Hourly and daily history, built from each run's totals. Counts only: no locations below city level, no people.

history.json keeps:
  hours: one snapshot per hour (the latest run in that hour), last 30 days
  days:  per-day peaks and highlights, last 90 days
"""
from collections import Counter
from zoneinfo import ZoneInfo

KEEP_HOURS = 24 * 30
KEEP_DAYS = 90


def snapshot(out):
    """Totals for one run of the bot."""
    feats = out["dispatch"]["features"]
    groups = Counter()
    by_source = Counter()
    for f in feats:
        p = f["properties"]
        by_source[p["src"]] += p["n"]
        for g in ("medical", "traffic", "fire", "rescue", "other"):
            groups[g] += p.get(g, 0)
    hazards = Counter(f["properties"]["kind"] for f in out["hazards"]["features"])
    teams = out["sideline"]["teams"]
    return {
        "calls": sum(groups.values()),
        "groups": dict(groups),
        "sources": dict(by_source),
        "air": len(out["aircraft"]["features"]),
        "emergencies": len(out["emergency_aircraft"]["features"]),
        "hazards": dict(hazards),
        "alerts": len(out["alerts"]["features"]),
        "athletes": {lg: sum(len(t["players"]) for t in teams if t.get("league") == lg) for lg in ("NFL", "NBA")},
        "out": {lg: sum(1 for t in teams if t.get("league") == lg for p in t["players"] if p.get("status") == "Out")
                for lg in ("NFL", "NBA")},
        "games_live": sum(1 for f in out["games"]["features"] if f["properties"]["state"] == "live"),
    }


def update(history, out, now):
    history = history or {}
    hours = history.get("hours", {})
    days = history.get("days", {})
    snap = snapshot(out)
    hours[now.strftime("%Y-%m-%dT%H")] = snap
    for k in sorted(hours)[:-KEEP_HOURS]:
        del hours[k]

    # Days follow US Eastern time so "today" matches what most US visitors see.
    day = days.setdefault(now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"), {"peak_calls": 0, "peak_air": 0, "places": {}, "emergencies": {},
                                                    "hazard_peaks": {}, "games": {}, "samples": 0})
    day["samples"] += 1
    day["peak_calls"] = max(day["peak_calls"], snap["calls"])
    day["peak_air"] = max(day["peak_air"], snap["air"])
    for f in out["dispatch"]["features"]:  # busiest city/town/ZIP areas (already area-level)
        place = f["properties"].get("place")
        if place:
            day["places"][place] = max(day["places"].get(place, 0), f["properties"]["n"])
    day["places"] = dict(Counter(day["places"]).most_common(15))
    for f in out["emergency_aircraft"]["features"]:
        p = f["properties"]
        day["emergencies"][p["id"]] = {k: p.get(k) for k in ("callsign", "model", "operator", "origin")}
    for kind, n in snap["hazards"].items():
        day["hazard_peaks"][kind] = max(day["hazard_peaks"].get(kind, 0), n)
    for f in out["games"]["features"]:
        p = f["properties"]
        day["games"][p["title"]] = {"league": p["league"], "start": p["start"]}
    day["athletes"] = snap["athletes"]
    day["out"] = snap["out"]
    for k in sorted(days)[:-KEEP_DAYS]:
        del days[k]
    return {"hours": hours, "days": days}
