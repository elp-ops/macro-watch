# Macro Watch Wiki — Rules

This wiki is the cumulative knowledge base behind Elena's rolling macro thesis. It is built only from real inputs Elena provides (podcasts, articles, books, notes) plus scout output once Macro Feed is built. See `../brief.md` for the project's ground rules in full; this file covers how the wiki itself is filed.

## Structure

- `raw/` — source material exactly as received (transcripts, article text, book notes). Read-only: never edit an existing file, only add new ones.
- `concepts/` — one file per recurring macro mechanism or indicator (e.g. `yield-curve-inversion.md`, `cftc-cot.md`). Explain it once; every later reference links back here instead of re-explaining.
- `people/` — one file per analyst, guest, or fund manager whose calls get tracked over time. Log calls with dates so the track record is visible.
- `sources/` — one file per recurring source (a podcast, newsletter, publication). Log which episodes/issues have been processed and the key takeaway from each.
- `themes/` — one file per cross-cutting thesis line (oil, AI capex, crypto cycle, rates). This is where signals from concepts/people/sources get synthesised into an actual view.
- `index.md` — table of contents, links to every page below.
- `log.md` — dated, one-line entries: what was added or changed, and why.
- `overview.md` — the current thesis in plain language. Read this first for "where do we stand."

## How to file a new input

1. Drop the raw material into `raw/` unchanged.
2. Update whichever `concepts/`, `people/`, `sources/`, `themes/` pages it touches. Cross-reference: if it confirms or contradicts something already there, say so explicitly on that page rather than just appending a new entry.
3. Add a line to `log.md`.
4. If the thesis itself moved, update `overview.md`.

## Ground rules (carried over from `../brief.md`)

- Never invent data, claims, or analysis. Everything traces back to a file in `raw/`.
- Gina's own background knowledge can add context but must be clearly marked as separate from what Elena or a source actually said.
- If something is uncertain or outside the provided material, say so rather than filling the gap.
