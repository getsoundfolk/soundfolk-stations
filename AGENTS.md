# Project context

Shared list of Soundfolk station data that Radio-Browser lacks (donation links, curated lists): TOML files in
`stations/` and `lists/`, checked and compiled by Python 3.11+ scripts (standard library only) into the JSON
every copy of the app downloads.

## Verification commands

- Targeted test: none (online check of one entry: `python3 scripts/check_links.py stations/<id>.toml`,
  `python3 scripts/check_lists.py lists/<id>.toml`)
- Full suite: none
- Lint / format: `python3 scripts/lint.py`
- Typecheck: none

## Rules

- If the need or an edge case is ambiguous, ask 2 or 3 short questions before coding. Otherwise, go ahead.
- Touch only the files you need. No new dependency without asking (the scripts use the standard library only).
- Never read, print or commit secrets or `.env` files.

## Pitfalls and non-obvious decisions

- A station or list id (its file name) cannot change once merged.
- A donation link is checked against the station's own `homepage`, never against the website listed in
  Radio-Browser, which anyone can edit.
- `donate.checked_by_hand` is for the maintainer only (CI refuses it from anyone else): give `found_on` instead.
- A new list names its author among `curators`.

## Definition of done

Lint at 0, `python3 scripts/compile.py` still runs, no debug log and no off-topic change.
