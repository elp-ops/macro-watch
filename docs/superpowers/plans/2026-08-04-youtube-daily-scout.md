# YouTube Daily Scout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily-run script that checks 4 fixed YouTube channels for new content, extracts and filters transcripts, logs them to Notion (per-episode for MacroVoices, daily-digest for the rest), and updates the "for Gina" rolling thesis page — deployed as a Railway cron job.

**Architecture:** A sequence of small, single-responsibility Python modules (RSS discovery → dedup ledger → transcript extraction with fallback → Claude-based classification/synthesis → Notion writes → thesis update), orchestrated by one entrypoint script that Railway's scheduler calls once a day.

**Tech Stack:** Python 3.11+, `youtube-transcript-api` (primary transcript source), Google Gemini API (fallback transcript source, reusing the existing `youtube-analyse` skill's video-understanding approach), Anthropic Claude API (classification/synthesis), Notion API (official `notion-client` package, not the MCP connector — this script runs standalone on Railway, outside a Claude Code session), `requests` + `xml.etree.ElementTree` for RSS (no extra XML dependency needed).

## Global Constraints

- Exactly 4 channels, fixed list, no dynamic channel addition: MacroVoices (`UCICRehoZjq3ZtAWgRJX118A`), Krown's Crypto Cave (`UCnwxzpFzZNtLH8NgTeAROFA`), Intelligent Cryptocurrency (`UCRF2-5W_uwflhpj6Hf6r4Jw`), Ivan on Tech (`UCrYmtJBtLdtm2ov84ulV-yg`).
- Discovery via RSS only (`https://www.youtube.com/feeds/videos.xml?channel_id=<id>`) — no YouTube Data API key.
- Transcript extraction is two-tier: `youtube-transcript-api` first, Gemini video-understanding fallback on failure. Never fail a video silently — log skips explicitly.
- Notion Sources DB data source ID: `263b6dcd-f245-4082-8c7d-11b9ee0f9f58`.
- "for Gina" thesis page ID (writes allowed): `3b1490cf-c56c-8015-9648-f388049211d1`.
- Elena's original thesis page ID (NEVER write to this): `2ec490cf-c56c-80f7-a4d7-caafc4466a93`. This is a hard constraint — no task in this plan may write to this ID under any circumstance.
- Daily Logs Archive page ID: `3b8490cf-c56c-83f0-a521-81c81778d9bd`.
- MacroVoices videos → one Notion page per episode (existing format, matches `#526`–`#543`). Krown/Ivan/Intelligent Cryptocurrency videos → one Notion page per `(channel, calendar_day)` with real content, following the digest format built manually on 2026-08-03.
- Dedup via a local git-tracked `processed.json` ledger, not a Notion query.
- Default model for synthesis/classification: Claude Sonnet (cost-efficiency standing rule — this is a "standard" tool-use/synthesis task, not "simple" or "complex architecture").
- Hosting: Railway cron, no Claude Code Routines / RemoteTrigger (standing rule, `memory/feedback_no_anthropic_cloud.md`).

---

## Task 1: Project scaffolding and channel config

**Files:**
- Create: `scouts/youtube-intake/config.py`
- Create: `scouts/youtube-intake/requirements.txt`
- Create: `scouts/youtube-intake/.env.example`
- Create: `scouts/youtube-intake/.gitignore`
- Test: `scouts/youtube-intake/tests/test_config.py`

**Interfaces:**
- Produces: `config.CHANNELS` — a list of `Channel` namedtuples with fields `name: str`, `handle: str`, `channel_id: str`, `format: Literal["episode", "digest"]`.
- Produces: `config.NOTION_SOURCES_DATA_SOURCE_ID`, `config.THESIS_PAGE_ID`, `config.ORIGINAL_THESIS_PAGE_ID` (constant, used only for the guard in Task 6), `config.DAILY_LOGS_ARCHIVE_ID` — all `str`.

- [ ] **Step 1: Write the failing test**

```python
# scouts/youtube-intake/tests/test_config.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config

def test_four_channels_configured():
    assert len(config.CHANNELS) == 4

def test_macrovoices_is_episode_format():
    mv = [c for c in config.CHANNELS if c.name == "MacroVoices"][0]
    assert mv.format == "episode"
    assert mv.channel_id == "UCICRehoZjq3ZtAWgRJX118A"

def test_krown_is_digest_format():
    krown = [c for c in config.CHANNELS if c.name == "Krown"][0]
    assert krown.format == "digest"
    assert krown.channel_id == "UCnwxzpFzZNtLH8NgTeAROFA"

def test_thesis_page_ids_are_distinct():
    assert config.THESIS_PAGE_ID != config.ORIGINAL_THESIS_PAGE_ID
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write the config module**

```python
# scouts/youtube-intake/config.py
from collections import namedtuple

Channel = namedtuple("Channel", ["name", "handle", "channel_id", "format"])

CHANNELS = [
    Channel("MacroVoices", "@macrovoices7508", "UCICRehoZjq3ZtAWgRJX118A", "episode"),
    Channel("Krown", "@ECKrown", "UCnwxzpFzZNtLH8NgTeAROFA", "digest"),
    Channel("IntelligentCryptocurrency", "@intelligentcryptocurrency", "UCRF2-5W_uwflhpj6Hf6r4Jw", "digest"),
    Channel("IvanOnTech", "@IvanOnTech", "UCrYmtJBtLdtm2ov84ulV-yg", "digest"),
]

NOTION_SOURCES_DATA_SOURCE_ID = "263b6dcd-f245-4082-8c7d-11b9ee0f9f58"
THESIS_PAGE_ID = "3b1490cf-c56c-8015-9648-f388049211d1"
ORIGINAL_THESIS_PAGE_ID = "2ec490cf-c56c-80f7-a4d7-caafc4466a93"
DAILY_LOGS_ARCHIVE_ID = "3b8490cf-c56c-83f0-a521-81c81778d9bd"

RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_config.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Add requirements, env example, gitignore**

```text
# scouts/youtube-intake/requirements.txt
youtube-transcript-api>=0.6.2
google-genai>=0.3.0
anthropic>=0.39.0
notion-client>=2.2.1
requests>=2.31.0
python-dotenv>=1.0.1
```

```bash
# scouts/youtube-intake/.env.example
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
NOTION_API_KEY=
```

```
# scouts/youtube-intake/.gitignore
.env
processed.json
__pycache__/
*.pyc
```

- [ ] **Step 6: Commit**

```bash
cd /Users/looneykat/ELP-ops/projects/macro-watch
git add scouts/youtube-intake/config.py scouts/youtube-intake/requirements.txt scouts/youtube-intake/.env.example scouts/youtube-intake/.gitignore scouts/youtube-intake/tests/test_config.py
git commit -m "scout: add channel config and project scaffolding"
```

---

## Task 2: RSS discovery

**Files:**
- Create: `scouts/youtube-intake/rss.py`
- Test: `scouts/youtube-intake/tests/test_rss.py`
- Test fixture: `scouts/youtube-intake/tests/fixtures/sample_feed.xml`

**Interfaces:**
- Consumes: `config.RSS_URL_TEMPLATE`, `config.Channel`.
- Produces: `rss.fetch_recent_videos(channel: config.Channel) -> list[rss.VideoEntry]` where `VideoEntry` is a namedtuple `(video_id: str, title: str, published: datetime.date, channel_name: str)`.
- Produces: `rss.parse_feed_xml(xml_text: str, channel_name: str) -> list[VideoEntry]` (pure function, used by the test and by `fetch_recent_videos`).

- [ ] **Step 1: Create a fixture from a real feed shape**

```xml
<!-- scouts/youtube-intake/tests/fixtures/sample_feed.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>abc12345678</yt:videoId>
    <title>Test Video One</title>
    <published>2026-08-01T12:00:00+00:00</published>
  </entry>
  <entry>
    <yt:videoId>def87654321</yt:videoId>
    <title>Test Video Two</title>
    <published>2026-08-02T09:30:00+00:00</published>
  </entry>
</feed>
```

- [ ] **Step 2: Write the failing test**

```python
# scouts/youtube-intake/tests/test_rss.py
import sys
import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import rss

FIXTURE = (Path(__file__).parent / "fixtures" / "sample_feed.xml").read_text()

def test_parse_feed_returns_two_entries():
    entries = rss.parse_feed_xml(FIXTURE, channel_name="TestChannel")
    assert len(entries) == 2

def test_parse_feed_extracts_video_id_and_title():
    entries = rss.parse_feed_xml(FIXTURE, channel_name="TestChannel")
    assert entries[0].video_id == "abc12345678"
    assert entries[0].title == "Test Video One"

def test_parse_feed_extracts_published_date():
    entries = rss.parse_feed_xml(FIXTURE, channel_name="TestChannel")
    assert entries[0].published == datetime.date(2026, 8, 1)
    assert entries[1].published == datetime.date(2026, 8, 2)

def test_parse_feed_attaches_channel_name():
    entries = rss.parse_feed_xml(FIXTURE, channel_name="TestChannel")
    assert all(e.channel_name == "TestChannel" for e in entries)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_rss.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rss'`

- [ ] **Step 4: Write the RSS module**

```python
# scouts/youtube-intake/rss.py
import datetime
import xml.etree.ElementTree as ET
from collections import namedtuple

import requests

import config

VideoEntry = namedtuple("VideoEntry", ["video_id", "title", "published", "channel_name"])

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def parse_feed_xml(xml_text: str, channel_name: str) -> list[VideoEntry]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry_el in root.findall("atom:entry", _NS):
        video_id = entry_el.find("yt:videoId", _NS).text
        title = entry_el.find("atom:title", _NS).text
        published_raw = entry_el.find("atom:published", _NS).text
        published_date = datetime.datetime.fromisoformat(published_raw).date()
        entries.append(VideoEntry(video_id, title, published_date, channel_name))
    return entries


def fetch_recent_videos(channel: "config.Channel") -> list[VideoEntry]:
    url = config.RSS_URL_TEMPLATE.format(channel_id=channel.channel_id)
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return parse_feed_xml(response.text, channel_name=channel.name)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_rss.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add scouts/youtube-intake/rss.py scouts/youtube-intake/tests/test_rss.py scouts/youtube-intake/tests/fixtures/sample_feed.xml
git commit -m "scout: add RSS feed discovery module"
```

---

## Task 3: Dedup ledger

**Files:**
- Create: `scouts/youtube-intake/ledger.py`
- Test: `scouts/youtube-intake/tests/test_ledger.py`

**Interfaces:**
- Consumes: `rss.VideoEntry`.
- Produces: `ledger.Ledger` class with methods `load(path: Path) -> Ledger` (classmethod), `is_processed(video_id: str) -> bool`, `mark_processed(video_id: str, notion_page_url: str) -> None`, `save(path: Path) -> None`.
- Produces: `ledger.group_new_videos(entries: list[rss.VideoEntry], ledger: Ledger) -> dict[tuple[str, datetime.date], list[rss.VideoEntry]]` — groups unprocessed entries by `(channel_name, published_date)`.

- [ ] **Step 1: Write the failing test**

```python
# scouts/youtube-intake/tests/test_ledger.py
import sys
import datetime
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import ledger
from rss import VideoEntry

def test_new_ledger_has_no_processed_videos(tmp_path):
    led = ledger.Ledger.load(tmp_path / "processed.json")
    assert not led.is_processed("abc123")

def test_mark_processed_then_is_processed(tmp_path):
    led = ledger.Ledger.load(tmp_path / "processed.json")
    led.mark_processed("abc123", "https://notion.so/page1")
    assert led.is_processed("abc123")

def test_save_and_reload_persists_state(tmp_path):
    path = tmp_path / "processed.json"
    led = ledger.Ledger.load(path)
    led.mark_processed("abc123", "https://notion.so/page1")
    led.save(path)

    reloaded = ledger.Ledger.load(path)
    assert reloaded.is_processed("abc123")

def test_group_new_videos_by_channel_and_date():
    entries = [
        VideoEntry("v1", "Title 1", datetime.date(2026, 8, 1), "Krown"),
        VideoEntry("v2", "Title 2", datetime.date(2026, 8, 1), "Krown"),
        VideoEntry("v3", "Title 3", datetime.date(2026, 8, 2), "Krown"),
    ]
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    groups = ledger.group_new_videos(entries, led)
    assert len(groups[("Krown", datetime.date(2026, 8, 1))]) == 2
    assert len(groups[("Krown", datetime.date(2026, 8, 2))]) == 1

def test_group_new_videos_excludes_already_processed():
    entries = [
        VideoEntry("v1", "Title 1", datetime.date(2026, 8, 1), "Krown"),
        VideoEntry("v2", "Title 2", datetime.date(2026, 8, 1), "Krown"),
    ]
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    led.mark_processed("v1", "https://notion.so/page1")
    groups = ledger.group_new_videos(entries, led)
    assert len(groups[("Krown", datetime.date(2026, 8, 1))]) == 1
    assert groups[("Krown", datetime.date(2026, 8, 1))][0].video_id == "v2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ledger'`

- [ ] **Step 3: Write the ledger module**

```python
# scouts/youtube-intake/ledger.py
import json
from collections import defaultdict
from pathlib import Path

from rss import VideoEntry


class Ledger:
    def __init__(self, data: dict):
        self._data = data  # video_id -> notion_page_url

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        if path.exists():
            return cls(json.loads(path.read_text()))
        return cls({})

    def is_processed(self, video_id: str) -> bool:
        return video_id in self._data

    def mark_processed(self, video_id: str, notion_page_url: str) -> None:
        self._data[video_id] = notion_page_url

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._data, indent=2, sort_keys=True))


def group_new_videos(entries: list[VideoEntry], ledger: Ledger) -> dict:
    groups = defaultdict(list)
    for entry in entries:
        if ledger.is_processed(entry.video_id):
            continue
        key = (entry.channel_name, entry.published)
        groups[key].append(entry)
    return dict(groups)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_ledger.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scouts/youtube-intake/ledger.py scouts/youtube-intake/tests/test_ledger.py
git commit -m "scout: add dedup ledger with channel/day grouping"
```

---

## Task 4: Two-tier transcript extraction

**Files:**
- Create: `scouts/youtube-intake/transcript.py`
- Test: `scouts/youtube-intake/tests/test_transcript.py`

**Interfaces:**
- Consumes: `GEMINI_API_KEY` env var (reuses the loading pattern from `.claude/skills/youtube-analyse/youtube_analyse.py`).
- Produces: `transcript.TranscriptResult` namedtuple `(video_id: str, text: str | None, source: Literal["captions", "gemini", "failed"])`.
- Produces: `transcript.get_transcript(video_id: str) -> TranscriptResult` — tries `youtube-transcript-api` first, falls back to Gemini video-understanding on any exception, returns `source="failed"` with `text=None` if both fail.

- [ ] **Step 1: Write the failing test**

```python
# scouts/youtube-intake/tests/test_transcript.py
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import transcript

def test_get_transcript_uses_captions_when_available():
    fake_snippet = MagicMock()
    fake_snippet.text = "hello world"
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.return_value = [fake_snippet]
        result = transcript.get_transcript("abc123")
    assert result.source == "captions"
    assert result.text == "hello world"
    assert result.video_id == "abc123"

def test_get_transcript_falls_back_to_gemini_on_captions_failure():
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_gemini_transcript", return_value="gemini transcript text") as mock_gemini:
            result = transcript.get_transcript("abc123")
    assert result.source == "gemini"
    assert result.text == "gemini transcript text"
    mock_gemini.assert_called_once_with("abc123")

def test_get_transcript_returns_failed_when_both_fail():
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_gemini_transcript", side_effect=Exception("Gemini error")):
            result = transcript.get_transcript("abc123")
    assert result.source == "failed"
    assert result.text is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_transcript.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transcript'`

- [ ] **Step 3: Write the transcript module**

```python
# scouts/youtube-intake/transcript.py
import os
from collections import namedtuple
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

TranscriptResult = namedtuple("TranscriptResult", ["video_id", "text", "source"])

GEMINI_MODEL = "gemini-2.5-flash"

GEMINI_TRANSCRIPT_PROMPT = (
    "Transcribe the spoken audio of this video as accurately as possible. "
    "Return only the transcript text, no commentary, no timestamps."
)


def _load_gemini_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("GEMINI_API_KEY not found in environment or .env")


def call_gemini_transcript(video_id: str) -> str:
    client = genai.Client(api_key=_load_gemini_api_key())
    url = f"https://www.youtube.com/watch?v={video_id}"
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=types.Content(
            parts=[
                types.Part(file_data=types.FileData(file_uri=url)),
                types.Part(text=GEMINI_TRANSCRIPT_PROMPT),
            ]
        ),
    )
    return response.text


def get_transcript(video_id: str) -> TranscriptResult:
    try:
        api = YouTubeTranscriptApi()
        snippets = api.fetch(video_id)
        text = " ".join(s.text for s in snippets)
        return TranscriptResult(video_id, text, "captions")
    except Exception:
        pass

    try:
        text = call_gemini_transcript(video_id)
        return TranscriptResult(video_id, text, "gemini")
    except Exception:
        return TranscriptResult(video_id, None, "failed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_transcript.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Manual smoke test against a real video (not mocked)**

Run:
```bash
cd scouts/youtube-intake
python -c "from transcript import get_transcript; r = get_transcript('dQw4w9WgXcQ'); print(r.source, len(r.text) if r.text else 0)"
```
Expected: prints `captions <some positive number>` — confirms the real `youtube-transcript-api` call path works end to end, not just the mocked unit test.

- [ ] **Step 6: Commit**

```bash
git add scouts/youtube-intake/transcript.py scouts/youtube-intake/tests/test_transcript.py
git commit -m "scout: add two-tier transcript extraction (captions + Gemini fallback)"
```

---

## Task 5: Claude-based classification and synthesis

**Files:**
- Create: `scouts/youtube-intake/synthesize.py`
- Test: `scouts/youtube-intake/tests/test_synthesize.py`

**Interfaces:**
- Consumes: `ANTHROPIC_API_KEY` env var, `transcript.TranscriptResult`.
- Produces: `synthesize.VideoClassification` namedtuple `(video_id: str, has_real_content: bool, reason: str)`.
- Produces: `synthesize.classify_video(title: str, transcript_text: str) -> VideoClassification`.
- Produces: `synthesize.write_digest_summary(channel_name: str, date: "datetime.date", videos: list[dict]) -> str` — `videos` is a list of `{"title": str, "transcript": str}` for videos already filtered to `has_real_content=True`. Returns markdown matching the structure used for the 2026-08-03 manual digests (AI Summary / Key Claims / Bond-Fed relevance / Risks / Filtered out).
- Produces: `synthesize.write_episode_summary(title: str, speaker: str, transcript_text: str) -> str` — matches the MV526-style per-episode format (macro scoreboard, catalysts, plain-English framing, numbered thesis points, bottom line, soundbites, open questions).

- [ ] **Step 1: Write the failing test**

```python
# scouts/youtube-intake/tests/test_synthesize.py
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import synthesize

def _fake_anthropic_response(text: str):
    fake_block = MagicMock()
    fake_block.text = text
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    return fake_response

def test_classify_video_parses_real_content_true():
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response(
            'REAL_CONTENT: true\nREASON: discusses specific BTC price levels'
        )
        result = synthesize.classify_video("Some Title", "transcript about bitcoin price levels")
    assert result.has_real_content is True
    assert "price levels" in result.reason

def test_classify_video_parses_real_content_false():
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response(
            'REAL_CONTENT: false\nREASON: pure course promo, no market content'
        )
        result = synthesize.classify_video("Buy My Course", "sign up now for my trading bot")
    assert result.has_real_content is False

def test_write_digest_summary_includes_channel_and_date():
    import datetime
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response("## AI Summary\nTest summary content")
        result = synthesize.write_digest_summary(
            "Krown", datetime.date(2026, 8, 5), [{"title": "Test Video", "transcript": "some transcript"}]
        )
    assert "AI Summary" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_synthesize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synthesize'`

- [ ] **Step 3: Write the synthesize module**

```python
# scouts/youtube-intake/synthesize.py
import os
import re
from collections import namedtuple

import anthropic

MODEL = "claude-sonnet-5"

VideoClassification = namedtuple("VideoClassification", ["video_id", "has_real_content", "reason"])

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CLASSIFY_PROMPT = """You are screening a YouTube video transcript for inclusion in a macro/crypto investment thesis tracker.

Title: {title}
Transcript (may be truncated): {transcript}

Is there real, substantive market/trading/macro analysis here (specific claims, price levels, indicators, macro data, trade ideas)? Or is this primarily a promo/pitch for a paid course, bot, signal service, or Patreon with little to no actual analysis?

Respond in exactly this format:
REAL_CONTENT: true|false
REASON: <one sentence>"""

DIGEST_PROMPT = """You are writing a daily digest entry for {channel} covering {date}, for Elena's rolling macro/crypto investment thesis.

Below are transcripts of {count} video(s) from this channel on this day, already filtered to exclude pure promotional content.

{videos_block}

Write a Notion page body in this exact structure (markdown):

## AI Summary
[2-4 sentence overview of what this day's content covers]

## Key Claims
- [bulleted concrete claims: price levels, indicators, timeframes, reasoning - one bullet per video or per distinct claim]

## Bond/Fed relevance
[Any mention of Federal Reserve, interest rates, bond yields (10Y/2Y/30Y), inflation, or the dollar (DXY) - quote or closely paraphrase. If none, say "No bond/Fed/yield content."]

## Risks / Contradictions
[Caveats, low-confidence framing, internal contradictions]

Do not invent claims not present in the transcripts. If a number or fact is unclear, say so rather than guessing."""

EPISODE_PROMPT = """You are writing a Notion page summary for a MacroVoices podcast episode, for Elena's rolling macro investment thesis.

Title: {title}
Speaker(s): {speaker}
Transcript: {transcript}

Write the page body in this exact structure (markdown), matching the depth and style of a professional research summary:

Macro scoreboard (week-over-week, gray-colored bullets, use <span color="gray">...</span> for each line)
Key near-term macro catalysts they flag
## What this episode is really about (plain English)
[2-3 sentences]
## [Speaker]'s core thesis
[Numbered points, each with sub-bullets, going deep on the actual argument and reasoning - not just a topic list]
## Bond / Fed / yield signals
[Dedicated section - any Fed/rates/yields/inflation/dollar content, prominent and precise. If none, say so explicitly.]
## Bottom line
[1-2 sentences]
## Soundbites / mental models worth keeping
[A few direct quotes or memorable framings]
## Open questions to carry into the rolling thesis
[Bulleted]

Do not invent claims, numbers, or analysis not present in the transcript. If a number is garbled or unclear in the transcript, flag the uncertainty rather than guessing a clean value."""


def classify_video(title: str, transcript_text: str) -> VideoClassification:
    prompt = CLASSIFY_PROMPT.format(title=title, transcript=transcript_text[:4000])
    response = _client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    real_content = re.search(r"REAL_CONTENT:\s*(true|false)", text, re.IGNORECASE)
    reason = re.search(r"REASON:\s*(.+)", text)
    return VideoClassification(
        video_id="",
        has_real_content=(real_content.group(1).lower() == "true") if real_content else False,
        reason=reason.group(1).strip() if reason else "",
    )


def write_digest_summary(channel_name: str, date, videos: list[dict]) -> str:
    videos_block = "\n\n".join(
        f"### Video: {v['title']}\n{v['transcript'][:8000]}" for v in videos
    )
    prompt = DIGEST_PROMPT.format(
        channel=channel_name, date=date.isoformat(), count=len(videos), videos_block=videos_block
    )
    response = _client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def write_episode_summary(title: str, speaker: str, transcript_text: str) -> str:
    prompt = EPISODE_PROMPT.format(title=title, speaker=speaker, transcript=transcript_text[:100000])
    response = _client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_synthesize.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scouts/youtube-intake/synthesize.py scouts/youtube-intake/tests/test_synthesize.py
git commit -m "scout: add Claude-based promo classification and summary synthesis"
```

---

## Task 6: Notion writer

**Files:**
- Create: `scouts/youtube-intake/notion_writer.py`
- Test: `scouts/youtube-intake/tests/test_notion_writer.py`

**Interfaces:**
- Consumes: `NOTION_API_KEY` env var, `config.NOTION_SOURCES_DATA_SOURCE_ID`, `config.ORIGINAL_THESIS_PAGE_ID`.
- Produces: `notion_writer.create_digest_page(channel_name: str, date: "datetime.date", summary_markdown: str, videos: list[dict]) -> str` (returns the created page URL). `videos` is `[{"title": str, "video_id": str, "transcript": str}]` — creates the main page plus one transcript child page per video.
- Produces: `notion_writer.create_episode_page(title: str, speaker: str, date: "datetime.date", summary_markdown: str, video_id: str, transcript_text: str) -> str` (returns page URL).
- Produces: `notion_writer.guard_against_original_thesis(page_id: str) -> None` — raises `ValueError` if `page_id == config.ORIGINAL_THESIS_PAGE_ID`. Called at the top of every write function that touches the thesis page (used in Task 7).

- [ ] **Step 1: Write the failing test**

```python
# scouts/youtube-intake/tests/test_notion_writer.py
import sys
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import notion_writer
import config

def test_guard_against_original_thesis_raises():
    import pytest
    with pytest.raises(ValueError):
        notion_writer.guard_against_original_thesis(config.ORIGINAL_THESIS_PAGE_ID)

def test_guard_against_original_thesis_allows_gina_copy():
    notion_writer.guard_against_original_thesis(config.THESIS_PAGE_ID)  # should not raise

def test_create_digest_page_returns_url():
    with patch("notion_writer._client") as mock_client:
        mock_client.pages.create.return_value = {"id": "abc-123", "url": "https://notion.so/abc123"}
        url = notion_writer.create_digest_page(
            "Krown", datetime.date(2026, 8, 5), "## AI Summary\ntest",
            [{"title": "Video 1", "video_id": "v1", "transcript": "transcript text"}]
        )
    assert url == "https://notion.so/abc123"
    assert mock_client.pages.create.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_notion_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'notion_writer'`

- [ ] **Step 3: Write the notion_writer module**

```python
# scouts/youtube-intake/notion_writer.py
import os
import datetime

from notion_client import Client

import config

_client = Client(auth=os.getenv("NOTION_API_KEY"))


def guard_against_original_thesis(page_id: str) -> None:
    if page_id == config.ORIGINAL_THESIS_PAGE_ID:
        raise ValueError(
            "Refusing to write to Elena's original thesis page. "
            "Automation may only write to config.THESIS_PAGE_ID (the 'for Gina' copy)."
        )


def _rich_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def _markdown_to_paragraph_blocks(markdown: str) -> list[dict]:
    blocks = []
    for line in markdown.split("\n"):
        if not line.strip():
            continue
        if line.startswith("## "):
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": _rich_text(line[3:])},
            })
        elif line.startswith("- "):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rich_text(line[2:])},
            })
        else:
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": _rich_text(line)},
            })
    return blocks


def _create_transcript_subpage(parent_page_id: str, title: str, transcript_text: str) -> str:
    page = _client.pages.create(
        parent={"page_id": parent_page_id},
        icon={"type": "emoji", "emoji": "\U0001F4DD"},
        properties={"title": {"title": _rich_text(title)}},
        children=_markdown_to_paragraph_blocks(transcript_text[:1900] or "(empty transcript)"),
    )
    return page["url"]


def create_digest_page(channel_name: str, date: datetime.date, summary_markdown: str, videos: list[dict]) -> str:
    date_str = date.strftime("%d %b %Y")
    title = f"{channel_name} – Daily Digest ({date_str})"
    page = _client.pages.create(
        parent={"data_source_id": config.NOTION_SOURCES_DATA_SOURCE_ID},
        icon={"type": "emoji", "emoji": "\U0001F3A5"},
        properties={
            "Name": {"title": _rich_text(title)},
            "Source Name": {"rich_text": _rich_text(f"{channel_name} (YouTube)")},
            "Speaker": {"rich_text": _rich_text(channel_name)},
            "Date": {"date": {"start": date.isoformat()}},
        },
        children=_markdown_to_paragraph_blocks(summary_markdown),
    )
    for video in videos:
        _create_transcript_subpage(page["id"], f"TRANSCRIPT - {video['title']}", video["transcript"])
    return page["url"]


def create_episode_page(title: str, speaker: str, date: datetime.date, summary_markdown: str, video_id: str, transcript_text: str) -> str:
    page = _client.pages.create(
        parent={"data_source_id": config.NOTION_SOURCES_DATA_SOURCE_ID},
        icon={"type": "emoji", "emoji": "\U0001F30E"},
        properties={
            "Name": {"title": _rich_text(title)},
            "Source Name": {"rich_text": _rich_text("MacroVoices")},
            "Speaker": {"rich_text": _rich_text(speaker)},
            "Date": {"date": {"start": date.isoformat()}},
        },
        children=_markdown_to_paragraph_blocks(summary_markdown),
    )
    _create_transcript_subpage(page["id"], "TRANSCRIPT", transcript_text)
    return page["url"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_notion_writer.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scouts/youtube-intake/notion_writer.py scouts/youtube-intake/tests/test_notion_writer.py
git commit -m "scout: add Notion writer with hard guard against original thesis page"
```

---

## Task 7: Thesis update pass

**Files:**
- Create: `scouts/youtube-intake/thesis_updater.py`
- Test: `scouts/youtube-intake/tests/test_thesis_updater.py`

**Interfaces:**
- Consumes: `notion_writer._client`, `notion_writer.guard_against_original_thesis`, `synthesize._client`, `config.THESIS_PAGE_ID`, `config.DAILY_LOGS_ARCHIVE_ID`.
- Produces: `thesis_updater.append_archive_entry(date: "datetime.date", run_summary: str) -> None` — always called once per run, even when nothing material happened.
- Produces: `thesis_updater.fetch_page_plain_text(page_id: str) -> str` — recursively walks a Notion page's block tree and returns a flat plain-text rendering, for feeding full-document context to an LLM prompt (not for re-writing the page, formatting is not preserved).
- Produces: `thesis_updater.assess_materiality(new_content_summaries: list[str], current_thesis: str) -> str | None` — returns a markdown snapshot-update block if the new content is material, or `None` if not. `current_thesis` must be the FULL thesis page content (Snapshot + Operating Thesis + Key Levels + Decision Tree), not just the Snapshot section — a contradiction can live in the Operating Thesis just as easily as the Snapshot (see the 3 Aug 2026 manual correction to the Operating Thesis section as the reference case). Comparing only against the Snapshot excerpt was flagged as a real gap and fixed before this task was implemented, not after.

- [ ] **Step 1: Write the failing test**

```python
# scouts/youtube-intake/tests/test_thesis_updater.py
import sys
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import thesis_updater

def _fake_anthropic_response(text: str):
    fake_block = MagicMock()
    fake_block.text = text
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    return fake_response

def test_assess_materiality_returns_none_when_not_material():
    with patch("thesis_updater._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response("MATERIAL: false")
        result = thesis_updater.assess_materiality(["minor BTC clip, no new signal"], "full thesis text")
    assert result is None

def test_assess_materiality_returns_block_when_material():
    with patch("thesis_updater._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response(
            "MATERIAL: true\nUPDATE:\n- New Fed hike signal confirmed"
        )
        result = thesis_updater.assess_materiality(["Fed hiked rates unexpectedly"], "full thesis text")
    assert result is not None
    assert "Fed hike" in result

def test_append_archive_entry_calls_notion():
    with patch("thesis_updater._notion_client") as mock_client:
        thesis_updater.append_archive_entry(datetime.date(2026, 8, 5), "Test run summary, nothing material.")
    assert mock_client.blocks.children.append.called

def test_fetch_page_plain_text_walks_children_and_paginates():
    with patch("thesis_updater._notion_client") as mock_client:
        page1 = {
            "results": [
                {"id": "b1", "type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Snapshot"}]}, "has_children": False},
                {"id": "b2", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Bond market is the story."}]}, "has_children": True},
            ],
            "has_more": True,
            "next_cursor": "cursor-2",
        }
        page2 = {
            "results": [
                {"id": "b3", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Second top-level block."}]}, "has_children": False},
            ],
            "has_more": False,
            "next_cursor": None,
        }
        child_page = {
            "results": [
                {"id": "b2a", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Nested child of b2."}]}, "has_children": False},
            ],
            "has_more": False,
            "next_cursor": None,
        }

        def _list(block_id, start_cursor=None):
            if block_id == "page-1" and start_cursor is None:
                return page1
            if block_id == "page-1" and start_cursor == "cursor-2":
                return page2
            if block_id == "b2":
                return child_page
            raise AssertionError(f"unexpected call: {block_id}, {start_cursor}")

        mock_client.blocks.children.list.side_effect = _list
        text = thesis_updater.fetch_page_plain_text("page-1")

    assert "Snapshot" in text
    assert "Bond market is the story." in text
    assert "Nested child of b2." in text
    assert "Second top-level block." in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_thesis_updater.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'thesis_updater'`

- [ ] **Step 3: Write the thesis_updater module**

```python
# scouts/youtube-intake/thesis_updater.py
import datetime
import os
import re

import anthropic
from notion_client import Client

import config
from notion_writer import guard_against_original_thesis

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_notion_client = Client(auth=os.getenv("NOTION_API_KEY"))

MODEL = "claude-sonnet-5"

MATERIALITY_PROMPT = """You maintain Elena's rolling macro/crypto investment thesis. Below is the FULL current
thesis page (Today/This Week Snapshot, Operating Thesis, Key Levels, and Decision Tree sections), followed by
summaries of new content logged today.

Current thesis (full page):
{current_thesis}

New content today:
{new_content}

Does any of this new content confirm, contradict, or add a materially new angle to ANY part of the current
thesis above — not just the Snapshot section, but also the Operating Thesis, Key Levels, or Decision Tree
(a contradiction can live in the deeper sections just as easily as the Snapshot; do not limit your check to
the Snapshot bullets)? Restating something already covered does not count. If yes, respond:
MATERIAL: true
UPDATE:
- <bulleted update points, in the same style as the existing snapshot, noting which section(s) are affected>

If no:
MATERIAL: false"""


def fetch_page_plain_text(page_id: str) -> str:
    """Recursively flatten a Notion page's block tree to plain text for LLM context. Formatting (bold,
    colors, callout/table structure) is not preserved — this is read-only context, never used to write back."""
    lines: list[str] = []

    def _walk(block_id: str) -> None:
        cursor = None
        while True:
            resp = _notion_client.blocks.children.list(block_id=block_id, start_cursor=cursor)
            for block in resp["results"]:
                block_type = block["type"]
                data = block.get(block_type, {})
                rich_text = data.get("rich_text", [])
                text = "".join(rt.get("plain_text", "") for rt in rich_text)
                if text:
                    lines.append(text)
                if block.get("has_children"):
                    _walk(block["id"])
            if resp.get("has_more"):
                cursor = resp["next_cursor"]
            else:
                break

    _walk(page_id)
    return "\n".join(lines)


def assess_materiality(new_content_summaries: list[str], current_thesis: str) -> str | None:
    new_content = "\n\n".join(new_content_summaries)
    prompt = MATERIALITY_PROMPT.format(current_thesis=current_thesis, new_content=new_content)
    response = _client.messages.create(
        model=MODEL, max_tokens=1500, messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text
    if re.search(r"MATERIAL:\s*true", text, re.IGNORECASE):
        update_match = re.search(r"UPDATE:\s*(.+)", text, re.DOTALL)
        return update_match.group(1).strip() if update_match else None
    return None


def append_archive_entry(date: datetime.date, run_summary: str) -> None:
    guard_against_original_thesis(config.DAILY_LOGS_ARCHIVE_ID)  # no-op here, but keeps the guard pattern consistent
    date_str = date.isoformat()
    _notion_client.blocks.children.append(
        block_id=config.DAILY_LOGS_ARCHIVE_ID,
        children=[{
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": f"{date_str} – Daily scout run"}}],
                "children": [{
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": run_summary}}]},
                }],
            },
        }],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_thesis_updater.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scouts/youtube-intake/thesis_updater.py scouts/youtube-intake/tests/test_thesis_updater.py
git commit -m "scout: add thesis materiality assessment and archive logging"
```

---

## Task 8: Main orchestration script

**Files:**
- Create: `scouts/youtube-intake/run_daily.py`
- Test: `scouts/youtube-intake/tests/test_run_daily.py`

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: `run_daily.main() -> None` — the Railway cron entrypoint. Calls `thesis_updater.fetch_page_plain_text` + `thesis_updater.assess_materiality` on every run that logged real content, and folds a flagged material update into the archive entry — this wiring is the actual point of Task 7's materiality assessment; a version of this task that builds `assess_materiality` but never calls it does not satisfy the plan.
- Produces: `run_daily.process_channel(channel: "config.Channel", led: "ledger.Ledger") -> list[dict]` — returns a list of `{"one_liner": str, "content": str}` per group logged. `one_liner` is for the archive run-summary; `content` is the full synthesized summary_md, passed to `assess_materiality` (a one-liner like "Krown digest: 3 videos -> url" is too thin to judge materiality against).

- [ ] **Step 1: Write the failing test**

```python
# scouts/youtube-intake/tests/test_run_daily.py
import sys
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import run_daily
import config
import ledger
from rss import VideoEntry
from transcript import TranscriptResult
from synthesize import VideoClassification

def test_process_channel_skips_when_no_new_videos():
    channel = config.CHANNELS[1]  # Krown
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    with patch("run_daily.rss.fetch_recent_videos", return_value=[]):
        summaries = run_daily.process_channel(channel, led)
    assert summaries == []

def test_process_channel_logs_real_content_and_marks_ledger():
    channel = config.CHANNELS[1]  # Krown, digest format
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    fake_entry = VideoEntry("v1", "Real Signal Video", datetime.date(2026, 8, 5), "Krown")

    with patch("run_daily.rss.fetch_recent_videos", return_value=[fake_entry]), \
         patch("run_daily.transcript.get_transcript", return_value=TranscriptResult("v1", "real transcript", "captions")), \
         patch("run_daily.synthesize.classify_video", return_value=VideoClassification("v1", True, "has price levels")), \
         patch("run_daily.synthesize.write_digest_summary", return_value="## AI Summary\ntest"), \
         patch("run_daily.notion_writer.create_digest_page", return_value="https://notion.so/newpage") as mock_create:
        summaries = run_daily.process_channel(channel, led)

    assert len(summaries) == 1
    assert summaries[0]["content"] == "## AI Summary\ntest"
    assert "https://notion.so/newpage" in summaries[0]["one_liner"]
    assert led.is_processed("v1")
    assert mock_create.called

def test_process_channel_skips_promo_only_videos():
    channel = config.CHANNELS[1]
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    fake_entry = VideoEntry("v1", "Buy My Course", datetime.date(2026, 8, 5), "Krown")

    with patch("run_daily.rss.fetch_recent_videos", return_value=[fake_entry]), \
         patch("run_daily.transcript.get_transcript", return_value=TranscriptResult("v1", "promo transcript", "captions")), \
         patch("run_daily.synthesize.classify_video", return_value=VideoClassification("v1", False, "pure promo")), \
         patch("run_daily.notion_writer.create_digest_page") as mock_create:
        summaries = run_daily.process_channel(channel, led)

    assert not mock_create.called
    assert led.is_processed("v1")  # still marked so we don't re-check it every day

def test_main_assesses_materiality_against_full_thesis_and_flags_archive():
    fake_channel = MagicMock()
    with patch("run_daily.config.CHANNELS", [fake_channel]), \
         patch("run_daily.ledger.Ledger.load"), \
         patch("run_daily.ledger.Ledger.save"), \
         patch("run_daily.process_channel", return_value=[
             {"one_liner": "Krown digest (2026-08-05): 1 video(s) -> https://notion.so/x", "content": "Fed hiked rates unexpectedly"}
         ]), \
         patch("run_daily.thesis_updater.fetch_page_plain_text", return_value="FULL THESIS TEXT") as mock_fetch, \
         patch("run_daily.thesis_updater.assess_materiality", return_value="- New Fed hike signal confirmed") as mock_assess, \
         patch("run_daily.thesis_updater.append_archive_entry") as mock_archive:
        run_daily.main()

    mock_fetch.assert_called_once_with(config.THESIS_PAGE_ID)
    mock_assess.assert_called_once_with(["Fed hiked rates unexpectedly"], "FULL THESIS TEXT")
    assert mock_archive.called
    archived_summary = mock_archive.call_args[0][1]
    assert "Krown digest" in archived_summary
    assert "MATERIAL UPDATE FLAGGED" in archived_summary
    assert "New Fed hike signal confirmed" in archived_summary

def test_main_skips_materiality_check_when_nothing_logged():
    with patch("run_daily.config.CHANNELS", [MagicMock()]), \
         patch("run_daily.ledger.Ledger.load"), \
         patch("run_daily.ledger.Ledger.save"), \
         patch("run_daily.process_channel", return_value=[]), \
         patch("run_daily.thesis_updater.fetch_page_plain_text") as mock_fetch, \
         patch("run_daily.thesis_updater.assess_materiality") as mock_assess, \
         patch("run_daily.thesis_updater.append_archive_entry") as mock_archive:
        run_daily.main()

    assert not mock_fetch.called
    assert not mock_assess.called
    assert mock_archive.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_run_daily.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'run_daily'`

- [ ] **Step 3: Write the orchestration script**

```python
# scouts/youtube-intake/run_daily.py
import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import config
import rss
import ledger
import transcript
import synthesize
import notion_writer
import thesis_updater

LEDGER_PATH = Path(__file__).parent / "processed.json"


def process_channel(channel: "config.Channel", led: "ledger.Ledger") -> list[dict]:
    entries = rss.fetch_recent_videos(channel)
    groups = ledger.group_new_videos(entries, led)
    summaries = []

    for (channel_name, date), videos in groups.items():
        real_content_videos = []
        for video in videos:
            result = transcript.get_transcript(video.video_id)
            if result.text is None:
                led.mark_processed(video.video_id, "")  # flagged/skipped, don't retry forever
                continue
            classification = synthesize.classify_video(video.title, result.text)
            if classification.has_real_content:
                real_content_videos.append({
                    "title": video.title, "video_id": video.video_id, "transcript": result.text,
                })
            led.mark_processed(video.video_id, "")

        if not real_content_videos:
            continue

        if channel.format == "episode":
            for v in real_content_videos:
                summary_md = synthesize.write_episode_summary(v["title"], channel_name, v["transcript"])
                url = notion_writer.create_episode_page(
                    v["title"], channel_name, date, summary_md, v["video_id"], v["transcript"]
                )
                led.mark_processed(v["video_id"], url)
                summaries.append({"one_liner": f"{channel_name}: {v['title']} -> {url}", "content": summary_md})
        else:
            summary_md = synthesize.write_digest_summary(channel_name, date, real_content_videos)
            url = notion_writer.create_digest_page(channel_name, date, summary_md, real_content_videos)
            for v in real_content_videos:
                led.mark_processed(v["video_id"], url)
            summaries.append({
                "one_liner": f"{channel_name} digest ({date}): {len(real_content_videos)} video(s) -> {url}",
                "content": summary_md,
            })

    return summaries


def main() -> None:
    led = ledger.Ledger.load(LEDGER_PATH)
    all_entries: list[dict] = []

    for channel in config.CHANNELS:
        try:
            all_entries.extend(process_channel(channel, led))
        except Exception as exc:
            all_entries.append({"one_liner": f"{channel.name}: RUN FAILED - {exc}", "content": ""})

    led.save(LEDGER_PATH)

    today = datetime.date.today()
    if not all_entries:
        thesis_updater.append_archive_entry(today, "No new content across any of the 4 channels today.")
        return

    run_summary = "\n".join(e["one_liner"] for e in all_entries)

    content_summaries = [e["content"] for e in all_entries if e["content"]]
    if content_summaries:
        current_thesis = thesis_updater.fetch_page_plain_text(config.THESIS_PAGE_ID)
        material_update = thesis_updater.assess_materiality(content_summaries, current_thesis)
        if material_update:
            run_summary += (
                "\n\n**MATERIAL UPDATE FLAGGED — needs a manual Snapshot/Operating Thesis rewrite:**\n"
                + material_update
            )

    thesis_updater.append_archive_entry(today, run_summary)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scouts/youtube-intake && python -m pytest tests/test_run_daily.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd scouts/youtube-intake && python -m pytest -v`
Expected: all tests across all modules PASS.

- [ ] **Step 6: Commit**

```bash
git add scouts/youtube-intake/run_daily.py scouts/youtube-intake/tests/test_run_daily.py
git commit -m "scout: add main orchestration script tying all modules together"
```

---

## Task 9: Railway deployment config

**Files:**
- Create: `scouts/youtube-intake/Procfile`
- Create: `scouts/youtube-intake/railway.json`
- Modify: `scouts/youtube-intake/README.md`

**Interfaces:**
- Consumes: `run_daily.main`.
- Produces: a deployable Railway cron service definition.

- [ ] **Step 1: Write the Procfile**

```
worker: python run_daily.py
```

- [ ] **Step 2: Write the Railway cron config**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python run_daily.py",
    "cronSchedule": "0 10 * * *",
    "restartPolicyType": "NEVER"
  }
}
```

Note: `0 10 * * *` is UTC. CET is UTC+1 (UTC+2 in summer/CEST) — 10:00 UTC lands at 11:00-12:00 CET/CEST, giving several hours of buffer before the 3pm CET deadline even accounting for a slow Gemini-fallback run. Confirm actual UTC offset at deploy time since it changes with daylight saving.

- [ ] **Step 3: Update the README**

```markdown
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
```

- [ ] **Step 4: Commit**

```bash
git add scouts/youtube-intake/Procfile scouts/youtube-intake/railway.json scouts/youtube-intake/README.md
git commit -m "scout: add Railway deployment config and update README"
```

---

## Self-Review Notes

**Spec coverage check:**
- RSS discovery (Section 1 of spec) → Task 2. ✓
- Two-tier transcript extraction with IP-block fallback (Section 3) → Task 4. ✓
- Promo filtering by content judgment (Section 4) → Task 5 (`classify_video`). ✓
- Daily-digest grouping vs. per-episode format (Section 5) → Task 3 (grouping) + Task 6 (both page formats) + Task 8 (dispatches by `channel.format`). ✓
- Direct thesis writes with no approval gate, hard guard against the original page (Section 6) → Task 7 + `guard_against_original_thesis` in Task 6, called in Task 7. ✓
- Railway hosting (Section 7) → Task 9. ✓
- Error handling (transcript failure, RSS failure, Notion failure) → Task 4 (`source="failed"`), Task 8 (`main()`'s per-channel try/except; failed transcripts marked processed with empty URL so they aren't retried forever but are visible in the ledger as a blank entry).
- Materiality judgment for thesis updates being an LLM call, not deterministic rules (spec's ambiguity-fix note) → Task 7 (`assess_materiality`).

**Scope confirmed with Elena (4 Aug 2026): log + flag, not full auto-rewrite.** This plan builds `assess_materiality` and the archive-append flow (Task 7), wired into `run_daily.main()` (Task 8) so it actually runs on every day with real content — it does NOT rewrite the Snapshot/Bottom-line/Operating-Thesis sections in place the way the 2026-08-03 manual run did (targeted `update_content` search-and-replace against known section headers). That's a meaningfully harder problem — the manual run had a human (me) reading the whole page and making judgment calls about what to demote vs. correct vs. leave alone. Phase 1 (this plan): log new content, assess materiality against the FULL current thesis page (not just the Snapshot excerpt — fixed 4 Aug 2026, see Task 7), append a clear, visibly-flagged archive-log summary of *what changed and why it might matter*. Elena (or a future Gina session) does the actual snapshot rewrite using that flag, same as the manual pattern that already worked on 2026-08-03. Full auto-rewrite is a Phase 2 candidate, not in scope here.

**Type consistency check:** `VideoEntry`, `TranscriptResult`, `VideoClassification`, `Ledger`, `Channel` — all used consistently by name and field across Tasks 2-8. `notion_writer.create_digest_page` and `create_episode_page` signatures match what Task 8's `process_channel` calls. Confirmed no drift.
