"""The Sideline layer: this week's official NFL injury report, one marker per team.

Source: the NFL's official injury reports as collected by nflverse (updated
daily in season). Only what the league itself publishes is shown: player,
position, practice participation, game status and the body part listed.
"""
import csv
import io

from collectors.common import get

URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"

# Home stadium of each team.
STADIUMS = {
    "ARI": ("Arizona Cardinals", 33.5276, -112.2626), "ATL": ("Atlanta Falcons", 33.7554, -84.4008),
    "BAL": ("Baltimore Ravens", 39.2780, -76.6227), "BUF": ("Buffalo Bills", 42.7738, -78.7870),
    "CAR": ("Carolina Panthers", 35.2258, -80.8528), "CHI": ("Chicago Bears", 41.8623, -87.6167),
    "CIN": ("Cincinnati Bengals", 39.0954, -84.5160), "CLE": ("Cleveland Browns", 41.5061, -81.6995),
    "DAL": ("Dallas Cowboys", 32.7473, -97.0945), "DEN": ("Denver Broncos", 39.7439, -105.0201),
    "DET": ("Detroit Lions", 42.3400, -83.0456), "GB": ("Green Bay Packers", 44.5013, -88.0622),
    "HOU": ("Houston Texans", 29.6847, -95.4107), "IND": ("Indianapolis Colts", 39.7601, -86.1639),
    "JAX": ("Jacksonville Jaguars", 30.3239, -81.6373), "KC": ("Kansas City Chiefs", 39.0489, -94.4839),
    "LV": ("Las Vegas Raiders", 36.0909, -115.1833), "LAC": ("Los Angeles Chargers", 33.9545, -118.3372),
    "LA": ("Los Angeles Rams", 33.9525, -118.3412), "MIA": ("Miami Dolphins", 25.9580, -80.2389),
    "MIN": ("Minnesota Vikings", 44.9738, -93.2577), "NE": ("New England Patriots", 42.0909, -71.2643),
    "NO": ("New Orleans Saints", 29.9511, -90.0812), "NYG": ("New York Giants", 40.8128, -74.0760),
    "NYJ": ("New York Jets", 40.8142, -74.0730), "PHI": ("Philadelphia Eagles", 39.9008, -75.1675),
    "PIT": ("Pittsburgh Steelers", 40.4468, -80.0158), "SF": ("San Francisco 49ers", 37.4030, -121.9700),
    "SEA": ("Seattle Seahawks", 47.5952, -122.3316), "TB": ("Tampa Bay Buccaneers", 27.9759, -82.5033),
    "TEN": ("Tennessee Titans", 36.1665, -86.7713), "WAS": ("Washington Commanders", 38.9076, -76.8645),
}


def nfl(now):
    season = now.year if now.month >= 8 else now.year - 1
    rows = list(csv.DictReader(io.StringIO(get(URL.format(season=season), accept="text/csv"))))
    if not rows:
        return {"week": None, "teams": []}
    reg = [r for r in rows if r["game_type"] == "REG"] or rows
    week = max(int(r["week"]) for r in reg)
    teams = {}
    for r in reg:
        if int(r["week"]) != week or r["team"] not in STADIUMS:
            continue
        injury = r["report_primary_injury"] or r["practice_primary_injury"]
        teams.setdefault(r["team"], []).append({
            "name": r["full_name"], "pos": r["position"], "injury": injury,
            "status": r["report_status"], "practice": r["practice_status"].replace(" in Practice", "").replace(" In Practice", ""),
        })
    out = []
    for code, players in teams.items():
        name, lat, lon = STADIUMS[code]
        order = {"Out": 0, "Doubtful": 1, "Questionable": 2}
        players.sort(key=lambda p: (order.get(p["status"], 3), p["name"]))
        out.append({"team": name, "lat": lat, "lon": lon, "players": players,
                    "out": sum(p["status"] == "Out" for p in players)})
    return {"week": week, "teams": out}
