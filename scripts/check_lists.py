#!/usr/bin/env python3
"""Looks up every station of the lists in Radio-Browser and checks that its stream answers.

Usage (from anywhere; Python 3.11+, no dependencies):
  python3 scripts/check_lists.py lists/<id>.toml ...
      Prints each station's Radio-Browser name, country and stream, for the reviewer of a pull
      request, and exits 1 if a UUID is not in Radio-Browser.
  python3 scripts/check_lists.py --daily <previous lists-status.json> -o <lists-status.json> [--issues <issues.json>]
      Checks every list and writes the status compile.py publishes from: each station's stream and
      country, and which stations are left out, since when. `previous` may be missing or empty.

A UUID no longer in Radio-Browser is often a station still there under another UUID: Radio-Browser
deletes duplicates and keeps one copy. The status keeps the last stream known for every station, so
when a UUID disappears, the Radio-Browser copy playing that same stream stands in for it in the
published list (the one with the same name first, then a working one, then the most voted). It
stays in until the UUID comes back or the copy goes too. Nobody is asked anything and the source file
does not change: a copy playing the same stream plays the same thing.

A station fails when:
  gone  its UUID is no longer in Radio-Browser and no copy plays its last known stream
  dead  its stream does not answer from here and Radio-Browser's own check fails too: a stream
        blocked outside its country answers Radio-Browser's checkers, and stays in

A failing station is left out of the published list at once and comes back by itself once the
check passes again; the source file does not change. An issue is opened for the list at once for
`gone`, after ISSUE_AFTER days for `dead`, and when the list has fewer than MIN_ITEMS stations left.
If more than GUARD of the stations fail the same day (and there are at least GUARD_MIN), the problem
is on this side: nothing new is left out and one issue says so. A copy standing in is not a failure.
A year after `checked`, an issue asks the curators to review the list.
"""

import argparse
import concurrent.futures
import datetime
import http.client
import json
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

from common import FetchError, ROOT, USER_AGENT, lists, load, name_key, radio_browser, stream_key

ISSUE_AFTER = datetime.timedelta(days=7)
REVIEW_AFTER = datetime.timedelta(days=365)
GUARD = 0.20
GUARD_MIN = 10
MIN_ITEMS = 5
STREAM_TIMEOUT = 15
BATCH = 50


def lookup(uuids: list[str]) -> dict[str, dict]:
    """Radio-Browser's entry of each UUID it knows."""
    found = {}
    for i in range(0, len(uuids), BATCH):
        for station in radio_browser("byuuid", uuids=",".join(uuids[i:i + BATCH])):
            found[station["stationuuid"]] = station
    return found


def last_known(uuid: str, previous: dict) -> dict | None:
    """What yesterday's status knew of this station (name, stream, urls), if it knew its stream."""
    stations = previous.get("stations", {})
    standing_in = previous.get("replaced", {}).get(uuid, {}).get("by")
    for known in (stations.get(standing_in), stations.get(uuid), previous.get("replaced", {}).get(uuid),
                  previous.get("lost", {}).get(uuid), previous.get("failing", {}).get(uuid)):
        if isinstance(known, dict) and known.get("stream"):
            return {"name": known.get("name", ""), "stream": known["stream"], "urls": known.get("urls", [])}
    return None


def same_stream(known: dict) -> list[dict]:
    """The Radio-Browser stations playing this stream, the best stand-in first."""
    urls = list(dict.fromkeys(known["urls"] + [f"https://{known['stream']}", f"http://{known['stream']}"]))
    found = {}
    for url in urls:
        for station in radio_browser("byurl", url=url):
            found[station["stationuuid"]] = station
    playing = [s for s in found.values()
               if known["stream"] in {stream_key(u) for u in (s.get("url"), s.get("url_resolved")) if u}]
    name = name_key(known["name"])
    return sorted(playing, key=lambda s: (name_key(s.get("name") or "") != name, s.get("lastcheckok") != 1,
                                          -(s.get("votes") or 0), -(s.get("clickcount") or 0), s["stationuuid"]))


