# Soundfolk stations

What the [Radio-Browser](https://www.radio-browser.info/) catalog doesn't say about a station, and
[Soundfolk](https://github.com/getsoundfolk/soundfolk) wants to show: first of all **where to donate**
to it, then whether it is ad-free or listener-supported.

This repository is the shared list. Every copy of Soundfolk will download it (once a day), so **a
donation link added here shows up in the player for every listener of that station**.

> Work in progress: Soundfolk doesn't read this list yet. The list is published at
> <https://getsoundfolk.github.io/soundfolk-stations/v1/stations.json>.

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
| `match.stations` | **Required.** Radio-Browser station UUIDs. Stations missing from Radio-Browser are not accepted for now. |
| `match.streams` | Optional. Stream URLs **without** `http(s)://`: `host/path`. A trailing `*` matches every path that starts with it. |
| `donate.url` | The station's donation page. |
| `donate.found_on` | The page of the station's website that links to `donate.url`: the proof. The bot fills it in; by hand, give the page where you found the link. |

## What is accepted
A wrong donation link sends listeners' money to someone else, so every link is checked before it
reaches the app:

* **The station's own website must link to it**, in the page's HTML: on its homepage or on one of
  its pages (`found_on`). A link the website doesn't give, or only shows with JavaScript, is not
  accepted for now.
* `https://` only, no URL shortener, no tracking parameters. The domain is the station's own, or one
  of these donation platforms: HelloAsso, Liberapay, Ko-fi, Patreon, Tipeee, Open Collective,
  Donorbox. Other platforms, PayPal included, are not accepted for now.
* Nothing is published without the maintainer merging it. The bot labels what needs a closer look:
  *new-station* (is `homepage`, taken from Radio-Browser, the official website?), *link-change* and
  *homepage-change*.
* **Every day**, CI checks every link again. A link no longer found on `found_on`, or that no longer
  answers, is left out of the published list at once, and comes back by itself as soon as the check
  passes. An issue is opened after 7 days, or at once if the link no longer answers or now leads to
  another domain.
* A station can ask for its entry to be changed or removed by opening an issue. A request sent from
  the station's own domain, or matching its website, is taken as coming from the station.

## Check locally
Python 3.11 or later, nothing to install:

```bash
python3 scripts/lint.py                              # the rules, offline
python3 scripts/check_links.py stations/<id>.toml    # the station's website links to the page
python3 scripts/compile.py                           # writes site/v1/stations.json
```

## Licence
By contributing, you agree that your entries are published under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (the list as a whole) and
the [Database Contents License 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) (each entry).
See [LICENSE](LICENSE).
