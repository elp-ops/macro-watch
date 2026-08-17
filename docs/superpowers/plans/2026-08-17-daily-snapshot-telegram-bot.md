# Daily Snapshot Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python script, run once daily by a Railway cron job, that fetches live market prices, compares them against Elena's tracked trigger levels, pulls the last day's scouted source material from Notion, and sends one plain-text summary message to her personal Telegram chat.

**Architecture:** Seven small, single-purpose modules (prices, trigger comparison, Notion reader, regime tag, on-deck channel list, message composer, Telegram sender) wired together by one orchestrator (`main.py`). No always-on process — the script runs, sends one message, exits. Each external call (price API, Notion, Anthropic, Telegram) is isolated in its own module so a failure in one doesn't take down the whole run.

**Tech Stack:** Python 3.11+, `requests`, `python-dotenv`, `notion-client`, `yfinance`, `anthropic`. No web framework, no bot listener framework — this bot never receives messages, only sends one.

**Spec:** [`2026-08-17-daily-snapshot-telegram-bot-design.md`](../specs/2026-08-17-daily-snapshot-telegram-bot-design.md)

## Global Constraints

- No Anthropic-hosted infrastructure (Claude Code Routines) — this deploys to Railway, per standing rule.
- Message drafting uses Claude Haiku (`claude-haiku-4-5-20251001`) — cheap formatting task, not reasoning, per the project's cost-efficiency rule.
- No invented data — the message composer prompt must explicitly forbid adding numbers, claims, or opinions not present in the structured input it's given.
- No directional opinion or trading recommendation in the output — facts and status only.
- One fixed recipient (Elena's personal Telegram chat), no multi-user support.
- Free data sources only, no paid API keys for price data (CoinGecko, FRED CSV endpoint, yfinance).

## Architecture note: trigger levels are a maintained config, not parsed from Notion prose

The design doc describes comparing live prices "against the trigger levels already logged in Key Levels." Parsing arbitrary, differently-worded Notion prose (`"~91k"`, `"66k-support"`, `"4.6–4.8%"`) reliably with code is fragile and would break silently whenever the wording changes. Instead, `config.py` holds a small `TRACKED_LEVELS` list, seeded below with the actual current values from the thesis page as of 17 Aug 2026. This is a deliberate, visible trade-off: whoever updates the Key Levels section in Notion should also update `TRACKED_LEVELS` in this file. It keeps the comparison deterministic and testable instead of LLM-fuzzy or regex-fragile. This is called out here so it's not a silent divergence from the spec.

---

## Task 1: Scaffolding, config, and the regime-tag module

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/requirements.txt`
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/.env.example`
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/.gitignore`
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/config.py`
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/regime.py`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_regime.py`

**Interfaces:**
- Produces: `config.TRACKED_LEVELS: list[dict]` (keys: `asset`, `label`, `direction`, `threshold`, `note`), `config.THESIS_PAGE_ID: str`, `config.DAILY_LOGS_ARCHIVE_ID: str`, `regime.regime_tag(us10y: float | None) -> str`

- [ ] **Step 1: Create the folder and dependency files**

`projects/macro-watch/telegram-bot/daily-snapshot/requirements.txt`:
```
requests
python-dotenv
anthropic
notion-client
yfinance
pytest
```

`projects/macro-watch/telegram-bot/daily-snapshot/.env.example`:
```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ANTHROPIC_API_KEY=
NOTION_API_KEY=
```

`projects/macro-watch/telegram-bot/daily-snapshot/.gitignore`:
```
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 2: Write `config.py`**

```python
# config.py
THESIS_PAGE_ID = "3b1490cf-c56c-8015-9648-f388049211d1"
DAILY_LOGS_ARCHIVE_ID = "3b8490cf-c56c-83f0-a521-81c81778d9bd"

# Seeded from the thesis page's Key Levels section as of 17 Aug 2026.
# Whoever edits Key Levels in Notion should update this list to match.
TRACKED_LEVELS = [
    {
        "asset": "BTC", "label": "BTC bull flip", "direction": "above",
        "threshold": 91000, "note": "trend flip, upside, needs a reclaim and hold",
    },
    {
        "asset": "BTC", "label": "BTC alt-flip (Dirk, moving target)", "direction": "above",
        "threshold": 84000,
        "note": "second, lower flip level from a different source; disagrees with the 91k line, treat as a moving target",
    },
    {
        "asset": "BTC", "label": "BTC support", "direction": "below",
        "threshold": 66000, "note": "downside support, start of the staged deploy zone",
    },
    {
        "asset": "US10Y", "label": "10Y danger band", "direction": "above",
        "threshold": 4.6, "note": "escalation threshold, upper bound 4.8%",
    },
    {
        "asset": "US30Y", "label": "30Y structural break", "direction": "above",
        "threshold": 5.0, "note": "already broke this in Aug 2026, watch for further deterioration",
    },
    {
        "asset": "BRENT", "label": "Oil (Brent) escalation line", "direction": "above",
        "threshold": 120, "note": "duration-risk line",
    },
    {
        "asset": "GOLD", "label": "Gold resistance", "direction": "above",
        "threshold": 4550, "note": "Fibonacci resistance level",
    },
]
```

- [ ] **Step 3: Write the failing test for `regime_tag`**

```python
# tests/test_regime.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from regime import regime_tag


def test_regime_unavailable_when_no_data():
    assert regime_tag(None) == "Regime unavailable (10Y fetch failed)"


def test_stress_regime_below_3_7():
    assert "stress regime" in regime_tag(3.5)


def test_neutral_chop_3_7_to_4():
    assert "Neutral chop" in regime_tag(3.9)


def test_tight_money_above_4_below_band():
    result = regime_tag(4.2)
    assert "Tight money" in result and "escalation" not in result


def test_escalation_zone_4_6_to_4_8():
    assert "escalation zone" in regime_tag(4.7)


def test_above_escalation_band():
    assert "above escalation band" in regime_tag(5.0)
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_regime.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'regime'` (file doesn't exist yet).

- [ ] **Step 5: Write `regime.py`**

```python
# regime.py
def regime_tag(us10y: float | None) -> str:
    if us10y is None:
        return "Regime unavailable (10Y fetch failed)"
    if us10y < 3.7:
        return f"Something is breaking — stress regime (10Y {us10y}%, below 3.7%)"
    if us10y < 4.0:
        return f"Neutral chop (10Y {us10y}%, 3.7–4%)"
    if us10y < 4.6:
        return f"Tight money (10Y {us10y}%, above 4%, below escalation band)"
    if us10y <= 4.8:
        return f"Tight money — escalation zone (10Y {us10y}%, in the 4.6–4.8% band)"
    return f"Tight money — above escalation band (10Y {us10y}%, past 4.8%)"
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_regime.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/requirements.txt telegram-bot/daily-snapshot/.env.example \
  telegram-bot/daily-snapshot/.gitignore telegram-bot/daily-snapshot/config.py \
  telegram-bot/daily-snapshot/regime.py telegram-bot/daily-snapshot/tests/test_regime.py
git commit -m "feat(daily-snapshot): scaffolding, config, regime-tag module"
```

---

## Task 2: Price fetch module

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/prices.py`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_prices.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `prices.fetch_all_prices() -> dict[str, float | None]` with keys `BTC`, `US2Y`, `US10Y`, `US30Y`, `DXY`, `BRENT`, `GOLD` — this exact dict shape is what Task 3 (`levels.py`) and Task 7 (`main.py`) consume.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prices.py
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import prices


def test_fetch_btc_parses_coingecko_response():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"bitcoin": {"usd": 63500.0}}
    fake_resp.raise_for_status.return_value = None
    with patch("prices.requests.get", return_value=fake_resp) as mock_get:
        result = prices.fetch_btc()
    assert result == 63500.0
    assert "coingecko" in mock_get.call_args[0][0]


