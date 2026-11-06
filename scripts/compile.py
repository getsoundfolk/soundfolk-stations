#!/usr/bin/env python3
"""Compiles stations/ into the list the app downloads, without the links that fail today.

Usage: python3 scripts/compile.py [--status site/v1/status.json] [-o site/v1/stations.json]

The list holds what the app needs and nothing else (`homepage` and `found_on` stay here):

  {"version": 1, "stations": [{"id", "name", "match": {"stations", "streams"?}, "donate"}]}

`version` moves only for a change older apps can't read; new optional keys keep it.
"""

import argparse
import json
import sys
from pathlib import Path

from common import ROOT, entries

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--status", type=Path, help="status.json from check_links.py --daily (optional)")
parser.add_argument("-o", "--output", type=Path, default=ROOT / "site" / "v1" / "stations.json")
args = parser.parse_args()

failing = {}
if args.status:
    try:
        failing = json.loads(args.status.read_text(encoding="utf-8")).get("failing", {})
    except (OSError, ValueError):
        failing = {}

stations = []
for station_id, entry in entries():
    if station_id in failing:
        continue
    match = {"stations": entry["match"]["stations"]}
    if entry["match"].get("streams"):
        match["streams"] = entry["match"]["streams"]
    stations.append({"id": station_id, "name": entry["name"], "match": match, "donate": entry["donate"]["url"]})

args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(
    json.dumps({"version": 1, "stations": stations}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(f"ok    {len(stations)} station(s) in {args.output.name}, {len(failing)} left out")
sys.exit(0)
