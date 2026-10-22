# On Scene

A live map of emergency response across the US, built only from public data.

## How it works

1. **The bot** (`collect.py`) runs every 5 minutes on GitHub Actions. It pulls every source in `collectors/`.
2. **The privacy step** happens inside the bot, before anything is saved:
   - Dispatches with coordinates are snapped to hexes about 800 m across. The exact point is thrown away.
   - Dispatches with only a street or town are counted by town.
   - Addresses, unit names, patient details and exact times are never written out.
   - Air-ambulance positions are rounded to about 1 km and hidden below 1,000 ft. Tail numbers are not published.
3. The bot writes one file, `site/data/live.json`, and pushes it to the `data` branch.
4. **The map** (`site/index.html`) reads that file and refreshes every minute.

## Sources

| Layer | Source | Freshness | How it's placed |
|---|---|---|---|
| Dispatch | Seattle Fire Dept (data.seattle.gov) | live, past 2 hours | hex |
| Dispatch | Austin Fire Dept (data.austintexas.gov) | live, past 2 hours | hex |
| Dispatch | Austin traffic crashes (data.austintexas.gov) | live, past 2 hours | hex |
| Dispatch | Pinellas County 911 (911.pinellas.gov) | active calls | hex (county grid) |
| Dispatch | Milwaukee Fire Dept (itmdapps.milwaukee.gov) | past 15–105 min | hex via Census geocoder, else city |
| Dispatch | San Diego Fire-Rescue (webapps.sandiego.gov) | active calls | city |
| Dispatch | City of Houston Active Incidents (fire, EMS, crashes) | active calls | city |
| Dispatch | Nashville Fire Dept (ArcGIS) | active calls | ZIP code |
| Dispatch | Lancaster County-Wide Communications RSS | active calls | township |
| Dispatch | Dauphin County WebCAD | active calls | township |
| Dispatch | Montgomery County PA WebCAD RSS | active calls | township |
| Dispatch | Hernando County Sheriff (Fire Rescue calls) | active calls | county |
| Aircraft | adsb.lol air-ambulance helicopters (ODbL) + FAA registry | live | ~1 km |
| Aircraft | adsb.lol aircraft squawking 7700 | every 10 min | ~1 km |
| Sideline | NFL official injury report (via nflverse) | daily in season | team stadium |
| Hazards | NIFC wildfires 100+ acres | live | fire location |
| Hazards | USGS earthquakes M2.5+, past day | live | epicenter |
| Hazards | NWS Local Storm Reports, past 6 hours (Iowa Mesonet) | live | ~1 km |
| Weather | National Weather Service alerts | live | alert area |

The full catalog of possible sources lives at https://claude.ai/artifact/2Drsf6H7eUA7dvCdPqcGbW

## Adding a source

1. Write a function in `collectors/dispatch.py` that returns `(lat, lon, group)` per call, or `(place, lat, lon, group)` for town-level sources.
2. Add it to `SOURCES` at the bottom of that file.
3. For town-level sources, add the county's FIPS code to `tools/build_places.py` and run it.
4. Run `python3 collect.py` and check the source shows `ok`.

## Running it locally

```bash
python3 collect.py
cd site && python3 -m http.server 8787
```

Then open http://localhost:8787.

## Upkeep

- `tools/build_hems_list.py` refreshes the air-ambulance list weekly (its own workflow).
- GitHub pauses scheduled workflows in a repo with no commits for 60 days. If the map stops updating, re-enable "Collect live data" under the Actions tab.
- County pages change without notice. A broken source shows as "down" on the map while the others keep running.

Not an emergency service. In an emergency, call 911.