def test_fetch_treasury_yield_skips_missing_values():
    csv_text = "DATE,DGS10\n2026-08-15,.\n2026-08-16,.\n2026-08-14,4.70\n"
    fake_resp = MagicMock()
    fake_resp.text = csv_text
    fake_resp.raise_for_status.return_value = None
    with patch("prices.requests.get", return_value=fake_resp):
        result = prices.fetch_treasury_yield("DGS10")
    assert result == 4.70


def test_fetch_treasury_yield_returns_none_if_all_missing():
    csv_text = "DATE,DGS10\n2026-08-15,.\n2026-08-16,.\n"
    fake_resp = MagicMock()
    fake_resp.text = csv_text
    fake_resp.raise_for_status.return_value = None
    with patch("prices.requests.get", return_value=fake_resp):
        result = prices.fetch_treasury_yield("DGS10")
    assert result is None


def test_fetch_yfinance_last_close():
    import pandas as pd
    fake_history = pd.DataFrame({"Close": [98.5, 99.2]})
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = fake_history
    with patch("prices.yf.Ticker", return_value=fake_ticker):
        result = prices.fetch_yfinance_last_close("DX-Y.NYB")
    assert result == 99.2


def test_fetch_yfinance_last_close_returns_none_when_empty():
    import pandas as pd
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = pd.DataFrame()
    with patch("prices.yf.Ticker", return_value=fake_ticker):
        result = prices.fetch_yfinance_last_close("DX-Y.NYB")
    assert result is None


