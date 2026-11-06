"""What the scripts share: reading the entries, the URL rules, and reading a station's page.

Python 3.11+, standard library only.
"""

import json
import re
import tomllib
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl

ROOT = Path(__file__).resolve().parent.parent
STATIONS = ROOT / "stations"
SCHEMA_LINE = "#:schema ../station.schema.json"
ID = re.compile(r"^[a-z0-9_-]{1,64}$")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
USER_AGENT = "Soundfolk-stations/1 (+https://github.com/getsoundfolk/soundfolk-stations)"
TIMEOUT = 20
MAX_PAGE = 2 * 1024 * 1024
MAX_URL = 500
MAX_PROOF = 300

SHORTENERS = {
    "bit.ly", "buff.ly", "cutt.ly", "goo.gl", "is.gd", "lnkd.in", "ow.ly", "rebrand.ly",
    "shorturl.at", "t.co", "t.ly", "tiny.cc", "tinyurl.com",
}
TRACKING = re.compile(r"^(utm_.*|mtm_.*|pk_.*|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|_ga|_gl|igshid)$", re.I)


def platforms() -> list[str]:
    return tomllib.loads((ROOT / "platforms.toml").read_text(encoding="utf-8"))["domains"]


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def site(url: str) -> str:
    """The domain a website is identified by: its host without `www.`."""
    h = host(url)
    return h[4:] if h.startswith("www.") else h


def on_domain(h: str, domain: str) -> bool:
    return h == domain or h.endswith("." + domain)


def normalize(url: str) -> str:
    """For comparing links: lowercase scheme and host, no default port, no fragment, no trailing `/`."""
    parts = urlsplit(url.strip())
    netloc = (parts.hostname or "").lower().rstrip(".")
    if parts.port and parts.port not in (80, 443):
        netloc += f":{parts.port}"
    path = parts.path.rstrip("/")
    return urlunsplit(("https", netloc, path, parts.query, ""))