def answers(url: str) -> str | None:
    """None when the stream sends something, else why not."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Icy-MetaData": "0"})
    try:
        with urllib.request.urlopen(request, timeout=STREAM_TIMEOUT) as response:
            if not response.read(4096):
                return "the stream sends nothing"
            return None
    except urllib.error.HTTPError as e:
        return f"the stream answers {e.code}"
    except http.client.BadStatusLine as e:
        # Old Shoutcast servers answer `ICY 200 OK`, which urllib refuses: the stream is there.
        return None if str(e).startswith("ICY 200") else f"the stream answers {str(e)[:60]!r}"
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, ValueError,
            http.client.HTTPException) as e:
        return f"the stream does not answer: {str(getattr(e, 'reason', e))[:100]}"


def check(uuids: list[str]) -> tuple[dict[str, dict], dict[str, tuple[str, str]]]:
    """Each known station's name, country and stream, and the failing ones as (kind, reason)."""
    known = lookup(uuids)
    info, failed = {}, {}
    for uuid in uuids:
        station = known.get(uuid)
        if station is None:
            failed[uuid] = ("gone", f"{uuid} is no longer in Radio-Browser")
            continue
        url = station.get("url_resolved") or station.get("url") or ""
        info[uuid] = {
            "name": (station.get("name") or "").strip(),
            "country": (station.get("countrycode") or "").upper(),
            "stream": stream_key(url) if url else "",
            "url": url,
            "urls": list(dict.fromkeys(u for u in (station.get("url"), station.get("url_resolved")) if u)),
            "rb_ok": station.get("lastcheckok") == 1,
        }
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        probes = dict(zip(info, pool.map(lambda u: answers(info[u]["url"]) if info[u]["url"] else "no stream",
                                         info)))
    for uuid, problem in probes.items():
        if problem and not info[uuid]["rb_ok"]:
            failed[uuid] = ("dead", f"{info[uuid]['name']}: {problem}, and Radio-Browser's check fails too")
        info[uuid]["answers"] = problem is None
    return info, failed


def check_files(paths: list[str]) -> int:
    loaded = []
    for name in paths:
        entry, error = load(Path(name))
        if entry is None:
            print(f"FAIL  {name}: not valid TOML: {error}")
            return 1
        loaded.append((name, [u for u in entry.get("stations", []) if isinstance(u, str)]))
    uuids = sorted({u for _, us in loaded for u in us})
    try:
        info, failed = check(uuids)
    except FetchError as e:
        print(f"FAIL  Radio-Browser: {e}")
        return 1
    bad = 0
    for name, us in loaded:
        print(f"## {name}\n")
        print("| # | Radio-Browser name | Country | Stream | |\n|---|---|---|---|---|")
        for n, uuid in enumerate(us, 1):
            if uuid not in info:
                bad += 1
                print(f"| {n} | `{uuid}` | | | not in Radio-Browser |")
                continue
            s = info[uuid]
            state = "answers" if s["answers"] else ("fails, but Radio-Browser reaches it" if uuid not in failed
                                                    else "**fails**")
            print(f"| {n} | {s['name']} | {s['country']} | `{s['stream']}` | {state} |")
        print()
    return 1 if bad else 0


