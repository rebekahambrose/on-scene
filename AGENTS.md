# On Scene: project brief for coding agents

Live site: https://onscene.netlify.app · Repo: github.com/rebekahambrose/on-scene (public)

On Scene is a free, public, non-commercial advocacy site that makes emergency response and
athletic trainers (ATs) visible. It maps live 911 activity, air ambulances, aircraft
emergencies, hazards, NFL/NBA/college games and official league injury reports, using only
public data. The owner is an athletic training student and a beginner coder: explain things
plainly, never present her as a certified or licensed AT, and never present anything as
medical advice.

## Non-negotiable rules
- **Privacy by design.** 911 calls are aggregated before anything is written: snapped to
  ~800 m hexes (`collectors/common.py` `hex_id`), or counted by town / ZIP / city. Never write
  addresses, names, unit IDs, patient details or exact call times to any output, even if the
  source publishes them. Air-ambulance positions are rounded to ~1 km, hidden below 1,000 ft,
  trails keep airborne points only, and takeoff/landing spots are never shown.
- **Athletes:** only what leagues publish in official injury reports, shown exactly as published.
  No speculation about anyone's condition.
- **Public data only, used legally.** Never bypass logins, auth tokens, CAPTCHAs, paywalls or
  rate limits (examples ruled out: PulsePoint, Hamilton County TN's API). Respect each source's
  terms and credit sources in the map attribution and About page. High school sports: decided
  against (no legal national source).
- **Budget ~$0.** Free tiers only (GitHub Actions on a public repo, Netlify, OpenFreeMap).
- **Secrets** (e.g. `CFBD_KEY`, `GITHUB_TOKEN` for the timer) live only in GitHub/Cloudflare
  secrets. Never print, commit or ask the owner to paste them into chat.
- Commits use the repo's no-reply email (already in local git config). Never expose the owner's email.

## How it works
1. `collect.py` (the bot) runs on GitHub Actions (`.github/workflows/collect.yml`). It reads the
   last published files from the `data` branch, runs every collector, applies the privacy step,
   then force-pushes `live.json` and `history.json` to the orphan `data` branch.
2. The site (`site/`, static HTML, deployed by Netlify from `main`) fetches
   `https://raw.githubusercontent.com/rebekahambrose/on-scene/data/live.json` (local previews read
   `site/data/live.json`).
3. GitHub's cron is unreliable (~every few hours). The fix is the Cloudflare Worker timer in
   `timer/` (setup steps in `timer/SETUP.md`, done by the owner).

## Layout
- `collectors/dispatch.py` 911 sources; each returns `(lat, lon, group)` for hex sources or
  `(place, lat, lon, group)` for area sources, and is listed in `SOURCES`.
- `collectors/aircraft.py` air ambulances (adsb.lol, one batched request per run; 500/day limit)
  and squawk 7700 (every other run, with hexdb.io + OpenSky details).
- `collectors/hazards.py` wildfires, quakes, storm reports, hurricanes, floods (slow; every 30 min,
  regional queries), air quality. `collectors/weather.py` NWS alerts.
- `collectors/sports.py` NFL injuries (nflverse), NBA injury PDF (pypdf), games (NFL schedule,
  NBA report matchups, college from `collectors/cfb_games.json`).
- `collectors/history.py` hourly and daily counts only.
- `tools/` lookup builders: places, ZIPs, airports, hospitals, air-ambulance fleet, college schedule.
- `site/` pages: `index.html` (home), `map.html` (live map; `?embed=1`, `?at=lon,lat,zoom`),
  `sideline.html`, `trends.html`, `recap.html`, `about.html`; shared `assets/style.css` and
  `assets/common.js`. **Bump the `?v=` number on those asset links whenever you change them.**

## Working on it
- Run the bot locally: `python3 collect.py` (the NBA collector needs `pip install -r requirements.txt`).
  Every source prints `ok` or `ERR`; one failing source must never stop the others.
- Preview: `cd site && python3 -m http.server 8787`, open http://localhost:8787.
- Before adding a source: confirm it is public, its terms allow reuse, it is live (newest record
  within minutes), and it works from GitHub's servers. Then add it to `SOURCES`, the README source
  table, and the About page credits if it is a new provider.
- Verify changes in a browser (desktop and phone width, no console errors, no sideways scroll)
  before pushing. Scan `site/data/live.json` for anything address-like before publishing.
- Design: mission-control look, dark navy + amber, Barlow Condensed / IBM Plex, toggle switches.

## Open items
- Owner to set up the Cloudflare timer and add the `CFBD_KEY` secret (college football).
- Optional: state 511 crash feeds need free per-state developer keys; one shared collector could
  cover the states that use the same 511 software.
- Leagues to add when in season and officially published: WNBA, MLB injured list, college
  availability reports, MLS.