def test_fetch_all_prices_isolates_one_failure():
    def fail():
        raise RuntimeError("source down")

    with patch("prices.fetch_btc", side_effect=fail), \
         patch("prices.fetch_treasury_yield", return_value=4.5), \
         patch("prices.fetch_yfinance_last_close", return_value=100.0):
        result = prices.fetch_all_prices()

    assert result["BTC"] is None
    assert result["US10Y"] == 4.5
    assert result["DXY"] == 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_prices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prices'`

- [ ] **Step 3: Write `prices.py`**

```python
# prices.py
import csv
import io

import requests
import yfinance as yf

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def fetch_btc() -> float | None:
    resp = requests.get(COINGECKO_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()["bitcoin"]["usd"]


def fetch_treasury_yield(series_id: str) -> float | None:
    url = FRED_CSV_URL.format(series_id=series_id)
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    for row in reversed(rows):
        value = row[series_id]
        if value != ".":
            return float(value)
    return None


def fetch_yfinance_last_close(ticker: str) -> float | None:
    history = yf.Ticker(ticker).history(period="5d")
    if history.empty:
        return None
    return float(history["Close"].iloc[-1])


def fetch_all_prices() -> dict[str, float | None]:
    fetchers = {
        "BTC": fetch_btc,
        "US2Y": lambda: fetch_treasury_yield("DGS2"),
        "US10Y": lambda: fetch_treasury_yield("DGS10"),
        "US30Y": lambda: fetch_treasury_yield("DGS30"),
        "DXY": lambda: fetch_yfinance_last_close("DX-Y.NYB"),
        "BRENT": lambda: fetch_yfinance_last_close("BZ=F"),
        "GOLD": lambda: fetch_yfinance_last_close("GC=F"),
    }
    prices: dict[str, float | None] = {}
    for key, fetch in fetchers.items():
        try:
            prices[key] = fetch()
        except Exception:
            prices[key] = None
    return prices
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_prices.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/prices.py telegram-bot/daily-snapshot/tests/test_prices.py
git commit -m "feat(daily-snapshot): price fetch module (BTC, yields, DXY, oil, gold)"
```

---

## Task 3: Trigger comparison module

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/levels.py`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_levels.py`

**Interfaces:**
- Consumes: `prices.fetch_all_prices()`'s output shape (`dict[str, float | None]`), `config.TRACKED_LEVELS`
- Produces: `levels.compare_to_triggers(prices: dict, tracked_levels: list[dict]) -> list[dict]`, each result dict has keys `asset`, `label`, `value`, `threshold`, `direction`, `note`, `status` (`status` is one of `"triggered"`, `"near"`, `"ok"`, `"unavailable"`) — this shape is what Task 5 (`message_composer.py`) and Task 7 (`main.py`) consume.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_levels.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from levels import compare_to_triggers

LEVEL_ABOVE = {"asset": "BTC", "label": "test above", "direction": "above", "threshold": 100, "note": "n"}
LEVEL_BELOW = {"asset": "BTC", "label": "test below", "direction": "below", "threshold": 100, "note": "n"}


def test_above_triggered():
    result = compare_to_triggers({"BTC": 101}, [LEVEL_ABOVE])
    assert result[0]["status"] == "triggered"


def test_above_near():
    result = compare_to_triggers({"BTC": 99}, [LEVEL_ABOVE])  # within 2% below threshold
    assert result[0]["status"] == "near"


def test_above_ok():
    result = compare_to_triggers({"BTC": 90}, [LEVEL_ABOVE])
    assert result[0]["status"] == "ok"


def test_below_triggered():
    result = compare_to_triggers({"BTC": 99}, [LEVEL_BELOW])
    assert result[0]["status"] == "triggered"


def test_below_near():
    result = compare_to_triggers({"BTC": 101}, [LEVEL_BELOW])  # within 2% above threshold
    assert result[0]["status"] == "near"


def test_below_ok():
    result = compare_to_triggers({"BTC": 110}, [LEVEL_BELOW])
    assert result[0]["status"] == "ok"


def test_unavailable_when_price_missing():
    result = compare_to_triggers({"BTC": None}, [LEVEL_ABOVE])
    assert result[0]["status"] == "unavailable"


def test_unavailable_when_asset_missing_from_prices():
    result = compare_to_triggers({}, [LEVEL_ABOVE])
    assert result[0]["status"] == "unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_levels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'levels'`

- [ ] **Step 3: Write `levels.py`**

