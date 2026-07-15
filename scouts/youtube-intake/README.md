# YouTube Intake

**Status:** Designed, implementation next.

Fetches a YouTube video's transcript and drafts a synthesis against the current thesis (confirms, contradicts, or introduces a new signal). Logs the result to Notion for review. Triggered via the [Telegram bot](../../telegram-bot/).

**Phase 1:** single video links, any channel. Send a link, get a transcript + synthesis logged to Notion as "Pending review."

**Phase 2 (later):** channel links. Paste a channel URL and pull back a configurable range (e.g. "last few years") of its videos in one batch, processed through the same pipeline.

**Stack:** `youtube-transcript-api` (transcript extraction, phase 1), YouTube Data API v3 (channel video listing, phase 2), Claude (synthesis).

See the full design: [`docs/superpowers/specs/2026-07-15-youtube-intake-telegram-bot-design.md`](../../docs/superpowers/specs/2026-07-15-youtube-intake-telegram-bot-design.md).
