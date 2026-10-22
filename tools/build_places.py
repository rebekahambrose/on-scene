"""Build the lookup tables that place area-level calls on the map.

collectors/places.json  town centers for counties whose feeds name a township or borough
collectors/zips.json    ZIP code centers, for feeds that give only a ZIP

Both come from the Census Bureau's public gazetteer files. Add a county's
5-digit FIPS code to COUNTIES when a new town-level source needs it.

    python3 tools/build_places.py
"""
import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/"
HERE = Path(__file__).resolve().parent.parent / "collectors"

COUNTIES = {
    "42071": "Lancaster County, PA",
    "42043": "Dauphin County, PA",
    "42091": "Montgomery County, PA",
}
# Center points for sources that report a whole city or county.
EXTRA = {
    "SAN DIEGO CITY, CA": [32.8153, -117.135],
    "HOUSTON CITY, TX": [29.7863, -95.3889],
    "MILWAUKEE CITY, WI": [43.0633, -87.9667],
    "HERNANDO COUNTY, FL": [28.5541, -82.4237],
}


def gazetteer(name):
    data = urllib.request.urlopen(BASE + name, timeout=300).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = z.read(next(n for n in z.namelist() if n.endswith(".txt"))).decode("utf-8", errors="replace")
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        yield {k.strip(): v.strip() for k, v in row.items() if k}


def main():
    places = dict(EXTRA)
    for row in gazetteer("2024_Gaz_cousubs_national.zip"):
        if row["GEOID"][:5] in COUNTIES:
            places[f"{row['NAME'].upper()}, {row['USPS']}"] = [round(float(row["INTPTLAT"]), 4), round(float(row["INTPTLONG"]), 4)]
    (HERE / "places.json").write_text(json.dumps(places, indent=0, sort_keys=True))
    print(f"{len(places)} places")

    zips = {row["GEOID"]: [round(float(row["INTPTLAT"]), 3), round(float(row["INTPTLONG"]), 3)]
            for row in gazetteer("2024_Gaz_zcta_national.zip")}
    (HERE / "zips.json").write_text(json.dumps(zips, separators=(",", ":"), sort_keys=True))
    print(f"{len(zips)} ZIP codes")


if __name__ == "__main__":
    main()
