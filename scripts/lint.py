#!/usr/bin/env python3
"""The rules of every entry in stations/, without going online.

Usage: python3 scripts/lint.py   (from anywhere; Python 3.11+, no dependencies)
"""

import sys

from common import ID, SCHEMA_LINE, STATIONS, ROOT, entry_errors, load, platforms

errors: list[str] = []
allowed = platforms()
for domain in allowed:
    if domain != domain.lower() or "/" in domain or domain.startswith("www."):
        errors.append(f"platforms.toml: {domain!r} must be a lowercase domain, without www. or a path")

streams: dict[str, str] = {}
stations: dict[str, str] = {}
count = 0
for path in sorted(STATIONS.iterdir()) if STATIONS.is_dir() else []:
    name = path.relative_to(ROOT)
    if path.name.startswith("."):
        continue
    if path.suffix != ".toml":
        errors.append(f"{name}: only <id>.toml files belong in stations/")
        continue
    count += 1
    if not ID.match(path.stem):
        errors.append(f"{name}: file names are lowercase letters, digits, `-` and `_` (at most 64)")
    entry, text = load(path)
    if entry is None:
        errors.append(f"{name}: not valid TOML: {text}")
        continue
    if text.splitlines()[:1] != [SCHEMA_LINE]:
        errors.append(f"{name}: the first line must be `{SCHEMA_LINE}`")
    errors += [f"{name}: {e}" for e in entry_errors(entry, allowed)]

    match = entry.get("match") if isinstance(entry.get("match"), dict) else {}
    for stream in match.get("streams", []) if isinstance(match.get("streams"), list) else []:
        key = str(stream).strip().lower().rstrip("/")
        if key in streams:
            errors.append(f"{name}: stream {stream!r} is already matched by {streams[key]}")
        streams[key] = path.name
    for uuid in match.get("stations", []) if isinstance(match.get("stations"), list) else []:
        key = str(uuid).strip().lower()
        if key in stations:
            errors.append(f"{name}: station {uuid!r} is already matched by {stations[key]}")
        stations[key] = path.name

if errors:
    print("\n".join(f"FAIL  {e}" for e in errors))
    sys.exit(1)
print(f"ok    {count} station(s), {len(allowed)} platform(s)")
