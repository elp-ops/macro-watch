# YouTube Intake + Telegram Bot — Design

**Date:** 2026-07-15
**Status:** Approved, ready for implementation planning
**Part of:** Macro Watch (umbrella project) → Macro Feed (automation pipeline).

**Revision note:** this spec replaces an earlier version scoped narrowly to auto-detecting new episodes on one channel (MacroVoices). Corrected scope: a general-purpose, source-agnostic YouTube intake pipeline plus a Telegram bot, reusable for any channel, not hardcoded to one.

## Purpose

Automate what was previously a fully manual step: Elena pasting a YouTube link to Gina for analysis and addition to the rolling macro thesis. Also give the system a public-facing interface (Telegram bot) that doubles as a portfolio piece, structured so someone else could copy the pattern for their own stack.

## Scope

**In scope (phase 1):**
- Given any single YouTube video link (any channel), fetch its transcript, draft a synthesis against the current thesis, and log it to Notion for review.
- Two ways to submit a link: directly to Gina in a Claude Code session, or via the Telegram bot. Both feed the same intake pipeline and Notion output.
- A Telegram bot that also answers market questions on demand (e.g. "where are we at this week compared to the rolling thesis?"), reading from the captured Notion thesis/source data. Reactive only, never sends unprompted messages.
- Manual review and merge into the actual rolling thesis, gated by Elena's explicit approval.

**Out of scope (deferred):**
- **Phase 2:** channel links. Paste a channel URL instead of a single video, pull back a configurable historical range (e.g. "last few years"), and bulk-process every video through the same pipeline. Needs the YouTube Data API to list a channel's videos; not needed for phase 1 since single-video links only require extracting the video ID from the URL.
- **Phase 3 (maybe):** automatic ongoing channel monitoring (checking a channel weekly for new uploads without a link being pasted at all). Not committed to; phase 1 covers the actual near-term need.
- Other scouts (CFTC, FRED, SEC EDGAR, Congressional trading — see `macro-feed-system.md` build order) and the consensus layer across multiple scouts. Independent sub-projects.

## Architecture (phase 1)

**1. Intake trigger — two paths, one pipeline**
- Path A: Elena pastes a link directly in a Claude Code session with Gina.
- Path B: Elena (or a template user, for the public/portfolio use case) sends a link to the Telegram bot.
- Both call the same underlying logic below.

**2. Transcript extraction — `youtube-transcript-api`**
Open-source Python library, pulls the existing caption track directly from YouTube (auto-generated or uploaded) given a video ID extracted from the URL. Free, no API key, no rate/token limits.

Rejected alternatives:
- Whisper (OpenAI API, $0.006/min): requires downloading audio, adds cost/complexity for a fallback case unlikely to trigger on any established channel. Deferred — handle a no-captions video as a one-off edge case if it ever happens, rather than building for it now.
- youtube-transcript.io (third-party service): free tier capped at 25 tokens/month, Plus tier $9.99/month for 1000 transcripts. Rejected as poor value versus the free direct library at this usage volume.

**3. Synthesis — Claude**
Drafts a short comparison (3-5 bullets) of the new transcript against the current rolling thesis: what's new, what confirms it, what contradicts it. Same pattern already used manually for past video sources in the thesis.

**4. Output — log first, merge only on approval**

Stage 1 (automatic): logged as a new row in the Notion Sources DB (`5eed33375a4640d597c17fd2bab83761`) with title, video URL, full transcript, and the synthesis. Status: "Pending review." Never touches the live thesis page.

Stage 2 (manual): Elena reviews the synthesis against the source whenever she checks in, no fixed cadence.

Stage 3 (manual trigger): Elena tells Gina "approved" in a session. Gina integrates the synthesis into the rolling thesis page (`2ec490cf-c56c-80f7-a4d7-caafc4466a93`), under the **Context / Supporting Models** section, as a new bullet, same style as existing entries. This step is not available through the Telegram bot, it requires a Gina session, so the bot never has write access to the live thesis.

**5. Telegram bot — Q&A**
Reads the rolling thesis + Sources DB (read-only for this function) and answers natural-language questions about current market positioning. No proactive/unprompted messages, ever, responds only when asked.

**6. Hosting — Railway**
The bot must run continuously to listen for Telegram messages, which rules out Claude Code Routines (scheduled, run-then-stop, not suited to always-on listening). Railway chosen over local, consistent with Elena's goal of not depending on her Mac being on. Local was considered and rejected for the same reason the health bot's local-only setup is already flagged as a limitation elsewhere.

## Notion formatting constraint

The rolling thesis page has an existing colour convention that must not be disturbed:
- Static section headings (Decision Tree, Operating Thesis, Action Plan, Key Levels, Catalysts, Yield & Curve Rules, etc.) have fixed colours that never change, automation must never recolour these.
- A separate rotation exists for "Today/This Week Snapshot" and "Bottom line for today" sections (newest = blue, demoted to gray when superseded, pruned to the Daily Logs archive after 2-3 rotations). This pipeline does not touch those sections, new entries land in Context/Supporting Models, which does not use colour-coding.

## Why manual approval for the merge (not full automation)

Elena's explicit choice: she wants to control what enters the thesis while this system is new and unproven, rather than trusting an automated merge from day one, whether triggered by a routine or by a Telegram reply. The logging and Q&A stages are fully automatic (low risk, either additive-only or read-only), the merge stage always requires an explicit "approved" from her in a session. Revisit once the system has a track record.

## Open items for the implementation plan (not blocking design approval)

- Telegram bot token, project setup (new bot, separate from the health bot's).
- Railway project setup and deployment config.
- Decide exact Sources DB schema/properties needed for the "Pending review" status and synthesis field, verify against current DB schema before adding new ones.
- Confirm how the bot distinguishes "this message is a YouTube link" vs "this message is a question" (simple URL pattern match should suffice).
