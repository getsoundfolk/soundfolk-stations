#!/usr/bin/env python3
"""Checks that each station's website still links to its donation page.

Usage (from anywhere; Python 3.11+, no dependencies):
  python3 scripts/check_links.py stations/<id>.toml ...
      Checks these entries and exits 1 if one fails (pull requests).
  python3 scripts/check_links.py --daily <previous status.json> -o <status.json> [--issues <issues.json>]
      Checks every entry and writes the new status: which links are left out of the published list,
      and since when. `previous` may be missing or empty (first run).

A failure is one of:
  missing   `found_on` answers but no longer links to `donate.url` (moved, redesigned, removed)
  gone      `found_on` or `donate.url` answers 404 or 410
  dead      no answer at all from `found_on` or `donate.url` (DNS, connection, TLS, timeout)
  redirect  `donate.url` now redirects to a domain that is neither the station's nor a platform's

Every failure leaves the link out of the list at once; it comes back by itself once the check passes
again. An issue is opened at once for `dead` and `redirect`, after ISSUE_AFTER days for the others.
If more than GUARD of the links fail the same day (and there are at least GUARD_MIN), the problem is
on this side (blocked runner, network): nothing new is left out and one issue says so.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from common import FetchError, ROOT, allowed_donation, entries, fetch, host, links_to, load, platforms

ISSUE_AFTER = datetime.timedelta(days=7)
GUARD = 0.20
GUARD_MIN = 10
URGENT = {"dead", "redirect"}


def check(entry: dict, allowed: list[str]) -> tuple[str, str] | None:
    """None when the link is fine, else (kind, reason)."""
    url = entry["donate"]["url"]
    found_on = entry["donate"]["found_on"]
    try:
        page = fetch(found_on)
    except FetchError as e:
        return "dead", f"{found_on} does not answer: {e}"
    if page.status in (404, 410):
        return "gone", f"{found_on} answers {page.status}"
    if page.status >= 400:
        # 403, 429, 5xx: often a bot filter or a passing outage, not the station's doing.
        return "missing", f"{found_on} answers {page.status}"
    if not links_to(page, url):
        return "missing", f"{found_on} no longer links to {url}"
    try:
        target = fetch(url, read_body=False)
    except FetchError as e:
        return "dead", f"{url} does not answer: {e}"
    if target.status in (404, 410):
        return "gone", f"{url} answers {target.status}"
    if not allowed_donation(target.url, entry["homepage"], allowed):
        return "redirect", f"{url} now leads to {host(target.url)}"
    return None


def check_files(paths: list[str]) -> int:
    allowed = platforms()
    failed = 0
    for name in paths:
        entry, error = load(Path(name))
        if entry is None:
            print(f"FAIL  {name}: not valid TOML: {error}")
            failed += 1
            continue
        result = check(entry, allowed)
        if result:
            failed += 1
            print(f"FAIL  {name}: {result[1]}")
        else:
            print(f"ok    {name}: {entry['donate']['found_on']} links to {entry['donate']['url']}")
    return 1 if failed else 0


def daily(previous_path: Path, out: Path, issues_out: Path | None) -> int:
    try:
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    before = previous.get("failing", {}) if isinstance(previous, dict) else {}
    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    allowed = platforms()

    all_entries = entries()
    results = {}
    for station_id, entry in all_entries:
        results[station_id] = check(entry, allowed)
        print(f"{'FAIL' if results[station_id] else 'ok  '}  {station_id}"
              + (f": {results[station_id][1]}" if results[station_id] else ""))

    failed = [i for i, r in results.items() if r]
    issues = []
    guard = len(all_entries) >= GUARD_MIN and len(failed) > GUARD * len(all_entries)
    failing = {}
    if guard:
        # Today's failures can't be trusted, but a passing link can: keep out only what was out
        # yesterday and still fails.
        failing = {i: v for i, v in before.items() if results.get(i)}
        issues.append({
            "id": "link-check",
            "title": "Link check: too many failures",
            "body": f"{len(failed)} of {len(all_entries)} links failed on {now.date()}: nothing new was "
                    "left out of the list. Check the runner first (blocked, network).\n\n"
                    + "\n".join(f"* `{i}`: {results[i][1]}" for i in failed),
        })
    else:
        for station_id in failed:
            kind, reason = results[station_id]
            since = before.get(station_id, {}).get("since", now.isoformat())
            failing[station_id] = {"since": since, "kind": kind, "reason": reason}
            age = now - datetime.datetime.fromisoformat(since)
            if kind in URGENT or age >= ISSUE_AFTER:
                issues.append({
                    "id": station_id,
                    "title": f"Broken link: {station_id}",
                    "body": f"`stations/{station_id}.toml` has been left out of the published list since "
                            f"{since[:10]}.\n\n{reason}\n\nFix `donate.url` or `donate.found_on`, or remove "
                            "the entry. The link comes back by itself as soon as the check passes.",
                })

    status = {"version": 1, "checked_at": now.isoformat(), "failing": failing}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if issues_out:
        issues_out.write_text(json.dumps(issues, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(all_entries)} link(s), {len(failed)} failed today, {len(failing)} left out"
          + (" (too many failures: nothing new left out)" if guard else ""))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*")
    parser.add_argument("--daily", type=Path, metavar="PREVIOUS")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "site" / "v1" / "status.json")
    parser.add_argument("--issues", type=Path)
    args = parser.parse_args()
    if args.daily:
        return daily(args.daily, args.output, args.issues)
    if not args.files:
        parser.error("give entries to check, or --daily")
    return check_files(args.files)


if __name__ == "__main__":
    sys.exit(main())
