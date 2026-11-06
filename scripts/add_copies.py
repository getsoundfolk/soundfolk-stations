#!/usr/bin/env python3
"""Adds to every entry the Radio-Browser copies of its station that it doesn't match yet.

Usage: python3 scripts/add_copies.py   (from anywhere; Python 3.11+, no dependencies)

Same rule as the issue bot: same name, website on the same domain as `homepage`. A copy already
matched by another entry is left alone. Rewrites the files it changes, and lists them: review the
diff before committing.
"""

import sys

from common import STATIONS, FetchError, copies, entries, write_entry

taken = {u: i for i, e in entries() for u in e["match"]["stations"]}
changed = 0
for station_id, entry in entries():
    try:
        found = copies(entry["name"], entry["homepage"])
    except FetchError as e:
        print(f"FAIL  {station_id}: {e}")
        continue
    added = [u for u in found if u not in taken]
    if not added:
        continue
    entry["match"]["stations"] = entry["match"]["stations"] + added
    for u in added:
        taken[u] = station_id
    write_entry(STATIONS / f"{station_id}.toml", entry)
    changed += 1
    print(f"added {station_id}: {', '.join(added)}")
print(f"ok    {changed} entr{'y' if changed == 1 else 'ies'} changed")
sys.exit(0)
