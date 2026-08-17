# Daily Snapshot Telegram Bot — Design

**Date:** 2026-08-17
**Status:** Approved, ready for implementation planning
**Part of:** Macro Watch (umbrella project) → Macro Watch Signals (automation pipeline, formerly "Macro Feed").

## Purpose

Give Elena one daily, high-level Telegram message: where markets stand against her own tracked trigger levels, and what new source material came in. A CEO-skim view, not a re-read of the full thesis. No directional opinion layered in, facts only.

## Relationship to the other Telegram bot spec

A separate, already-approved-but-unbuilt design exists for a **reactive** Telegram bot (`2026-07-15-youtube-intake-telegram-bot-design.md`): submit a YouTube link for synthesis, or ask an ad-hoc question, answered from Notion. That bot explicitly never sends unprompted messages.

This is the opposite job: a **proactive**, scheduled push, unprompted by design. Kept as a separate build. They may end up sharing one Telegram bot identity later (one bot can both listen and push), but nothing about this build depends on that happening, and this build does not implement the reactive side.

## Scope

**In scope:**
- One scheduled run per day, one Telegram message sent to Elena's personal chat.
- Live price fetch for the assets tied to her tracked trigger levels (BTC, 10Y, 30Y, 2Y, DXY, oil, gold).
- Compare live prices against the trigger levels already logged in the thesis page's Key Levels section, flag anything within range of firing or already past it.
- A regime tag, read mechanically off the existing Decision Tree 10Y-based rule (no independent judgment).
- A same-day-typical-publishers list, from the 4 tracked YouTube channels.
- A digest of what the existing youtube-intake scout logged in the last 24 hours (titles + existing factual takeaways only, not re-summarized).
- A count of items still flagged "material, not yet synthesized" into the main thesis page.

**Out of scope (this build):**
- Anything reactive (link submission, Q&A) — separate spec, separate build.
- Any opinion, recommendation, or "so what" framing beyond the mechanical regime tag. If Elena wants that later, it's a distinct, explicitly-opinionated product.
- Multi-recipient support. One fixed chat ID.
- Fixing the pipeline's own data-integrity issues (e.g. the unverified $39,500 attribution found 17 Aug 2026) — flagged as a known open issue, not blocking this build, but the digest step must not silently propagate a claim from the daily-log archive that doesn't trace to an actual source transcript. See "Data integrity" below.

## Architecture

**New folder:** `projects/macro-watch/telegram-bot/daily-snapshot/` (Python), separate from `telegram-bot/` root reactive-bot placeholder.

**1. Trigger — Railway cron**
Daily at 07:00 CET (06:00 UTC winter / 05:00 UTC summer — set as 06:00 UTC and revisit if DST drift matters to Elena). Same hosting pattern as the youtube-intake scout and the CFTC pull: no Claude Code Routines, no always-on process, a script that runs once and exits.

**2. Price fetch**
- BTC: CoinGecko public API (no key required).
- 10Y / 30Y / 2Y yields, DXY, oil (WTI/Brent), gold: `yfinance` (free, no key).
- Each fetch wrapped individually; if one source fails, the message still sends with the rest, missing values marked `(unavailable)` rather than failing the whole run silently.

**3. Notion read (reuses existing helpers where possible)**
- Fetch the Key Levels section of the thesis page (`THESIS_PAGE_ID`, already in `config.py`) to get the current trigger levels and their text.
- Fetch the last 24h of entries from the Daily Logs archive (`DAILY_LOGS_ARCHIVE_ID`) for the "what came in yesterday" section.
- Count flagged-but-unsynthesized entries the same way (look for the "MATERIAL UPDATE FLAGGED" marker already used in those log entries).
- Reuses `fetch_page_plain_text`-style logic from `thesis_updater.py` rather than re-implementing Notion block-walking.

**4. Data integrity check on the digest step**
Before including a "what came in yesterday" bullet sourced from the archive, the script does not need to re-verify against the original video transcript on every run (too expensive to do daily) — but any bullet copied from the archive must be sourced as written, not reworded or strengthened. This build does not fix the upstream synthesis-fabrication risk found today; it just avoids compounding it by copying entries verbatim from the archive's own "Key Claims"-style language rather than re-summarizing them further.

**5. Message drafting — Claude Haiku**
Takes the fetched prices, trigger comparison, channel list, and archive digest as structured input, formats into one readable Telegram message (plain text, short sections, no markdown that Telegram won't render well). Cheap task, Haiku is the right model per the project's cost rule, this is formatting, not reasoning.

**6. Send — Telegram Bot API**
Plain `requests.post` to `sendMessage`, no bot framework needed since the bot never listens. Chat ID and bot token from Railway environment variables.

**7. Error handling**
- Any Notion or price-fetch failure that isn't total: send anyway with gaps marked, don't fail silently and skip the day.
- Total failure (can't reach Notion at all, or can't reach Telegram at all): log to Railway, no message sent, no retry storm. Elena finds out by noticing the gap, acceptable for a v1 personal tool.

## Content structure (one message)

1. Date + regime tag (mechanical, from Decision Tree 10Y rule).
2. Live levels vs. tracked triggers, flagging near/past-threshold items.
3. "On deck today" — typical publishers among the 4 tracked channels.
4. "What came in yesterday" — titles + existing factual takeaway, verbatim from the archive.
5. Backlog count — items flagged material, not yet synthesized into the main thesis.

## Testing

- Dry run locally against real Notion data and real price APIs, output printed to console instead of sent, before wiring up the actual `sendMessage` call.
- One real send to Elena's chat to confirm formatting renders legibly on mobile Telegram before scheduling the cron.
- Confirm a partial-failure case (temporarily break one price source) still produces a sendable message with the gap marked.

## Open items for the implementation plan (not blocking design approval)

- Elena creates the Telegram bot via BotFather and provides the token + her chat ID.
- Confirm exact yfinance tickers for each tracked level (10Y, 30Y, 2Y, DXY, WTI/Brent, gold) against what's actually available free.
- Confirm Railway project: new service under the existing `elp-ops/macro-watch` Railway project, or a new Railway project. Recommend reusing the existing project, new service within it, consistent with how the CFTC scout is planned.