```python
# levels.py
NEAR_MARGIN = 0.02  # within 2% of the threshold counts as "near"


def compare_to_triggers(prices: dict, tracked_levels: list[dict]) -> list[dict]:
    results = []
    for level in tracked_levels:
        value = prices.get(level["asset"])
        status = _status_for(value, level["direction"], level["threshold"])
        results.append({
            "asset": level["asset"],
            "label": level["label"],
            "value": value,
            "threshold": level["threshold"],
            "direction": level["direction"],
            "note": level["note"],
            "status": status,
        })
    return results


def _status_for(value: float | None, direction: str, threshold: float) -> str:
    if value is None:
        return "unavailable"
    if direction == "above":
        if value >= threshold:
            return "triggered"
        if value >= threshold * (1 - NEAR_MARGIN):
            return "near"
        return "ok"
    # direction == "below"
    if value <= threshold:
        return "triggered"
    if value <= threshold * (1 + NEAR_MARGIN):
        return "near"
    return "ok"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_levels.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/levels.py telegram-bot/daily-snapshot/tests/test_levels.py
git commit -m "feat(daily-snapshot): trigger comparison module"
```

---

## Task 4: On-deck channel list module

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/on_deck.py`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_on_deck.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `on_deck.on_deck_channels(today: datetime.date) -> list[str]` — consumed by Task 7 (`main.py`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_on_deck.py
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from on_deck import on_deck_channels


def test_thursday_includes_macrovoices():
    thursday = datetime.date(2026, 8, 13)  # confirmed Thursday
    result = on_deck_channels(thursday)
    assert any("MacroVoices" in line for line in result)


def test_monday_excludes_macrovoices():
    monday = datetime.date(2026, 8, 17)  # confirmed Monday
    result = on_deck_channels(monday)
    assert not any("MacroVoices" in line for line in result)


def test_always_includes_daily_channels():
    monday = datetime.date(2026, 8, 17)
    result = on_deck_channels(monday)
    joined = " ".join(result)
    assert "Krown" in joined
    assert "Dirk" in joined
    assert "Ivan on Tech" in joined
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_on_deck.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'on_deck'`

- [ ] **Step 3: Write `on_deck.py`**

```python
# on_deck.py
import datetime

THURSDAY = 3  # datetime.date.weekday(): Monday=0 ... Sunday=6


def on_deck_channels(today: datetime.date) -> list[str]:
    channels = []
    if today.weekday() == THURSDAY:
        channels.append("MacroVoices (weekly, usually Thursdays — expect a new episode today)")
    channels.append("Krown (near-daily digest, check for a fresh one)")
    channels.append("Dirk / IntelligentCryptocurrency (near-daily digest, check for a fresh one)")
    channels.append("Ivan on Tech (near-daily digest, check for a fresh one)")
    return channels
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_on_deck.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/on_deck.py telegram-bot/daily-snapshot/tests/test_on_deck.py
git commit -m "feat(daily-snapshot): on-deck channel list module"
```

---

## Task 5: Notion reader module

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/notion_reader.py`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_notion_reader.py`

**Interfaces:**
- Consumes: a `notion_client.Client`-shaped object (only `.blocks.children.list(block_id, start_cursor=None)` is used), `config.DAILY_LOGS_ARCHIVE_ID`
- Produces: `notion_reader.fetch_recent_archive_entries(client, archive_page_id: str, since: date) -> list[dict]` (each entry: `date`, `title`, `text`), `notion_reader.count_flagged(entries: list[dict]) -> int` — both consumed by Task 7 (`main.py`)

- [ ] **Step 1: Write the failing tests**

The Daily Logs archive page stores each day's run as a Notion **toggle** block titled `"YYYY-MM-DD: Daily scout run"`, with paragraph blocks as children holding the actual text. This fake client mimics that shape.

