# YouTube Daily Scout — Design

**Date:** 2026-08-04
**Status:** Approved, ready for implementation planning
**Part of:** Macro Watch (umbrella project) → Macro Feed (automation pipeline).
**Supersedes/extends:** [`2026-07-15-youtube-intake-telegram-bot-design.md`](2026-07-15-youtube-intake-telegram-bot-design.md) — that spec's Phase 1 (single-video links, manual paste) is still valid and unaffected. This spec covers Phase 2/3 territory (channel-level, ongoing monitoring) but for a fixed list of 4 channels rather than an arbitrary channel, and folds in what was actually learned building the manual version of this on 2026-08-03/04.

## Purpose

Automate the daily check Elena was doing manually: has MacroVoices, Krown's Crypto Cave, Intelligent Cryptocurrency, or Ivan on Tech posted anything new, and does it change the rolling macro thesis. Runs once a day, logs new content to Notion, and keeps the "for Gina" rolling thesis page current without Elena having to ask.

## Scope

**In scope:**
- Daily check across exactly 4 channels (fixed list, not arbitrary channel intake — that's the existing Phase 1/2 spec's job).
- MacroVoices: full episode-level backfill was done manually as a one-off (episodes #527–543, 2026-08-03/04). Going forward, only new episodes get processed — no standing deep-backfill requirement.
- Krown / Ivan on Tech / Intelligent Cryptocurrency: no historical backfill beyond what was already done manually. Daily check only covers new videos since the last successful run.
- Transcript extraction, promo filtering, Notion logging (daily-digest format), and an update pass against the "for Gina" thesis page.

**Out of scope (deferred):**
- Telegram bot / Q&A interface — that's the existing 2026-07-15 spec, independent sub-project, not blocked by this one.
- Any channel beyond the fixed 4.
- Manual-approval gate on thesis writes — explicitly not wanted (see Key Design Decisions).

## Channels (resolved)

| Channel | Handle | Channel ID | Cadence |
|---|---|---|---|
| MacroVoices | @macrovoices7508 | `UCICRehoZjq3ZtAWgRJX118A` | ~weekly (episode + 1-2 companion clips) |
| Krown's Crypto Cave | @ECKrown | `UCnwxzpFzZNtLH8NgTeAROFA` | 3-5 short videos/day |
| Intelligent Cryptocurrency | @intelligentcryptocurrency | `UCRF2-5W_uwflhpj6Hf6r4Jw` | ~1/day |
| Ivan on Tech | @IvanOnTech | `UCrYmtJBtLdtm2ov84ulV-yg` | ~1/day |

## Architecture

**1. Discovery — RSS, not the YouTube Data API**
`https://www.youtube.com/feeds/videos.xml?channel_id=<id>` per channel. Free, no API key, no quota. Confirmed working live on 2026-08-03 (fetched all 4 channels' recent uploads this way). Returns roughly the last 15 uploads per channel — enough for daily incremental checks, not enough for a deep historical backfill (not needed per scope above).

**2. Dedup — local ledger, not a Notion query**
`processed.json` in the scout's folder (git-tracked), mapping `video_id → notion_page_url`. Cheaper and more portable than querying Notion just to check "have I seen this." Grouped by `(channel, calendar_day)` since Notion entries are per-day digests, not per-video.

**3. Transcript extraction — two-tier, because of a real IP-block risk**
Primary: `youtube-transcript-api` (free, no key). Confirmed working for 20 consecutive requests on 2026-08-03, then hit `IpBlocked` on the 21st. The library's own docs flag that cloud-provider IPs — exactly what Railway is — get blocked more aggressively than a residential IP. This is a genuine production risk for the daily cron, not just a backfill-volume issue.
Fallback: the existing `youtube-analyse` skill (`.claude/skills/youtube-analyse/youtube_analyse.py`), which uses Gemini's multimodal video understanding (watches the video directly via `file_data`, no caption scraping) — different failure mode, not subject to the same IP block. Slower and costs Gemini API tokens, so used only when the primary method fails on a given video, not as the default.
If both fail on a given video: log it as flagged/skipped (matches the existing "no captions" handling pattern), don't block the rest of the run.

**4. Promo filtering — content judgment, not title heuristics**
Every video's transcript gets pulled regardless of title. Before writing anything, Claude judges: is there actual market/trade content, or is this a program/bot/course pitch with no signal? Mixed content (common on livestreams) gets partially included — real segments summarized, promo segments explicitly noted as excluded, not silently dropped. This was validated manually on 2026-08-03 across ~20 videos and worked well (e.g., correctly separated Krown's livestream analysis from his Kong AI signup pitches within the same video).

**5. Grouping and Notion write — daily digest, one page per channel per day**
Not one page per video. Krown alone can post 3-5 short videos a day; per-video logging would flood the Sources DB. Instead: group same-day videos from the same channel into one Notion entry (`[Channel] — Daily Digest (YYYY-MM-DD)`), combined AI Summary / Key Claims / Risks across that day's real-content videos, one raw-transcript subpage per underlying video. This structure was hand-built for 10 entries on 2026-08-03 and is the template to replicate in code.
MacroVoices keeps its existing per-episode page format (not digest-grouped) since it's ~weekly, not high-frequency — matches the format already used for #526 and now #527–543.

**6. Thesis update — writes directly, no approval gate**
Unlike the 2026-07-15 spec's Telegram-intake design (which stages everything as "pending review" before merging into the live thesis), this scout writes directly to the **"for Gina" thesis page** (`3b1490cf-c56c-8015-9648-f388049211d1`) — a duplicate Elena maintains specifically so automation can write to it without risking her original (`2ec490cf-c56c-80f7-a4d7-caafc4466a93`, edited by hand, never touched by automation). The risk that motivated the manual-approval gate in the other spec — bad automated output landing in the live thesis — is contained by page duplication instead. Elena confirmed this explicitly on 2026-08-03.
What "writes" means in practice, per the manual run: refresh the Today/This Week Snapshot and Bottom line sections (new dated entry, demote the previous one per the existing color-rotation rule — blue → gray → pruned to Daily Logs Archive after 2-3 rotations), and correct the Operating Thesis/Decision Tree sections in place if a signal directly contradicts a standing assumption (this happened on 2026-08-03: the 10Y hit the thesis's own QE-trigger band without QE following, so the framework itself got corrected, not just appended to).

**7. Hosting — Railway, daily cron**
Consistent with the standing "no Anthropic-hosted infrastructure" rule. Timed to complete by 3pm CET. Given MacroVoices' weekly cadence and the other 3 channels' daily cadence, most days the run is small (a handful of videos); the IP-block risk from Section 3 is a tail risk on high-volume days, not a daily certainty.

## Data flow (single run)

1. Fetch RSS for all 4 channels.
2. Filter to videos not in `processed.json`, grouped by `(channel, date)`.
3. For each new video: pull transcript (primary → fallback per Section 3).
4. For each `(channel, date)` group: classify each video (real content / promo / thin-no-signal), synthesize a combined write-up for the real-content subset.
5. Write to Notion: MacroVoices → per-episode page (existing workflow); others → daily-digest page + per-video transcript subpages.
6. Update `processed.json`.
7. Compare new content against the current "for Gina" thesis page; always add one entry to the Daily Logs Archive summarizing the run (even a "nothing material today" run gets a one-line entry, for continuity). "Material" is not a deterministic rule — it's an LLM judgment call each run (does this new signal confirm, contradict, or add a new angle to a standing thesis point), same judgment exercised manually during the 2026-08-03 build. The implementation should prompt for this explicitly rather than trying to encode fixed materiality rules.

## Error handling

- No new videos on a channel → skip silently, no log noise.
- Transcript unavailable (no captions AND Gemini fallback also fails) → log video as flagged/skipped, continue.
- RSS fetch fails for a channel → retry once, then note the failure in the run's archive entry so Elena isn't left thinking the channel was silently clean.
- Notion write fails → don't advance `processed.json` for that video (so it's retried next run, not silently lost).

## Key Design Decisions (carried from the brainstorming conversation)

- **RSS + transcript-api over YouTube Data API**: no quota, no key, matches the free-tooling pattern already used for MacroVoices elsewhere in `macro-feed-system.md`.
- **Daily-digest grouping over per-video logging**: Elena's explicit call once she saw Krown's actual posting volume (up to 15 videos/5 days in the backfill window).
- **Promo filtering by content, not title**: titles don't reliably signal promo vs. real content; validated manually.
- **Direct thesis writes, no approval gate**: differs from the 2026-07-15 spec's Telegram-intake design on purpose — that design was for arbitrary/untrusted channels reaching the live thesis; this scout only touches the "for Gina" duplicate, which exists specifically to absorb this risk.
- **MacroVoices gets deep backfill (one-time, done manually); the other 3 don't**: Elena's call — MacroVoices' multi-speaker weekly format has lasting thesis value per-episode; the crypto TA channels are high-frequency rolling signals where only the recent window matters.

## Open items for the implementation plan (not blocking design approval)

- Exact retry/backoff behavior for the transcript-api → Gemini fallback (how many failures before falling back vs. retrying the same method).
- Whether `processed.json` needs a size cap / rotation, or just grows indefinitely (likely fine indefinitely given video counts involved — a few hundred entries a year at most).
- Railway cron exact trigger time (needs enough buffer before 3pm CET for the run itself, including any Gemini-fallback slowdowns).
- Confirm Sources DB schema needs no changes (Section 5 of this spec reuses the existing `Name`/`Source Name`/`Speaker`/`Date` schema as-is — verified against the live schema on 2026-08-03, no changes needed).
