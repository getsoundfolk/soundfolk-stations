# Soundfolk stations

What the [Radio-Browser](https://www.radio-browser.info/) catalog doesn't say about a station, and
[Soundfolk](https://github.com/getsoundfolk/soundfolk) wants to show: first of all **where to donate**
to it, then whether it is ad-free or listener-supported.

This repository is the shared list. Every copy of Soundfolk will download it (once a day), so **a
donation link added here shows up in the player for every listener of that station**.

> Work in progress: the format below is a draft, and Soundfolk doesn't read this list yet.

---

## Add a donation link

You need a GitHub account. No git or command line.

1. Find the station's own donation page: a "Soutenir", "Faire un don", "Adhérer", "Support us" or
   "Donate" link **on the station's website**.
2. Open the *Add a donation link* form (soon: **Suggest a donation link** in Soundfolk, ⓘ in the
   player, which fills in the station for you), paste the link, tick the licence box and submit.
3. A bot checks the link and opens a pull request, or says on the issue what is wrong.

Once a maintainer merges it, every copy of Soundfolk gets the link within a day.

### Or by hand, with a pull request
One file per station, `stations/<id>.toml` (lowercase letters, digits, `-` and `_`, named after the
station; it can't change later):

```toml
name = "Radio Campus Clermont-Ferrand"
homepage = "https://campus-clermont.net/"
match = { stations = ["<Radio-Browser UUID>"], streams = ["live.radio-campus.org:8002/clermont-ferrand"] }
donate = "https://www.helloasso.com/associations/…"
```

| Field | |
|---|---|
| `match.stations` | Radio-Browser station UUIDs. Better than streams, which change. Give both when you can. |
| `match.streams` | Stream URLs **without** `http(s)://`: `host/path`. A trailing `*` matches every path that starts with it. |
| `homepage` | The station's website: the page the donation link is checked against. |
| `donate` | The station's donation page. |

## What is accepted
A wrong donation link sends listeners' money to someone else, so every link is checked before it
reaches the app:

* **The station's own website must link to it.** CI reads the homepage (and its obvious support
  pages) and looks for the link. Found: the pull request is marked *verified*. Not found: a
  maintainer checks it by hand, and may ask the station.
* `https://` only, no URL shortener, no tracking parameters. The domain is the station's own, or a
  known donation platform (HelloAsso, Liberapay, Ko-fi, Patreon, Tipeee, Open Collective…).
* **Changing an existing link** is never verified automatically: a maintainer always compares the
  old and new pages.
* Nothing is published without a maintainer merging it.
* A station can ask for its entry to be changed or removed by opening an issue. A request sent from
  the station's own domain, or matching its website, is taken as coming from the station.

## Licence
By contributing, you agree that your entries are published under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (the list as a whole) and
the [Database Contents License 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) (each entry).
See [LICENSE](LICENSE).
