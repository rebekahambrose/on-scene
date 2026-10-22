"""Build collectors/places.json: center points for towns that area-level sources name.

Uses the Census Bureau's public gazetteer of county subdivisions (townships,
boroughs, cities). Add a county's 5-digit FIPS code to COUNTIES when a new
area-level source needs it.

    python3 tools/build_places.py
"""
import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

GAZETTEER = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_cousubs_national.zip"
OUT = Path(__file__).resolve().parent.parent / "collectors" / "places.json"

COUNTIES = {
    "42071": "Lancaster County, PA",
    "42043": "Dauphin County, PA",
}
# Census place centroids for city-wide sources (from the 2024 places gazetteer).
EXTRA = {
    "SAN DIEGO CITY, CA": [32.8153, -117.135],
}


def main():
    data = urllib.request.urlopen(GAZETTEER, timeout=300).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.endswith(".txt"))
        text = z.read(name).decode("utf-8", errors="replace")
    places = dict(EXTRA)
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        row = {k.strip(): v.strip() for k, v in row.items() if k}
        if row["GEOID"][:5] in COUNTIES:
            places[f"{row['NAME'].upper()}, {row['USPS']}"] = [round(float(row["INTPTLAT"]), 4), round(float(row["INTPTLONG"]), 4)]
    OUT.write_text(json.dumps(places, indent=0, sort_keys=True))
    print(f"{len(places)} places written to {OUT}")


if __name__ == "__main__":
    main()
