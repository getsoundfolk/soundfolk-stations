#!/usr/bin/env python3
"""Compiles lists/ into the file the app downloads, without the stations that fail today.

Usage: python3 scripts/compile_lists.py --status site/v1/lists-status.json [-o site/v1/lists.json]

The status, from check_lists.py --daily, gives each station's stream and country as Radio-Browser
has them today. The file holds what the app needs and nothing else (`checked` stays here):

  {"version": 1, "lists": [{"id", "title", "description", "curators", "use", "genres", "countries",
                            "items": [{"uuid", "stream"}]}]}

Lists are sorted by id (the app sorts them by title); items keep the curator's order. `countries`
holds each country of at least COUNTRY_SHARE of the list's stations. `version` moves only for a
change older apps can't read; new optional keys keep it.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

from common import ROOT, lists

COUNTRY_SHARE = 0.20

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--status", type=Path, required=True, help="lists-status.json from check_lists.py --daily")
parser.add_argument("-o", "--output", type=Path, default=ROOT / "site" / "v1" / "lists.json")
args = parser.parse_args()

status = json.loads(args.status.read_text(encoding="utf-8"))
known, failing = status.get("stations", {}), status.get("failing", {})

published, left_out = [], 0
for list_id, entry in lists():
    stations = [known[u] | {"uuid": u} for u in entry["stations"] if u in known]
    counts = collections.Counter(s["country"] for s in stations if s["country"])
    countries = sorted(c for c, n in counts.items() if stations and n / len(stations) >= COUNTRY_SHARE)
    items = []
    for uuid in entry["stations"]:
        if uuid in failing or uuid not in known:
            left_out += 1
            continue
        item = {"uuid": uuid}
        if known[uuid]["stream"]:
            item["stream"] = known[uuid]["stream"]
        items.append(item)
    published.append({
        "id": list_id,
        "title": entry["title"],
        "description": entry["description"],
        "curators": entry["curators"],
        "use": entry["use"],
        "genres": entry["genres"],
        "countries": countries,
        "items": items,
    })

args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(
    json.dumps({"version": 1, "lists": published}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(f"ok    {len(published)} list(s) in {args.output.name}, "
      f"{sum(len(p['items']) for p in published)} station(s), {left_out} left out")
sys.exit(0)
