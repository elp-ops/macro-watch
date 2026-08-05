# YouTube Intake

**Status:** Two components now live:
1. **Single-video intake** (Phase 1 of the original design) — send a link, get a transcript + synthesis logged to Notion. See `2026-07-15-youtube-intake-telegram-bot-design.md`.
2. **Daily scout** — checks 4 fixed channels (MacroVoices, Krown, Intelligent Cryptocurrency, Ivan on Tech) once a day via RSS, logs new content to Notion (per-episode for MacroVoices, daily-digest for the rest), and updates the "for Gina" rolling thesis page. See `2026-08-04-youtube-daily-scout-design.md`.

**Daily scout stack:** RSS discovery, `youtube-transcript-api` (primary) + Gemini video-understanding (fallback, for when YouTube IP-blocks the primary method), Claude (classification + synthesis), Notion API (`notion-client`, not the MCP connector — this runs standalone on Railway).

**Running locally:**
```bash
cd scouts/youtube-intake
pip install -r requirements.txt
cp .env.example .env  # fill in ANTHROPIC_API_KEY, GEMINI_API_KEY, NOTION_API_KEY
python -m pytest -v   # run tests
python run_daily.py   # run a real pass
```

**Deployed:** Railway cron, `railway.json`, daily at 10:00 UTC (buffer before the 3pm CET deadline).

**Credentials needed (not yet provisioned as of this plan):**
- A Notion integration token (`NOTION_API_KEY`) with access shared to the Sources DB, the "for Gina" thesis page, and the Daily Logs Archive page. This is separate from Claude's Notion MCP connection — a standalone script needs its own integration, created at notion.so/my-integrations.
- `GEMINI_API_KEY` — already exists for the `youtube-analyse` skill, reuse the same key.
- `ANTHROPIC_API_KEY` — a real API key (not a Claude Code session), for standalone script use.
