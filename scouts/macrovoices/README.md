# MacroVoices Scout

**Status:** Designed, implementation next.

Detects new episodes on the MacroVoices YouTube channel, pulls the transcript, and drafts a synthesis against the current thesis (confirms, contradicts, or introduces a new signal) for review before it's merged into the thesis.

**Stack:** YouTube Data API v3 (channel monitoring), `youtube-transcript-api` (transcript extraction), Claude (synthesis).

See the full design: [`docs/superpowers/specs/2026-07-15-macrovoices-youtube-scout-design.md`](../../docs/superpowers/specs/2026-07-15-macrovoices-youtube-scout-design.md).
