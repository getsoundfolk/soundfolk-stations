# Soundfolk stations

What the [Radio-Browser](https://www.radio-browser.info/) catalog doesn't say about a station, and
[Soundfolk](https://github.com/getsoundfolk/soundfolk) wants to show: first of all **where to donate**
to it, then whether it is ad-free or listener-supported; and **curated lists** of stations.

This repository is the shared list. Every copy of Soundfolk will download it (once a day), so **a
donation link added here shows up in the player for every listener of that station**.

> Work in progress: Soundfolk doesn't read this list yet. The list is published at
> <https://getsoundfolk.github.io/soundfolk-stations/v1/stations.json>, the curated lists at
> <https://getsoundfolk.github.io/soundfolk-stations/v1/lists.json>.

---

## Add a donation link

You need a GitHub account. No git or command line.

1. Find the station's own donation page: a "Soutenir", "Faire un don", "Adhérer", "Support us" or
   "Donate" link **on the station's website**.
2. Open the [*Add a donation link*](https://github.com/getsoundfolk/soundfolk-stations/issues/new?template=donation.yml)
   form (soon: **Suggest a donation link** in Soundfolk, ⓘ in the player, which fills in the station
   for you), give the station's Radio-Browser link and the donation link, tick the licence box and
   submit.
3. A bot looks for the link on the station's website and opens a pull request, or says on the issue
   what is wrong. Edit the issue to try again.

A link leads somewhere else, or doesn't work any more?
[Report it](https://github.com/getsoundfolk/soundfolk-stations/issues/new?template=wrong-link.yml).

Once the maintainer merges it, every copy of Soundfolk gets the link within a day.

### Or by hand, with a pull request
One file per station, `stations/<id>.toml` (lowercase letters, digits, `-` and `_`, named after the
station; it can't change later):

```toml
#:schema ../station.schema.json
schema = 1
name = "Radio Campus Clermont-Ferrand"
homepage = "https://campus-clermont.net/"
match = { stations = ["<Radio-Browser UUID>"], streams = ["live.radio-campus.org:8002/clermont-ferrand"] }

[donate]
url = "https://www.helloasso.com/associations/…"
found_on = "https://campus-clermont.net/soutenir/"
```

| Field | |
|---|---|
| `schema` | Always `1` for now. |
| `name` | The station's name, for people reading the file. |
| `homepage` | The station's official website. The donation link is checked against it, never against the website listed in Radio-Browser, which anyone can edit. |
| `match.stations` | **Required.** Radio-Browser station UUIDs, every copy of the station: Radio-Browser often lists one station several times, and Soundfolk may show any of them. The bot adds the copies with the same name and a website on the same domain. Stations missing from Radio-Browser are not accepted for now. |
| `match.streams` | Optional. Stream URLs **without** `http(s)://`: `host/path`. A trailing `*` matches every path that starts with it. |
| `donate.url` | The station's donation page. |
| `donate.found_on` | The page of the station's website that links to `donate.url`: the proof. The bot fills it in; by hand, give the page where you found the link. |
| `donate.checked_by_hand` | **Maintainer only**, instead of `found_on`, when the website doesn't link to the page: how and when the link was checked. |

## What is accepted
A wrong donation link sends listeners' money to someone else, so every link is checked before it
reaches the app:

* **The station's own website must link to it**, in the page's HTML: on its homepage or on one of
  its pages (`found_on`). For HelloAsso, `donate.url` is the form's page
  (`https://www.helloasso.com/associations/<association>/formulaires/<n>`).
* When the website doesn't give the link, the bot labels the issue *manual-check* instead. The
  maintainer may check it another way (an e-mail from the station's address, the association
  registry) and add it with `checked_by_hand`, which only the maintainer can write. The surest way
  is still to ask the station to link the page from its website: the entry then becomes an ordinary
  one.
* `https://` only, no URL shortener, no tracking parameters. The domain is the station's own, or one
  of these donation platforms: HelloAsso, Liberapay, Ko-fi, Patreon, Tipeee, Open Collective,
  Donorbox. Other platforms, PayPal included, are not accepted for now.
* Nothing is published without the maintainer merging it. The bot labels what needs a closer look:
  *new-station* (is `homepage`, taken from Radio-Browser, the official website?), *link-change* and
  *homepage-change*.
* **Every day**, CI checks every link again (for a link checked by hand, only that it still
  answers). A link no longer found on `found_on`, or that no longer answers, is left out of the
  published list at once, and comes back by itself as soon as the check
  passes. An issue is opened after 7 days, or at once if the link no longer answers or now leads to
  another domain.
* A station can ask for its entry to be changed or removed by opening an issue. A request sent from
  the station's own domain, or matching its website, is taken as coming from the station.

## Curated lists
A list is a handful of Radio-Browser stations picked by someone, around a theme: community radios
of a country, streams to work to, public broadcasters' music channels. Soundfolk shows each list as
a row in Discover, with its title, its description and "by @login". One file per list,
`lists/<id>.toml` (lowercase letters, digits and `-`; it can't change later):

```toml
#:schema ../list.schema.json
schema = 1
title = "Ambient to focus"
description = "Ambient and downtempo streams with few voices, for working, reading or coding."
curators = ["raphaelh"]
checked = 2026-11-06
use = ["focus", "calm"]
genres = ["ambient"]

stations = [
  "960cf833-0601-11e8-ae97-52543be04c81",  # SomaFM Groove Salad (128k MP3)
  "ae7aeb65-5a30-4848-8059-91b2bc2dcfd9",  # SomaFM Drone Zone (256k MP3)
]
```

| Field | |
|---|---|
| `title` | At most 40 characters, in one language: the one of the list's listeners. Say what is in the list rather than a mood. |
| `description` | One sentence, at most 140 characters, in the same language. |
| `curators` | 1 to 3 GitHub logins, yours included. The first one gets the issues CI opens. |
| `checked` | The date you last listened through the whole list. Never shown in the app; a year later, an issue asks you to review it again. |
| `use` | 1 to 3 of `focus`, `calm`, `energy`, `discovery`, `shows` ([vocab.toml](vocab.toml)): what the list is put on for. |
| `genres` | 0 to 3 genre ids from [vocab.toml](vocab.toml), only when they dominate the list. |
| `stations` | 5 to 40 Radio-Browser UUIDs, in your order, each followed by a comment with the station's name. One UUID per station: when Radio-Browser lists it several times, pick the copy that works best. |

Anything goes as long as the stations match the title and the description, whatever their network
(every channel of one broadcaster is a fine list) and whether or not they air ads. The pull request
shows each station's Radio-Browser name, country and whether its stream answers: check that each
UUID is the station you meant. The country of the list is worked out from its stations.

**Every day**, CI looks up every station again. Radio-Browser deletes duplicates, so a UUID can
disappear while the station is still there under another one: the copy playing the same stream then
stands in for it in the published list, without asking anyone. A station gone from Radio-Browser
with no copy playing its stream, or whose stream no longer answers (from here and from
Radio-Browser's own checkers), is left out of the published list, and comes back by itself once it
answers again; the file doesn't change. The first curator gets an issue at once for a station gone
from Radio-Browser (paste its new UUID), after 7 days for a stream that doesn't answer; the check
closes the issue itself once it passes again. Unanswered for 30 days, the maintainer fixes the list,
takes it over or unpublishes it.

## Check locally
Python 3.11 or later, nothing to install:

```bash
python3 scripts/lint.py                              # the rules, offline
python3 scripts/check_links.py stations/<id>.toml    # the station's website links to the page
python3 scripts/compile.py                           # writes site/v1/stations.json
python3 scripts/add_copies.py                        # adds Radio-Browser's new copies of each station
python3 scripts/check_lists.py lists/<id>.toml       # each station's Radio-Browser name, country, stream
python3 scripts/check_lists.py --daily /dev/null     # writes site/v1/lists-status.json
python3 scripts/compile_lists.py --status site/v1/lists-status.json   # writes site/v1/lists.json
```

## Licence
By contributing, you agree that your entries are published under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (the list as a whole) and
the [Database Contents License 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) (each entry).
See [LICENSE](LICENSE).
