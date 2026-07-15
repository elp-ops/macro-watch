# MacroVoices YouTube Scout — Design

**Date:** 2026-07-15
**Status:** Approved, ready for implementation planning
**Part of:** Macro Watch (umbrella project) → Macro Feed (automation pipeline). First scout built, per build priority order in `macro-feed-system.md`.

## Purpose

Automate what was previously a manual step: Elena pasting MacroVoices YouTube links to Gina for analysis and addition to the rolling macro thesis. This scout detects new episodes on the MacroVoices channel, pulls the transcript, and drafts a synthesis against the existing thesis, ready for Elena to review and approve.

## Scope

In scope: detecting new videos on one specific YouTube channel, pulling transcripts, drafting a comparison against the current thesis, logging to Notion for review, and a manual merge step into the thesis.

Out of scope (deferred to later sub-projects): other scouts (CFTC, FRED, SEC EDGAR, Congressional trading — see `macro-feed-system.md` build order), the consensus layer across multiple scouts, and the Telegram Q&A bot (separate design, reads from the same captured data once this exists).

## Source

- Channel: MacroVoices, `https://www.youtube.com/@macrovoices7508`
- Backfill window: last 1 year of uploads, then ongoing detection of new uploads going forward.

## Architecture

**1. Detection — YouTube Data API v3**
Query the channel's "uploads" playlist via `playlistItems.list` (every channel has one, derived from the channel ID). This single method handles both the one-time 1-year backfill (paginate filtered by `publishedAt`) and ongoing weekly checks (fetch anything newer than the last known video). Requires a YouTube Data API key (free tier, well within quota for one channel checked weekly).

Rejected alternatives:
- RSS feed only (`youtube.com/feeds/videos.xml`): free, no key needed, but only returns the ~15 most recent uploads — can't do the 1-year backfill, and no date filtering.
- Hybrid (RSS for ongoing + API for backfill): rejected for unnecessary complexity — two mechanisms for one job.

**2. Transcription — `youtube-transcript-api`**
Open-source Python library, pulls the existing caption track directly from YouTube (auto-generated or uploaded). Free, no API key, no rate/token limits.

Rejected alternatives:
- Whisper (OpenAI API, $0.006/min): would require downloading audio and adds cost/complexity for a fallback case that's unlikely to trigger on an established channel. Deferred — if a video with no captions is ever encountered, handle that single case then rather than building for it now.
- youtube-transcript.io (third-party service): free tier capped at 25 tokens/month, Plus tier $9.99/month for 1000 transcripts. Rejected as poor value at this volume (~4-5 episodes/month from one channel) versus the free direct library.

**3. Runtime — Claude Code Routine**
Runs weekly, cloud-hosted, clones the `elp-ops/macro-watch` GitHub repo. Chosen over a local script so it doesn't depend on Elena's Mac being on. Repo's `CLAUDE.md` should stay scoped to this scout, not inherit the full ELP-ops root context, to avoid wasting tokens per run. YouTube API key goes into the routine's Cloud Environment variables (not `.env`, which won't exist in the cloned repo).

**4. Output — log first, merge only on approval**

Stage 1 (automatic, every run): each new episode is logged as a new row in the Notion Sources DB (`5eed33375a4640d597c17fd2bab83761`) with title, publish date, video URL, full transcript, and a short Claude-written synthesis (3-5 bullets: what's new, what confirms the existing thesis, what contradicts it). Status: "Pending review." This never touches the live thesis page.

Stage 2 (manual): Elena reviews the synthesis against the source whenever she checks in. No fixed cadence requirement — items can sit as "Pending review" until she gets to them.

Stage 3 (manual trigger): Elena tells Gina "approved" in a session. Gina then integrates the synthesis into the rolling thesis page (`2ec490cf-c56c-80f7-a4d7-caafc4466a93`), specifically under the **Context / Supporting Models** section, as a new bullet — same style as existing entries (e.g. the IPO lockup cascade video, Ivan on Tech entries): bold label + date, prose synthesis, no special formatting. Matches the existing pattern for how retail/podcast video sources have always been added to this thesis.

## Notion formatting constraint

The rolling thesis page has an existing colour convention that must not be disturbed:
- Static section headings (Decision Tree, Operating Thesis, Action Plan, Key Levels, Catalysts, Yield & Curve Rules, etc.) have fixed colours that never change — automation must never recolour these.
- A separate rotation exists for "Today/This Week Snapshot" and "Bottom line for today" sections (newest = blue, demoted to gray when superseded, pruned to the Daily Logs archive after 2-3 rotations). This scout does not touch those sections and does not need to replicate that rotation — new entries land in Context/Supporting Models, which does not use colour-coding.

## Why manual approval for the merge (not full automation)

Elena's explicit choice: she wants to control what enters the thesis while this system is new and unproven, rather than trusting an automated merge from day one. The logging stage is fully automatic (low risk, additive-only, doesn't touch the live thesis), but the merge stage requires an explicit "approved" from her each time. This can be revisited once she's seen the system work reliably over a few weeks.

## Open items for the implementation plan (not blocking design approval)

- Resolve `@macrovoices7508` to a channel ID and derive the uploads playlist ID.
- Confirm Claude Code Routines can actually run successfully off `elp-ops/macro-watch` (mechanism is understood from prior use, but not yet tested against this specific repo).
- Decide exact Sources DB schema/properties needed for the new "Pending review" status and synthesis field (may already have compatible properties from manual use — verify against current DB schema before adding new ones).
