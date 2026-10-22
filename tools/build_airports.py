"""Build collectors/airports.json from OurAirports (public domain).

Used to name the airport an emergency flight took off from. Keeps large and
medium airports worldwide plus small airports that have an IATA code.

    python3 tools/build_airports.py
"""
import csv
import io
import json
import urllib.request
from pathlib import Path

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OUT = Path(__file__).resolve().parent.parent / "collectors" / "airports.json"


def main():
    text = urllib.request.urlopen(URL, timeout=300).read().decode("utf-8", errors="replace")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r["type"] in ("large_airport", "medium_airport") or (r["type"] == "small_airport" and r["iata_code"]):
            code = r["iata_code"] or r["icao_code"] or r["gps_code"] or r["ident"]
            out.append([round(float(r["latitude_deg"]), 4), round(float(r["longitude_deg"]), 4), r["name"], code])
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(out)} airports written to {OUT}")


if __name__ == "__main__":
    main()