```python
# tests/test_notion_reader.py
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_reader import fetch_recent_archive_entries, count_flagged


def _rich_text(content: str) -> list[dict]:
    return [{"plain_text": content}]


class FakeBlocksChildren:
    def __init__(self, responses: dict):
        # responses: block_id -> list of block dicts (single page, no pagination in these fixtures)
        self._responses = responses

    def list(self, block_id: str, start_cursor=None):
        return {"results": self._responses.get(block_id, []), "has_more": False, "next_cursor": None}


class FakeBlocks:
    def __init__(self, children: FakeBlocksChildren):
        self.children = children


class FakeNotionClient:
    def __init__(self, responses: dict):
        self.blocks = FakeBlocks(FakeBlocksChildren(responses))


def _toggle_block(block_id: str, title: str) -> dict:
    return {"id": block_id, "type": "toggle", "toggle": {"rich_text": _rich_text(title)}}


def _paragraph_block(text: str) -> dict:
    return {"type": "paragraph", "paragraph": {"rich_text": _rich_text(text)}}


def test_fetch_recent_archive_entries_filters_by_date_and_pulls_text():
    responses = {
        "archive-page": [
            _toggle_block("old-entry", "2026-08-10: Daily scout run"),
            _toggle_block("recent-entry", "2026-08-17: Daily scout run"),
        ],
        "recent-entry": [_paragraph_block("Krown digest link and notes.")],
    }
    client = FakeNotionClient(responses)

    entries = fetch_recent_archive_entries(client, "archive-page", since=datetime.date(2026, 8, 16))

    assert len(entries) == 1
    assert entries[0]["date"] == "2026-08-17"
    assert entries[0]["title"] == "2026-08-17: Daily scout run"
    assert "Krown digest" in entries[0]["text"]


def test_fetch_recent_archive_entries_ignores_non_toggle_blocks():
    responses = {"archive-page": [{"id": "p1", "type": "paragraph", "paragraph": {"rich_text": _rich_text("noise")}}]}
    client = FakeNotionClient(responses)

    entries = fetch_recent_archive_entries(client, "archive-page", since=datetime.date(2026, 1, 1))

    assert entries == []


def test_count_flagged_counts_only_flagged_entries():
    entries = [
        {"date": "2026-08-16", "title": "t1", "text": "**MATERIAL UPDATE FLAGGED (needs a manual Snapshot/Operating Thesis rewrite):**\n- something"},
        {"date": "2026-08-17", "title": "t2", "text": "just a normal digest, nothing flagged"},
        {"date": "2026-08-15", "title": "t3", "text": "**MATERIAL UPDATE FLAGGED (needs a manual Snapshot/Operating Thesis rewrite):**\n- something else"},
    ]
    assert count_flagged(entries) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_notion_reader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'notion_reader'`

- [ ] **Step 3: Write `notion_reader.py`**

```python
# notion_reader.py
import datetime
import re

FLAGGED_MARKER = "MATERIAL UPDATE FLAGGED"
DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def fetch_recent_archive_entries(client, archive_page_id: str, since: datetime.date) -> list[dict]:
    entries = []
    cursor = None
    while True:
        resp = client.blocks.children.list(block_id=archive_page_id, start_cursor=cursor)
        for block in resp["results"]:
            if block["type"] != "toggle":
                continue
            title = _plain_text(block["toggle"].get("rich_text", []))
            entry_date = _parse_entry_date(title)
            if entry_date is None or entry_date < since:
                continue
            text = _fetch_children_text(client, block["id"])
            entries.append({"date": entry_date.isoformat(), "title": title, "text": text})
        if resp.get("has_more"):
            cursor = resp["next_cursor"]
        else:
            break
    return entries


def count_flagged(entries: list[dict]) -> int:
    return sum(1 for entry in entries if FLAGGED_MARKER in entry["text"])


def _parse_entry_date(title: str) -> datetime.date | None:
    match = DATE_PREFIX_RE.match(title)
    if not match:
        return None
    return datetime.date.fromisoformat(match.group(1))


def _fetch_children_text(client, block_id: str) -> str:
    lines = []
    cursor = None
    while True:
        resp = client.blocks.children.list(block_id=block_id, start_cursor=cursor)
        for block in resp["results"]:
            block_type = block["type"]
            rich_text = block.get(block_type, {}).get("rich_text", [])
            text = _plain_text(rich_text)
            if text:
                lines.append(text)
        if resp.get("has_more"):
            cursor = resp["next_cursor"]
        else:
            break
    return "\n".join(lines)


def _plain_text(rich_text: list[dict]) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_notion_reader.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/notion_reader.py telegram-bot/daily-snapshot/tests/test_notion_reader.py
git commit -m "feat(daily-snapshot): Notion archive reader module"
```

---

## Task 6: Message composer module

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/message_composer.py`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_message_composer.py`

