"""Build site/hospitals.json: every Medicare-listed hospital with an emergency department.

Source: CMS Hospital General Information (public domain). Addresses are public
facility addresses, geocoded once with the Census Bureau batch geocoder.
Run this a few times a year; the map loads the file directly.

    python3 tools/build_hospitals.py
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collectors.common import geocode  # noqa: E402

API = "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0?limit=500&offset={}"
OUT = Path(__file__).resolve().parent.parent / "site" / "hospitals.json"


def main():
    rows, offset = [], 0
    while True:
        page = json.load(urllib.request.urlopen(API.format(offset), timeout=120))["results"]
        rows += page
        offset += len(page)
        if len(page) < 500:
            break
    er = [r for r in rows if r.get("emergency_services") == "Yes"]
    print(f"{len(rows)} hospitals, {len(er)} with emergency services")
    found = {}
    for start in range(0, len(er), 2000):  # the geocoder takes up to 10,000 per batch; smaller batches finish sooner
        chunk = er[start:start + 2000]
        hits = geocode([(r["address"], r["citytown"], r["state"]) for r in chunk])
        found.update({start + i: ll for i, ll in hits.items()})
        print(f"  geocoded {len(found)} so far")
    features = []
    for i, r in enumerate(er):
        if i not in found:
            continue
        lat, lon = found[i]
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
                         "properties": {"name": r["facility_name"].title(), "city": f"{r['citytown'].title()}, {r['state']}",
                                        "type": r["hospital_type"], "phone": r["telephone_number"]}})
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"{len(features)} hospitals written to {OUT}")


if __name__ == "__main__":
    main()
