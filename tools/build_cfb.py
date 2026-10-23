"""Build collectors/cfb_games.json: this week's FBS and FCS college football games with stadium locations.

Source: CollegeFootballData.com (free API key, commercial use permitted by its terms).
Runs once a day from .github/workflows/cfb.yml, about 3-4 API calls, well inside the
free monthly quota. The bot then decides live/upcoming from kickoff times without
calling the API again.

    CFBD_KEY=... python3 tools/build_cfb.py
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.collegefootballdata.com"
OUT = Path(__file__).resolve().parent.parent / "collectors" / "cfb_games.json"


def call(path, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['CFBD_KEY']}",
                                               "Accept": "application/json", "User-Agent": "OnScene/0.1"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def pick(d, *names):
    for n in names:
        if d.get(n) not in (None, ""):
            return d[n]
    return None


def latlon(loc):
    """CFBD venue locations come as {x, y}; work out which one is latitude."""
    if not isinstance(loc, dict):
        return None
    a, b = loc.get("x"), loc.get("y")
    if a is None or b is None:
        return None
    return (a, b) if -90 <= a <= 90 and b < 0 else (b, a)


def main():
    if not os.environ.get("CFBD_KEY"):
        print("CFBD_KEY is not set yet; skipping. Add it under the repo's Settings → Secrets → Actions.")
        return
    now = datetime.now(timezone.utc)
    season = now.year if now.month >= 7 else now.year - 1
    weeks = call("/calendar", year=season)
    current = None
    for w in weeks:
        start = pick(w, "startDate", "firstGameStart", "first_game_start")
        end = pick(w, "endDate", "lastGameStart", "last_game_start")
        if start and end and start[:10] <= now.strftime("%Y-%m-%d") <= end[:10]:
            current = w
    if not current:  # between weeks: take the next one that hasn't started
        upcoming = [w for w in weeks if (pick(w, "startDate", "firstGameStart") or "") > now.isoformat()]
        current = upcoming[0] if upcoming else weeks[-1]
    week = current["week"]
    stype = pick(current, "seasonType", "season_type") or "regular"

    venues = {v["id"]: v for v in call("/venues")}
    games = []
    for division in ("fbs", "fcs"):
        for g in call("/games", year=season, week=week, seasonType=stype, classification=division):
            v = venues.get(pick(g, "venueId", "venue_id"))
            ll = latlon(v.get("location")) if v else None
            if not ll:
                continue
            games.append({
                "away": pick(g, "awayTeam", "away_team"), "home": pick(g, "homeTeam", "home_team"),
                "start": pick(g, "startDate", "start_date"), "tbd": bool(pick(g, "startTimeTBD", "start_time_tbd")),
                "venue": v.get("name"), "city": f"{v.get('city', '')}, {v.get('state', '')}".strip(", "),
                "lat": round(ll[0], 4), "lon": round(ll[1], 4), "division": division.upper(),
            })
    OUT.write_text(json.dumps({"season": season, "week": week, "built": now.strftime("%Y-%m-%dT%H:%MZ"), "games": games},
                              indent=0, sort_keys=True))
    print(f"week {week}: {len(games)} games written to {OUT}")


if __name__ == "__main__":
    main()