def url_errors(url: str, what: str) -> list[str]:
    """The rules every URL of an entry follows."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return [f"{what} must start with https://"]
    errors = []
    if len(url) > MAX_URL:
        errors.append(f"{what} is longer than {MAX_URL} characters")
    parts = urlsplit(url)
    if not parts.hostname:
        errors.append(f"{what} has no host")
    elif host(url) in SHORTENERS:
        errors.append(f"{what} is a shortened link: give the page it leads to")
    if parts.username or parts.password:
        errors.append(f"{what} must not contain a user name or password")
    tracking = [k for k, _ in parse_qsl(parts.query, keep_blank_values=True) if TRACKING.match(k)]
    if tracking:
        errors.append(f"{what} has tracking parameters ({', '.join(tracking)}): remove them")
    return errors


def entry_errors(entry: dict, allowed: list[str]) -> list[str]:
    """The rules of one entry (the schema, plus what a schema can't say)."""
    errors = []
    known = {"schema", "name", "homepage", "match", "donate"}
    for key in entry.keys() - known:
        errors.append(f"unknown field `{key}`")
    for key in sorted(known - entry.keys()):
        errors.append(f"missing field `{key}`")
    if entry.get("schema", 1) != 1:
        errors.append("`schema` must be 1")
    name = entry.get("name", "")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        errors.append("`name` must be a non-empty string (at most 200 characters)")

    homepage = entry.get("homepage", "")
    errors += url_errors(homepage, "`homepage`")

    match = entry.get("match", {})
    if not isinstance(match, dict):
        errors.append("`match` must be a table")
        match = {}
    for key in match.keys() - {"stations", "streams"}:
        errors.append(f"unknown field `match.{key}`")
    stations = match.get("stations")
    if not isinstance(stations, list) or not stations:
        errors.append("`match.stations` must list at least one Radio-Browser UUID")
    else:
        for uuid in stations:
            if not isinstance(uuid, str) or not UUID.fullmatch(uuid):
                errors.append(f"`match.stations`: {uuid!r} is not a lowercase Radio-Browser UUID")
    streams = match.get("streams", [])
    if not isinstance(streams, list) or not all(isinstance(s, str) and s.strip() for s in streams):
        errors.append("`match.streams` must be a list of `host/path`")
    else:
        for stream in streams:
            if "://" in stream:
                errors.append(f"`match.streams`: write {stream!r} without http(s)://")

    donate = entry.get("donate", {})
    if not isinstance(donate, dict):
        return errors + ["`donate` must be a table: [donate] with `url` and `found_on`"]
    for key in donate.keys() - {"url", "found_on", "checked_by_hand"}:
        errors.append(f"unknown field `donate.{key}`")
    url = donate.get("url", "")
    url_problems = url_errors(url, "`donate.url`")
    if not url_problems and form_page(url) != url:
        url_problems.append(f"`donate.url` must be the form's page: {form_page(url)}")
    errors += url_problems
    if ("found_on" in donate) == ("checked_by_hand" in donate):
        errors.append("`donate` needs either `found_on` (the page of the station's website that links to "
                      "`url`) or, added by the maintainer only, `checked_by_hand`")
    elif "found_on" in donate:
        found_on = donate["found_on"]
        errors += url_errors(found_on, "`donate.found_on`")
        if homepage.startswith("https://") and str(found_on).startswith("https://"):
            if not on_domain(host(found_on), site(homepage)):
                errors.append(f"`donate.found_on` must be on the station's website ({site(homepage)})")
    else:
        proof = donate["checked_by_hand"]
        if not isinstance(proof, str) or not 10 <= len(proof.strip()) <= MAX_PROOF:
            errors.append(f"`donate.checked_by_hand` says how and when the maintainer checked the link "
                          f"(10 to {MAX_PROOF} characters)")
    if not url_problems and homepage.startswith("https://"):
        if not allowed_donation(url, homepage, allowed):
            errors.append(
                f"`donate.url` must be on the station's website ({site(homepage)}) or on a platform of "
                f"platforms.toml ({', '.join(allowed)})"
            )
    return errors


def allowed_donation(url: str, homepage: str, allowed: list[str]) -> bool:
    h = host(url)
    return on_domain(h, site(homepage)) or any(on_domain(h, d) for d in allowed)


def load(path: Path) -> tuple[dict | None, str]:
    """An entry and its text, or None when the TOML does not parse (the error is in the text)."""
    text = path.read_text(encoding="utf-8")
    try:
        return tomllib.loads(text), text
    except tomllib.TOMLDecodeError as e:
        return None, str(e)


def entries() -> list[tuple[str, dict]]:
    """Every entry that parses, by id."""
    found = []
    for path in sorted(STATIONS.glob("*.toml")):
        entry, _ = load(path)
        if entry is not None:
            found.append((path.stem, entry))
    return found


def toml_string(value: str) -> str:
    # A JSON string is a valid TOML basic string.
    return json.dumps(value, ensure_ascii=False)


def write_entry(path: Path, entry: dict) -> None:
    lines = [
        SCHEMA_LINE,
        "schema = 1",
        f"name = {toml_string(entry['name'])}",
        f"homepage = {toml_string(entry['homepage'])}",
    ]
    match = [f"stations = [{', '.join(toml_string(s) for s in entry['match']['stations'])}]"]
    if entry["match"].get("streams"):
        match.append(f"streams = [{', '.join(toml_string(s) for s in entry['match']['streams'])}]")
    lines.append(f"match = {{ {', '.join(match)} }}")
    lines += [
        "",
        "[donate]",
        f"url = {toml_string(entry['donate']['url'])}",
    ]
    for key in ("found_on", "checked_by_hand"):
        if key in entry["donate"]:
            lines.append(f"{key} = {toml_string(entry['donate'][key])}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Reading pages.

class Fetched:
    def __init__(self, url: str, status: int, body: str):
        self.url = url  # after redirects
        self.status = status
        self.body = body


class FetchError(Exception):
    """No answer at all: DNS, connection, TLS or timeout."""


def fetch(url: str, read_body: bool = True) -> Fetched:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(MAX_PAGE) if read_body else b""
            charset = response.headers.get_content_charset() or "utf-8"
            return Fetched(response.geturl(), response.status, body.decode(charset, "replace"))
    except urllib.error.HTTPError as e:
        return Fetched(e.geturl() or url, e.code, "")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise FetchError(str(getattr(e, "reason", e))) from e


class _Links(HTMLParser):
    """Every link of a page, with its text: <a href>, <iframe src>, <form action>."""

    ATTRS = {"a": "href", "iframe": "src", "form": "action", "area": "href"}

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.links: list[tuple[str, str]] = []
        self._open: list[int] = []

    def handle_starttag(self, tag, attrs):
        if tag == "base":
            href = dict(attrs).get("href")
            if href:
                self.base = urljoin(self.base, href)
        attr = self.ATTRS.get(tag)
        value = dict(attrs).get(attr) if attr else None
        if value and not value.startswith(("javascript:", "mailto:", "tel:", "#")):
            self.links.append((urljoin(self.base, value.strip()), ""))
            if tag == "a":
                self._open.append(len(self.links) - 1)

    def handle_data(self, data):
        for i in self._open:
            url, text = self.links[i]
            self.links[i] = (url, text + data)

    def handle_endtag(self, tag):
        if tag == "a" and self._open:
            self._open.pop()


def links(page: Fetched) -> list[tuple[str, str]]:
    parser = _Links(page.url)
    parser.feed(page.body)
    return [(url, " ".join(text.split())) for url, text in parser.links]


# A website embeds a HelloAsso form with a link to `…/formulaires/<n>/` plus a suffix: the same form.
EMBEDDED = re.compile(r"/widget[a-z-]*$")


def form_page(url: str) -> str:
    """The HelloAsso form's page, the one listeners open, for a link to the same form embedded."""
    if not on_domain(host(url), "helloasso.com"):
        return url
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=EMBEDDED.sub("", parts.path.rstrip("/"))))


def canonical(url: str) -> str:
    url = normalize(url)
    if on_domain(host(url), "helloasso.com"):
        parts = urlsplit(url)
        url = urlunsplit(parts._replace(path=EMBEDDED.sub("", parts.path), query=""))
    return url


def links_to(page: Fetched, url: str) -> bool:
    target = canonical(url)
    return any(canonical(link) == target for link, _ in links(page))
