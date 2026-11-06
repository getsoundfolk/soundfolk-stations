#!/usr/bin/env python3
"""Writes the entry of an "Add a donation link" issue into stations/<id>.toml.

Usage: python3 scripts/from_issue.py <event.json> [--summary <file.md>]   (from the repository root)

Prints `id=<id>` and `change=new|link|homepage|copies|same` for $GITHUB_OUTPUT, and writes what the
maintainer must look at into the summary. Exits 1 with the reason on stderr when the issue can't be
used, 2 when the link is fine but the station's website doesn't give it: only the maintainer can
then add it, checked by hand (`checked_by_hand`). The issue body is untrusted: it is only parsed,
checked, and written to that one file.

1. The station comes from Radio-Browser, by the UUID in the issue: name and, unless the issue gives
   one, website. An entry that already matches the UUID is updated in place (same id).
2. A HelloAsso link to an embedded form becomes the form's page.
3. The donation link must be found on the station's website: on its homepage, or on one of a few
   pages of the same site whose link looks like a donation page. That page becomes `found_on`.
   An entry checked by hand becomes an ordinary one as soon as the website gives the link.
4. Radio-Browser's other copies of the station (same name, website on the same domain) are added to
   `match.stations`: the app may show any of them.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

from common import (
    ID, STATIONS, UUID, FetchError, allowed_donation, copies, entries, entry_errors, fetch, form_page, links,
    links_to, on_domain, platforms, radio_browser, site, url_errors, write_entry,
)

RECIPES = "https://getsoundfolk.github.io/soundfolk-recipes/v1/recipes.json"
MAX_PAGES = 10
DONATION_WORDS = re.compile(
    r"don|donat|soutien|soutenir|adh[eé]r|support|spend|unterst[uü]tz|dona|apoy|helloasso|tipeee|patreon"
    r"|liberapay|ko-fi|opencollective|donorbox",
    re.I,
)


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def sections(body: str) -> dict[str, str]:
    """`### Heading` → content, as GitHub renders issue forms."""
    found: dict[str, str] = {}
    parts = re.split(r"^### (.+)$", body.replace("\r\n", "\n"), flags=re.M)
    for heading, content in zip(parts[1::2], parts[2::2]):
        text = content.strip()
        found[heading.strip()] = "" if text == "_No response_" else text
    return found


def get_json(url: str):
    page = fetch(url)
    if page.status != 200:
        raise FetchError(f"{url} answered {page.status}")
    return json.loads(page.body)


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:64].strip("-") or "station"


def recipe_id(uuid: str) -> str | None:
    """The id of the shared recipe for this station, if any: the same id helps people find both."""
    try:
        recipes = get_json(RECIPES).get("recipes", [])
    except (FetchError, ValueError, AttributeError):
        return None
    for recipe in recipes:
        if uuid in recipe.get("match", {}).get("stations", []):
            return recipe.get("id")
    return None


def find_link(homepage: str, url: str) -> str | None:
    """The page of the station's website that links to `url`, if any."""
    try:
        home = fetch(homepage)
    except FetchError:
        return None
    if home.status >= 400:
        return None
    domain = site(homepage)
    if on_domain(site(home.url), domain) and links_to(home, url):
        return home.url
    seen = {home.url}
    candidates = []
    for link, text in links(home):
        if link.startswith("https://") and on_domain(site(link), domain) and link not in seen:
            if DONATION_WORDS.search(link.split("://", 1)[1].split("/", 1)[-1]) or DONATION_WORDS.search(text):
                seen.add(link)
                candidates.append(link)
    for candidate in candidates[:MAX_PAGES]:
        try:
            page = fetch(candidate)
        except FetchError:
            continue
        if page.status < 400 and on_domain(site(page.url), domain) and links_to(page, url):
            return page.url
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    event = json.loads(args.event.read_text(encoding="utf-8"))
    fields = sections(event["issue"].get("body") or "")
    station_field = fields.get("Station", "")
    url = fields.get("Donation link", "").strip()
    website = fields.get("Station website", "").strip()

    uuids = UUID.findall(station_field.lower())
    if len(set(uuids)) != 1:
        fail("Give one Radio-Browser station: its UUID, or its link on radio-browser.info "
             "(https://www.radio-browser.info/history/<uuid>).")
    uuid = uuids[0]
    problems = url_errors(url, "The donation link")
    if website:
        if website.startswith("http://"):
            website = "https://" + website[len("http://"):]
        problems += url_errors(website, "The station website")
    if problems:
        fail("\n".join(problems))
    # The form's page, the one listeners open, even if the issue gave the embedded form.
    url = form_page(url)

    try:
        found = radio_browser(f"byuuid/{quote(uuid)}")
    except FetchError as e:
        fail(f"Radio-Browser can't be reached right now ({e}): edit the issue later to try again.")
    if not found:
        fail(f"Radio-Browser has no station {uuid}.")
    station = found[0]

    existing = next(((i, e) for i, e in entries() if uuid in e.get("match", {}).get("stations", [])), None)
    if not website:
        if existing:
            website = existing[1]["homepage"]
        else:
            website = (station.get("homepage") or "").strip()
            if website.startswith("http://"):
                website = "https://" + website[len("http://"):]
            if url_errors(website, "website"):
                fail("Radio-Browser has no usable website for this station: fill in *Station website*.")

    allowed = platforms()
    if not allowed_donation(url, website, allowed):
        fail(f"{url} is neither on the station's website ({site(website)}) nor on an accepted donation platform "
             f"({', '.join(allowed)}). Other platforms, PayPal included, are not accepted for now.")

    found_on = find_link(website, url)
    if not found_on:
        if existing and existing[1]["donate"].get("url") == url:
            # Already in the list, checked by hand.
            print(f"id={existing[0]}")
            print("change=same")
            return
        print(f"The station's website ({website}) doesn't link to {url}, neither on its homepage nor on a "
              "page that looks like a donation page.\n\n"
              "The maintainer can check it by hand (for instance by writing to the station). If you know "
              "the station, the surest way is to ask it to link this page from its website: edit this issue "
              "once it does, and the link is added at once. If the website is not the station's, fill in "
              "*Station website*.", file=sys.stderr)
        sys.exit(2)

    if existing:
        station_id, before = existing
        entry = dict(before)
        entry["homepage"] = website
        entry["donate"] = {"url": url, "found_on": found_on}
    else:
        station_id = recipe_id(uuid) or slug(station.get("name") or "station")
        base, n = station_id, 2
        while (STATIONS / f"{station_id}.toml").exists():
            station_id = f"{base[:60]}-{n}"
            n += 1
        before = None
        entry = {
            "schema": 1,
            "name": (station.get("name") or station_id).strip(),
            "homepage": website,
            "match": {"stations": [uuid]},
            "donate": {"url": url, "found_on": found_on},
        }
    # Radio-Browser's other copies of the station (same name, same website): the app may show any.
    try:
        found_copies = copies(station.get("name") or entry["name"], entry["homepage"])
    except FetchError:
        found_copies = []
    taken = {u for i, e in entries() if i != station_id for u in e.get("match", {}).get("stations", [])}
    known = list(entry["match"]["stations"])
    added = [u for u in found_copies if u not in known and u not in taken]
    entry["match"] = {**entry["match"], "stations": known + added}

    if not ID.match(station_id):
        fail(f"Can't make a valid id from {station_id!r}: a maintainer will add it by hand.")

    errors = entry_errors(entry, allowed)
    if errors:
        fail("\n".join(errors))

    if before is None:
        change = "new"
    elif before["homepage"] != entry["homepage"]:
        change = "homepage"
    elif before["donate"]["url"] != entry["donate"]["url"]:
        change = "link"
    elif added:
        change = "copies"
    else:
        change = "same"

    STATIONS.mkdir(exist_ok=True)
    write_entry(STATIONS / f"{station_id}.toml", entry)

    if args.summary:
        lines = []
        if change == "new":
            lines.append(f"**New station:** {entry['name']}, Radio-Browser `{uuid}`.")
            lines.append(f"**Check the website:** {entry['homepage']} must be the station's official site "
                         "(taken from Radio-Browser, which anyone can edit, unless the issue gave one).")
        if change == "homepage":
            lines.append(f"**The website changes:** {before['homepage']} → {entry['homepage']}. "
                         "Check it is the station's official site.")
        if change in ("link", "homepage") and before["donate"]["url"] != url:
            lines.append(f"**The donation link changes:** {before['donate']['url']} → {url}.")
        lines.append(f"**Found on the station's website:** {found_on} links to {url}.")
        if added:
            listed = ", ".join(f"[`{u}`](https://www.radio-browser.info/history/{u})" for u in added)
            lines.append(f"**Other copies in Radio-Browser** (same name, same website), added to `match.stations`: "
                         f"{listed}.")
        args.summary.write_text("\n\n".join(lines) + "\n", encoding="utf-8")

    print(f"id={station_id}")
    print(f"change={change}")


if __name__ == "__main__":
    main()
