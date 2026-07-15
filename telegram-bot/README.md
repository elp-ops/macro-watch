# Market Watch Telegram Bot

**Status:** Designed, implementation next.

Reactive only, never sends unprompted messages. Two jobs:

1. **Submit a link.** Send a YouTube video URL, it fetches the transcript, drafts a synthesis against the current thesis, and logs it to Notion as "Pending review." (Same underlying intake pipeline is also usable directly through a Claude Code session, Telegram is a convenience channel, not the only path.)
2. **Ask a question.** "Where are we at this week compared to the rolling thesis?" or any other question about current market positioning, answered from the captured Notion thesis and source data, not a live web search.

Merging a reviewed synthesis into the actual rolling thesis stays a manual, human-approved step, not something this bot does on its own.

**Stack:** Python, Telegram Bot API, Claude (both synthesis and Q&A), Notion (read/write for logging, read-only for Q&A), hosted on Railway (always-on, no dependency on a local machine).

See the full design: [`docs/superpowers/specs/2026-07-15-youtube-intake-telegram-bot-design.md`](../../docs/superpowers/specs/2026-07-15-youtube-intake-telegram-bot-design.md).