def daily(previous_path: Path, out: Path, issues_out: Path | None) -> int:
    try:
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    before = previous.get("failing", {}) if isinstance(previous, dict) else {}
    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)

    if not isinstance(previous, dict):
        previous = {}

    all_lists = lists()
    uuids = sorted({u for _, entry in all_lists for u in entry["stations"]})

    # Which Radio-Browser station stands for each UUID of the lists: itself, or a copy playing its stream.
    standing = {u: r["by"] for u, r in previous.get("replaced", {}).items() if u in uuids and "by" in r}
    present = lookup(sorted(set(uuids) | set(standing.values())))
    effective, replaced, lost, gone = {}, {}, {}, {}
    for uuid in uuids:
        if uuid in present:
            effective[uuid] = uuid
            continue
        before_rep = previous.get("replaced", {}).get(uuid, {})
        known = last_known(uuid, previous)
        if standing.get(uuid) in present:
            copy = standing[uuid]
        else:
            copies = same_stream(known) if known else []
            copy = copies[0]["stationuuid"] if copies else None
        if copy is None:
            gone[uuid] = ("gone", f"{uuid} is no longer in Radio-Browser, and no copy plays "
                                  + (f"its stream `{known['stream']}`" if known else "its stream (unknown here)"))
            if known:
                lost[uuid] = known
            continue
        effective[uuid] = copy
        replaced[uuid] = (known or {}) | {
            "by": copy,
            "since": before_rep.get("since", now.isoformat()) if before_rep.get("by") == copy else now.isoformat(),
        }
        if before_rep.get("by") != copy:
            print(f"MOVED {uuid} -> {copy}: same stream `{replaced[uuid].get('stream', '')}`")

    info, failed_now = check(sorted(set(effective.values())))
    failed = dict(gone)
    for uuid, copy in effective.items():
        if copy in failed_now:
            failed[uuid] = failed_now[copy]
    for uuid in uuids:
        if uuid in failed:
            print(f"FAIL  {uuid}: {failed[uuid][1]}")

    issues = []
    guard = len(uuids) >= GUARD_MIN and len(failed) > GUARD * len(uuids)
    if guard:
        failing = {u: v for u, v in before.items() if u in failed}
        issues.append({
            "id": "list-check",
            "title": "List check: too many failures",
            "body": f"{len(failed)} of {len(uuids)} stations of the lists failed on {now.date()}: nothing new was "
                    "left out. Check the runner first (blocked, network).\n\n"
                    + "\n".join(f"* `{u}`: {failed[u][1]}" for u in sorted(failed)),
        })
    else:
        failing = {}
        for uuid, (kind, reason) in failed.items():
            since = before.get(uuid, {}).get("since", now.isoformat())
            failing[uuid] = {"since": since, "kind": kind, "reason": reason}

    for list_id, entry in all_lists:
        curator = entry["curators"][0]
        out_here = [u for u in entry["stations"] if u in failing]
        urgent = [u for u in out_here if failing[u]["kind"] == "gone"
                  or now - datetime.datetime.fromisoformat(failing[u]["since"]) >= ISSUE_AFTER]
        left = len(entry["stations"]) - len(out_here)
        if urgent or left < MIN_ITEMS:
            lines = [f"* `{u}` ({failing[u]['kind']} since {failing[u]['since'][:10]}): {failing[u]['reason']}"
                     for u in out_here]
            issues.append({
                "id": list_id,
                "title": f"List: {list_id}",
                "body": f"@{curator}, {len(out_here)} station(s) of `lists/{list_id}.toml` are left out of the "
                        f"published list ({left} published).\n\n" + "\n".join(lines) + "\n\n"
                        "A station *gone* from Radio-Browser, with no copy playing its stream, needs its new "
                        "UUID or to be removed; a *dead* one "
                        "comes back by itself as soon as its stream answers again. Without an answer from the "
                        "curators within 30 days, the maintainer fixes the list, takes it over or unpublishes it.",
            })
        checked = entry["checked"]
        if now.date() - checked >= REVIEW_AFTER:
            issues.append({
                "id": f"review-{list_id}",
                "title": f"Yearly review: {list_id}",
                "label": "list-review",
                "body": f"@{curator}, `lists/{list_id}.toml` was last reviewed on {checked}. The daily check "
                        "cannot hear everything: a station bought or changing format, a show the list was built "
                        "around that ended. Listen through it, change what needs to, and set `checked` to "
                        "today's date. Left unanswered, this changes nothing in the app.",
            })

    status = {
        "version": 1,
        "checked_at": now.isoformat(),
        "stations": {u: {k: info[u][k] for k in ("name", "country", "stream", "urls")} for u in sorted(info)},
        "replaced": {u: replaced[u] for u in sorted(replaced)},
        "lost": {u: lost[u] for u in sorted(lost)},
        "failing": failing,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if issues_out:
        issues_out.write_text(json.dumps(issues, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(all_lists)} list(s), {len(uuids)} station(s), {len(replaced)} played through a copy, "
          f"{len(failed)} failed today, {len(failing)} left out"
          + (" (too many failures: nothing new left out)" if guard else ""))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*")
    parser.add_argument("--daily", type=Path, metavar="PREVIOUS")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "site" / "v1" / "lists-status.json")
    parser.add_argument("--issues", type=Path)
    args = parser.parse_args()
    if args.daily:
        try:
            return daily(args.daily, args.output, args.issues)
        except FetchError as e:
            print(f"FAIL  Radio-Browser: {e}")
            return 1
    if not args.files:
        parser.error("give lists to check, or --daily")
    return check_files(args.files)


if __name__ == "__main__":
    sys.exit(main())
