"""Build the list of air-ambulance helicopters from the FAA aircraft registry.

Run weekly. Downloads the public FAA registry, keeps rotorcraft whose registered
owner is an air-medical operator or a hospital, and writes their transponder
(Mode S) hex codes to collectors/hems.json. Aircraft owned by banks or leasing
trusts are missed; that is a known gap.

    python3 tools/build_hems_list.py [path/to/ReleasableAircraft.zip]
"""
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

REGISTRY = "https://registry.faa.gov/database/ReleasableAircraft.zip"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
OUT = Path(__file__).resolve().parent.parent / "collectors" / "hems.json"

OWNER = re.compile(
    r"AIR METHODS|AIR EVAC|PHI HEALTH|MED-TRANS|MED TRANS|METRO AVIATION|REACH AIR|LIFE ?FLIGHT|GUARDIAN FLIGHT"
    r"|AIR MEDICAL|AIRMEDICAL|MEDICAL|HOSPITAL|HEALTH|CAREFLITE|CARE FLIGHT|LIFE ?STAR|LIFE ?NET|LIFE ?GUARD|AIR ?LIFE"
    r"|MEDSTAR|MERCY|CALSTAR|MEDEVAC|MED EVAC|SHOCK TRAUMA|TRAUMA|AEROMED|STAT MEDEVAC|LIFELINE|ANGEL ?ONE"
)


def main():
    if len(sys.argv) > 1:
        data = Path(sys.argv[1]).read_bytes()
    else:
        req = urllib.request.Request(REGISTRY, headers={"User-Agent": BROWSER_UA})
        data = urllib.request.urlopen(req, timeout=600).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = z.read("MASTER.txt").decode("utf-8-sig", errors="replace")
    rows = csv.reader(io.StringIO(text))
    head = [h.strip() for h in next(rows)]
    col = {h: i for i, h in enumerate(head)}
    hexes = set()
    for row in rows:
        if len(row) < len(head) - 1 or row[col["TYPE AIRCRAFT"]].strip() != "6":
            continue
        owner = row[col["NAME"]].strip()
        if OWNER.search(owner):
            code = row[col["MODE S CODE HEX"]].strip().lower()
            if code:
                hexes.add(code)
    OUT.write_text(json.dumps(sorted(hexes)))
    print(f"{len(hexes)} air-ambulance helicopters written to {OUT}")


if __name__ == "__main__":
    main()
