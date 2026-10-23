"""The Sideline layer: official league injury reports, one marker per team.

NFL: the league's official injury reports as collected by nflverse (updated
daily in season). NBA: the league's official injury report PDF, posted every
15 minutes on game days. Only what the league itself publishes is shown:
player, status and the reason the league lists.
"""
import csv
import io
import re
import urllib.request

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
        out.append({"league": "NFL", "team": name, "lat": lat, "lon": lon, "players": players,
                    "note": f"Official NFL injury report, week {week}."})
    return {"week": week, "teams": out}


# NBA arenas. Team names as they appear in the league's injury report.
ARENAS = {
    "Atlanta Hawks": (33.7573, -84.3963), "Boston Celtics": (42.3662, -71.0621), "Brooklyn Nets": (40.6826, -73.9754),
    "Charlotte Hornets": (35.2251, -80.8392), "Chicago Bulls": (41.8807, -87.6742), "Cleveland Cavaliers": (41.4965, -81.6882),
    "Dallas Mavericks": (32.7905, -96.8103), "Denver Nuggets": (39.7487, -105.0077), "Detroit Pistons": (42.3410, -83.0550),
    "Golden State Warriors": (37.7680, -122.3877), "Houston Rockets": (29.7508, -95.3621), "Indiana Pacers": (39.7640, -86.1555),
    "LA Clippers": (33.9449, -118.3418), "Los Angeles Lakers": (34.0430, -118.2673), "Memphis Grizzlies": (35.1382, -90.0506),
    "Miami Heat": (25.7814, -80.1870), "Milwaukee Bucks": (43.0451, -87.9172), "Minnesota Timberwolves": (44.9795, -93.2761),
    "New Orleans Pelicans": (29.9490, -90.0821), "New York Knicks": (40.7505, -73.9934), "Oklahoma City Thunder": (35.4634, -97.5151),
    "Orlando Magic": (28.5392, -81.3839), "Philadelphia 76ers": (39.9012, -75.1720), "Phoenix Suns": (33.4457, -112.0712),
    "Portland Trail Blazers": (45.5316, -122.6668), "Sacramento Kings": (38.5802, -121.4997), "San Antonio Spurs": (29.4270, -98.4375),
    "Toronto Raptors": (43.6435, -79.3791), "Utah Jazz": (40.7683, -111.9011), "Washington Wizards": (38.8981, -77.0209),
}
NBA_STATUS = {"Out", "Questionable", "Doubtful", "Probable", "Available"}
# nba.com refuses requests that don't look like a browser.
NBA_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def _latest_nba_pdf():
    req = urllib.request.Request("https://official.nba.com/nba-injury-report/", headers=NBA_HEADERS)
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="replace")
    links = re.findall(r"https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_[^\"']+\.pdf", page)
    return links[-1] if links else None


def parse_nba(tokens):
    """Walk the report's word stream: team names open a block, 'Last, First Status Reason' rows follow."""
    names = sorted(((n.split(), n) for n in ARENAS), key=lambda x: -len(x[0]))
    teams, team, i = {}, None, 0
    while i < len(tokens):
        for words, name in names:
            if tokens[i:i + len(words)] == words:
                team, i = name, i + len(words)
                break
        else:
            tok = tokens[i]
            if team and tok.endswith(",") and len(tok) > 1:
                j = i + 1
                while j < len(tokens) and tokens[j] not in NBA_STATUS and j - i < 6:
                    j += 1
                if j < len(tokens) and tokens[j] in NBA_STATUS:
                    name = f"{' '.join(tokens[i + 1:j])} {tok[:-1]}"
                    k = j + 1
                    while (k < len(tokens) and not tokens[k].endswith(",")
                           and not re.match(r"\d\d/\d\d/\d{4}$|\d\d:\d\d$|[A-Z]{2,3}@[A-Z]{2,3}$|Page$", tokens[k])
                           and not any(tokens[k:k + len(w)] == w for w, _ in names)):
                        k += 1
                    reason = " ".join(tokens[j + 1:k]).replace("Injury/Illness - ", "").replace("Injury/Illness -", "").strip()
                    teams.setdefault(team, []).append({"name": name, "status": tokens[j], "injury": reason})
                    i = k
                    continue
            i += 1
    return teams