**Interfaces:**
- Consumes: a `dict` with keys `date: str`, `regime: str`, `levels: list[dict]` (shape from Task 3), `reference_levels: dict[str, float | None]` (`US2Y` and `DXY` — tracked in the thesis but with no explicit trigger threshold, so they don't fit the `levels` shape; shown for context only), `on_deck: list[str]` (shape from Task 4), `digest_entries: list[dict]` (shape from Task 5), `flagged_count: int` (from Task 5)
- Produces: `message_composer.compose_message(data: dict) -> str` — consumed by Task 7 (`main.py`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_message_composer.py
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from message_composer import compose_message

SAMPLE_DATA = {
    "date": "2026-08-17",
    "regime": "Tight money — escalation zone (10Y 4.70%, in the 4.6–4.8% band)",
    "levels": [
        {"asset": "BTC", "label": "BTC bull flip", "value": 63500, "threshold": 91000,
         "direction": "above", "note": "trend flip", "status": "ok"},
    ],
    "reference_levels": {"US2Y": 4.23, "DXY": 99.7},
    "on_deck": ["Krown (near-daily digest, check for a fresh one)"],
    "digest_entries": [{"date": "2026-08-16", "title": "2026-08-16: Daily scout run", "text": "some digest text"}],
    "flagged_count": 1,
}


def test_compose_message_returns_model_text():
    fake_response = SimpleNamespace(content=[SimpleNamespace(type="text", text="Final message text")])
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("message_composer.anthropic.Anthropic", return_value=fake_client):
        result = compose_message(SAMPLE_DATA)

    assert result == "Final message text"


def test_compose_message_uses_haiku_and_includes_key_facts_in_prompt():
    fake_response = SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")])
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("message_composer.anthropic.Anthropic", return_value=fake_client):
        compose_message(SAMPLE_DATA)

    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    prompt_text = call_kwargs["messages"][0]["content"]
    assert "2026-08-17" in prompt_text
    assert "escalation zone" in prompt_text
    assert "BTC bull flip" in prompt_text
    assert "4.23" in prompt_text  # reference level, no threshold
    assert "Krown" in prompt_text
    assert "flagged" in prompt_text.lower()
    assert "Do not add, invent, or infer" in prompt_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_message_composer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'message_composer'`

- [ ] **Step 3: Write `message_composer.py`**

```python
# message_composer.py
import anthropic

MODEL = "claude-haiku-4-5-20251001"

PROMPT_TEMPLATE = """You are formatting a daily market snapshot for Elena from already-verified data. \
Do not add, invent, or infer any numbers, price levels, or claims that are not present in the data below. \
Do not add opinion, trading recommendations, or directional bias — report facts and status only. Keep it \
skimmable, CEO-level, short sections, plain text (no markdown headers, this is a Telegram message).

Date: {date}
Regime: {regime}

Live levels vs tracked triggers:
{levels_block}

Other tracked levels (no explicit trigger set, shown for context only):
{reference_block}

On deck today (channels expected to publish):
{on_deck_block}

What came in over the last day:
{digest_block}

Flagged items in this window still waiting on manual thesis review: {flagged_count}

Write the final Telegram message now."""


def compose_message(data: dict) -> str:
    client = anthropic.Anthropic()
    prompt = PROMPT_TEMPLATE.format(
        date=data["date"],
        regime=data["regime"],
        levels_block=_format_levels(data["levels"]),
        reference_block=_format_reference(data["reference_levels"]),
        on_deck_block="\n".join(f"- {c}" for c in data["on_deck"]),
        digest_block=_format_digest(data["digest_entries"]),
        flagged_count=data["flagged_count"],
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _format_levels(levels: list[dict]) -> str:
    lines = []
    for lvl in levels:
        value = "(unavailable)" if lvl["value"] is None else lvl["value"]
        lines.append(
            f"- {lvl['label']}: current {value}, trigger {lvl['direction']} {lvl['threshold']}, "
            f"status: {lvl['status']} ({lvl['note']})"
        )
    return "\n".join(lines)


def _format_reference(reference_levels: dict) -> str:
    lines = []
    for label, value in reference_levels.items():
        shown = "(unavailable)" if value is None else value
        lines.append(f"- {label}: {shown}")
    return "\n".join(lines)


def _format_digest(entries: list[dict]) -> str:
    if not entries:
        return "(nothing new logged in this window)"
    lines = []
    for entry in entries:
        lines.append(f"- {entry['date']}: {entry['title']}\n{entry['text'][:500]}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_message_composer.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/message_composer.py telegram-bot/daily-snapshot/tests/test_message_composer.py
git commit -m "feat(daily-snapshot): message composer module (Haiku, no-invention prompt)"
```

---

## Task 7: Telegram sender module

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/telegram_sender.py`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_telegram_sender.py`

**Interfaces:**
- Consumes: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables, the `str` produced by `message_composer.compose_message`
- Produces: `telegram_sender.send_message(text: str) -> None` — consumed by Task 8 (`main.py`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_telegram_sender.py
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import telegram_sender


def test_send_message_posts_to_correct_url_with_payload(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    fake_resp = MagicMock()
    fake_resp.raise_for_status.return_value = None

    with patch("telegram_sender.requests.post", return_value=fake_resp) as mock_post:
        telegram_sender.send_message("hello world")

    called_url = mock_post.call_args[0][0]
    called_json = mock_post.call_args.kwargs["json"]
    assert called_url == "https://api.telegram.org/bottest-token/sendMessage"
    assert called_json == {"chat_id": "12345", "text": "hello world"}


def test_send_message_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    fake_resp = MagicMock()
    fake_resp.raise_for_status.side_effect = RuntimeError("HTTP error")

    with patch("telegram_sender.requests.post", return_value=fake_resp):
        with pytest.raises(RuntimeError):
            telegram_sender.send_message("hello world")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_telegram_sender.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'telegram_sender'`

- [ ] **Step 3: Write `telegram_sender.py`**

```python
# telegram_sender.py
import os

import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = TELEGRAM_API_URL.format(token=token)
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    resp.raise_for_status()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_telegram_sender.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/telegram_sender.py telegram-bot/daily-snapshot/tests/test_telegram_sender.py
git commit -m "feat(daily-snapshot): Telegram sender module"
```

---

## Task 8: Orchestrator (`main.py`), Railway deployment config, and dry-run verification

**Files:**
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/main.py`
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/Procfile`
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/railway.json`
- Create: `projects/macro-watch/telegram-bot/daily-snapshot/README.md`
- Test: `projects/macro-watch/telegram-bot/daily-snapshot/tests/test_main.py`

**Interfaces:**
- Consumes: everything produced by Tasks 1–7 (`config.TRACKED_LEVELS`, `config.DAILY_LOGS_ARCHIVE_ID`, `prices.fetch_all_prices`, `levels.compare_to_triggers`, `on_deck.on_deck_channels`, `notion_reader.fetch_recent_archive_entries`, `notion_reader.count_flagged`, `regime.regime_tag`, `message_composer.compose_message`, `telegram_sender.send_message`)
- Produces: `main.build_snapshot(run_date: datetime.date) -> str`, a `main()` CLI entrypoint with a `--dry-run` flag

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main.py
import sys
import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import main


def test_build_snapshot_orchestrates_all_modules():
    run_date = datetime.date(2026, 8, 17)

    with patch("main.prices_mod.fetch_all_prices", return_value={"US10Y": 4.7, "BTC": 63500}) as mock_prices, \
         patch("main.levels_mod.compare_to_triggers", return_value=[{"status": "ok"}]) as mock_levels, \
         patch("main.NotionClient") as mock_notion_cls, \
         patch("main.notion_reader.fetch_recent_archive_entries", return_value=[{"date": "2026-08-16", "title": "t", "text": "x"}]) as mock_entries, \
         patch("main.notion_reader.count_flagged", return_value=2) as mock_flagged, \
         patch("main.regime_mod.regime_tag", return_value="Tight money") as mock_regime, \
         patch("main.on_deck.on_deck_channels", return_value=["Krown"]) as mock_on_deck, \
         patch("main.message_composer.compose_message", return_value="the final message") as mock_compose, \
         patch.dict("os.environ", {"NOTION_API_KEY": "fake-key"}):
        result = main.build_snapshot(run_date)

    assert result == "the final message"
    mock_prices.assert_called_once()
    mock_levels.assert_called_once()
    mock_entries.assert_called_once()
    mock_flagged.assert_called_once()
    mock_regime.assert_called_once_with(4.7)
    mock_on_deck.assert_called_once_with(run_date)
    mock_compose.assert_called_once()


def test_build_snapshot_survives_missing_10y():
    run_date = datetime.date(2026, 8, 17)

    with patch("main.prices_mod.fetch_all_prices", return_value={"US10Y": None}), \
         patch("main.levels_mod.compare_to_triggers", return_value=[]), \
         patch("main.NotionClient"), \
         patch("main.notion_reader.fetch_recent_archive_entries", return_value=[]), \
         patch("main.notion_reader.count_flagged", return_value=0), \
         patch("main.regime_mod.regime_tag", return_value="Regime unavailable (10Y fetch failed)"), \
         patch("main.on_deck.on_deck_channels", return_value=[]), \
         patch("main.message_composer.compose_message", return_value="message with gaps marked") as mock_compose, \
         patch.dict("os.environ", {"NOTION_API_KEY": "fake-key"}):
        result = main.build_snapshot(run_date)

    assert result == "message with gaps marked"
    mock_compose.assert_called_once()


def test_dry_run_prints_instead_of_sending(capsys):
    with patch("main.build_snapshot", return_value="printed message"), \
         patch("main.telegram_sender.send_message") as mock_send, \
         patch("sys.argv", ["main.py", "--dry-run"]):
        main.main()

    captured = capsys.readouterr()
    assert "printed message" in captured.out
    mock_send.assert_not_called()


def test_normal_run_sends_message():
    with patch("main.build_snapshot", return_value="sent message"), \
         patch("main.telegram_sender.send_message") as mock_send, \
         patch("sys.argv", ["main.py"]):
        main.main()

    mock_send.assert_called_once_with("sent message")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write `main.py`**

```python
# main.py
import argparse
import datetime
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from notion_client import Client as NotionClient

import config
import prices as prices_mod
import levels as levels_mod
import notion_reader
import regime as regime_mod
import on_deck
import message_composer
import telegram_sender


def build_snapshot(run_date: datetime.date) -> str:
    live_prices = prices_mod.fetch_all_prices()
    compared_levels = levels_mod.compare_to_triggers(live_prices, config.TRACKED_LEVELS)

    notion_client = NotionClient(auth=os.environ["NOTION_API_KEY"])
    since = run_date - datetime.timedelta(days=1)
    entries = notion_reader.fetch_recent_archive_entries(notion_client, config.DAILY_LOGS_ARCHIVE_ID, since)
    flagged_count = notion_reader.count_flagged(entries)

    tag = regime_mod.regime_tag(live_prices.get("US10Y"))
    channels = on_deck.on_deck_channels(run_date)

    data = {
        "date": run_date.isoformat(),
        "regime": tag,
        "levels": compared_levels,
        "reference_levels": {"US2Y": live_prices.get("US2Y"), "DXY": live_prices.get("DXY")},
        "on_deck": channels,
        "digest_entries": entries,
        "flagged_count": flagged_count,
    }
    return message_composer.compose_message(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Elena's daily macro snapshot to Telegram.")
    parser.add_argument("--dry-run", action="store_true", help="Print the message instead of sending it")
    args = parser.parse_args()

    run_date = datetime.date.today()
    message = build_snapshot(run_date)

    if args.dry_run:
        print(message)
    else:
        telegram_sender.send_message(message)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest tests/test_main.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd projects/macro-watch/telegram-bot/daily-snapshot && python -m pytest -v`
Expected: PASS (all tests across all modules, ~28 total)

- [ ] **Step 6: Write the Railway deployment files**

`projects/macro-watch/telegram-bot/daily-snapshot/Procfile`:
```
worker: python main.py
```

`projects/macro-watch/telegram-bot/daily-snapshot/railway.json`:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python main.py",
    "cronSchedule": "0 6 * * *",
    "restartPolicyType": "NEVER"
  }
}
```

(`0 6 * * *` = 06:00 UTC = 07:00 CET in winter / 08:00 CEST in summer. This drifts by an hour across the DST change, same known limitation as the youtube-intake scout's cron — revisit only if the hour drift actually bothers Elena.)

- [ ] **Step 7: Write the setup README**

`projects/macro-watch/telegram-bot/daily-snapshot/README.md`:
```markdown
# Daily Snapshot Telegram Bot

Sends Elena one daily Telegram message: live prices vs. tracked trigger levels,
what's expected from tracked YouTube channels today, what came in over the last
day, and how many items are still flagged for manual thesis review. Never listens
for replies — see the design spec for why this is a separate bot from the
reactive link-submission/Q&A bot.

Design: `../../docs/superpowers/specs/2026-08-17-daily-snapshot-telegram-bot-design.md`

## One-time setup

1. **Create the Telegram bot.** In Telegram, message **@BotFather**, send `/newbot`,
   follow the prompts. Copy the token it gives you.
2. **Get your chat ID.** Send your new bot any message (e.g. "hi"), then visit
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser — your chat ID
   is the `chat.id` field in the response.
3. Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `ANTHROPIC_API_KEY`, `NOTION_API_KEY`.
4. `pip install -r requirements.txt`

## Local testing

Dry run (prints instead of sending):
```
python main.py --dry-run
```

Real send, to confirm formatting renders correctly on mobile Telegram before scheduling:
```
python main.py
```

## Deploy

Railway service, same pattern as the other Macro Watch scouts — new service in the
existing `elp-ops/macro-watch` Railway project, pointed at this folder, env vars set
in Railway's dashboard (never commit `.env`). `railway.json` sets the daily cron.
```

- [ ] **Step 8: Run `python main.py --dry-run` locally against real data**

This step needs real credentials in `.env` (Telegram token/chat ID from Step 7's setup, plus the existing `ANTHROPIC_API_KEY` and `NOTION_API_KEY`). Confirm:
- The script completes without crashing.
- The printed message contains real current prices, a real regime tag, and reflects yesterday's actual Notion archive entries.
- If any price source is down, confirm the message still prints with that item marked, not a crash.

- [ ] **Step 9: Run one real send**

Run `python main.py` (no `--dry-run`) once, confirm the message arrives in Elena's Telegram chat and is readable on mobile (no broken formatting, reasonable length).

- [ ] **Step 10: Commit**

```bash
cd projects/macro-watch
git add telegram-bot/daily-snapshot/main.py telegram-bot/daily-snapshot/tests/test_main.py \
  telegram-bot/daily-snapshot/Procfile telegram-bot/daily-snapshot/railway.json \
  telegram-bot/daily-snapshot/README.md
git commit -m "feat(daily-snapshot): orchestrator, Railway config, setup docs

New scout component goes live — milestone push per project push-cadence rule."
git push
```

(This is the actual "new pipeline component goes live" milestone per `projects/macro-watch/CLAUDE.md` — push here, not just commit, and this is the point to squash/push everything accumulated from Tasks 1–7 too if it wasn't already pushed incrementally.)