NBA_CODES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets", "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers", "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies", "MIA": "Miami Heat", "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves", "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}
# Venues that host NFL games away from a team's home stadium.
NEUTRAL = {
    "Stade de France": (48.9245, 2.3602), "Tottenham Hotspur Stadium": (51.6043, -0.0664), "Wembley Stadium": (51.5560, -0.2796),
    "Allianz Arena": (48.2188, 11.6247), "Deutsche Bank Park": (50.0686, 8.6455), "Estadio Azteca": (19.3029, -99.1505),
    "Estadio Banorte": (19.3029, -99.1505), "Croke Park": (53.3607, -6.2512), "Neo Quimica Arena": (-23.5453, -46.4742),
    "Santiago Bernabeu": (40.4531, -3.6883), "Melbourne Cricket Ground": (-37.8200, 144.9834), "Olympiastadion": (52.5147, 13.2395),
}
NFL_GAMES = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"


def _status(start, now, length_h):
    from datetime import timedelta
    if start <= now <= start + timedelta(hours=length_h):
        return "live"
    if now < start <= now + timedelta(hours=14):
        return "upcoming"
    return None


def games(now, nba_tokens=None):
    """NFL and NBA games underway now or starting within 14 hours.

    NFL times come from the nflverse schedule; NBA times come from the matchups
    listed in the league's own injury report. Every one of these games has
    athletic trainers from both teams on the sideline.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    et = ZoneInfo("America/New_York")
    out = []
    today = now.astimezone(et).date()
    for r in csv.DictReader(io.StringIO(get(NFL_GAMES, accept="text/csv"))):
        try:
            day = datetime.strptime(r["gameday"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if abs((day - today).days) > 1 or not r["gametime"]:
            continue
        start = datetime.strptime(f"{r['gameday']} {r['gametime']}", "%Y-%m-%d %H:%M").replace(tzinfo=et)
        state = _status(start, now, 3.5)
        if not state:
            continue
        if r["location"] == "Neutral" and r["stadium"] in NEUTRAL:
            lat, lon = NEUTRAL[r["stadium"]]
        elif r["home_team"] in STADIUMS:
            _, lat, lon = STADIUMS[r["home_team"]]
        else:
            continue
        away, home = STADIUMS.get(r["away_team"], (r["away_team"],))[0], STADIUMS.get(r["home_team"], (r["home_team"],))[0]
        out.append({"league": "NFL", "lat": lat, "lon": lon, "state": state, "title": f"{away} at {home}",
                    "venue": r["stadium"], "start": start.strftime("%-I:%M %p ET, %a %b %-d")})

    toks = nba_tokens or []
    day = None
    for i, t in enumerate(toks):
        if re.match(r"\d\d/\d\d/\d{4}$", t):
            day = t
        m = re.match(r"([A-Z]{3})@([A-Z]{3})$", t)
        if not (m and day and i >= 2 and re.match(r"\d\d:\d\d$", toks[i - 2])):
            continue
        hh, mm = map(int, toks[i - 2].split(":"))
        if hh < 11:
            hh += 12  # the report lists tip-off times without AM/PM; NBA games tip in the afternoon or evening
        start = datetime.strptime(day, "%m/%d/%Y").replace(hour=hh % 24, minute=mm, tzinfo=et)
        state = _status(start, now, 2.75)
        home = NBA_CODES.get(m.group(2))
        if not state or home not in ARENAS or any(g["title"].endswith(home) and g["league"] == "NBA" for g in out):
            continue
        lat, lon = ARENAS[home]
        out.append({"league": "NBA", "lat": lat, "lon": lon, "state": state,
                    "title": f"{NBA_CODES.get(m.group(1), m.group(1))} at {home}", "venue": "",
                    "start": start.strftime("%-I:%M %p ET, %a %b %-d")})
    return out


def nba(now):
    from pypdf import PdfReader  # installed in the bot's workflow

    url = _latest_nba_pdf()
    if not url:
        return {"teams": []}
    req = urllib.request.Request(url, headers=NBA_HEADERS)
    reader = PdfReader(io.BytesIO(urllib.request.urlopen(req, timeout=60).read()))
    tokens = " ".join(p.extract_text() or "" for p in reader.pages).split()
    when = re.search(r"Injury-Report_(\d{4}-\d\d-\d\d)_(\d\d)_?(\d\d)?(AM|PM)", url)
    stamp = f"{when.group(1)} {when.group(2)}:{when.group(3) or '00'} {when.group(4)} ET" if when else ""
    order = {"Out": 0, "Doubtful": 1, "Questionable": 2, "Probable": 3, "Available": 4}
    out = []
    for team, players in parse_nba(tokens).items():
        lat, lon = ARENAS[team]
        players.sort(key=lambda p: (order.get(p["status"], 5), p["name"]))
        out.append({"league": "NBA", "team": team, "lat": lat, "lon": lon, "players": players,
                    "note": f"Official NBA injury report, {stamp}."})
    return {"teams": out, "url": url, "tokens": tokens}
