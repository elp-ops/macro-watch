# scouts/youtube-intake/thesis_updater.py
from __future__ import annotations

import datetime
import logging
import os
import re

import anthropic
from notion_client import Client

import config
from notion_writer import guard_against_original_thesis
from synthesize import extract_text

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_notion_client = Client(auth=os.getenv("NOTION_API_KEY"))

MODEL = "claude-sonnet-5"

RICH_TEXT_MAX_CHARS = 1900  # safe margin under Notion's 2000-char rich_text content cap

MATERIALITY_PROMPT = """You maintain Elena's rolling macro/crypto investment thesis. Below is the FULL current
thesis page (Today/This Week Snapshot, Operating Thesis, Key Levels, and Decision Tree sections), followed by
summaries of new content logged today.

Current thesis (full page):
{current_thesis}

New content today:
{new_content}

Does any of this new content confirm, contradict, or add a materially new angle to ANY part of the current
thesis above, not just the Snapshot section, but also the Operating Thesis, Key Levels, or Decision Tree
(a contradiction can live in the deeper sections just as easily as the Snapshot; do not limit your check to
the Snapshot bullets)? Restating something already covered does not count. If yes, respond:
MATERIAL: true
UPDATE:
- <bulleted update points, in the same style as the existing snapshot, noting which section(s) are affected>

These sources are already vetted and trusted by Elena. Write update points as fact, the same way
the rest of the thesis is written. Do not add credibility caveats ("low credibility", "unverified",
"no figures given", "hedged language", etc.) or question whether a claim is confirmed.

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
                if block_type == "table_row":
                    cell_texts = [
                        "".join(rt.get("plain_text", "") for rt in cell)
                        for cell in data.get("cells", [])
                    ]
                    text = " | ".join(cell_texts)
                else:
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
        # max_tokens history: 1500 -> 4000 on 12 Aug 2026, 4000 -> 8000 on 28 Sep 2026 (an 11-day
        # scout outage let a large backlog build up, one run's content summaries alone exceeded 4000).
        # Same cutoff bug already fixed twice in this file for the digest/episode writers (10 Aug).
        # See extract_text() in synthesize.py for why this fails loudly instead of shipping a partial verdict.
        model=MODEL, max_tokens=8000, messages=[{"role": "user", "content": prompt}]
    )
    text = extract_text(response)
    if re.search(r"MATERIAL:\s*true", text, re.IGNORECASE):
        update_match = re.search(r"UPDATE:\s*(.+)", text, re.DOTALL)
        if update_match:
            return update_match.group(1).strip()
        logging.warning(
            "assess_materiality: MATERIAL: true but UPDATE: could not be parsed. Raw response: %s", text
        )
        return f"(materiality flagged but UPDATE text could not be cleanly parsed) {text[:500]}"
    return None


def _chunk_text(text: str, max_chars: int) -> list[str]:
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or [""]


def append_archive_entry(date: datetime.date, run_summary: str) -> None:
    guard_against_original_thesis(config.DAILY_LOGS_ARCHIVE_ID)  # no-op here, but keeps the guard pattern consistent
    date_str = date.isoformat()
    summary_blocks = [
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
        }
        for chunk in _chunk_text(run_summary, RICH_TEXT_MAX_CHARS)
    ]
    _notion_client.blocks.children.append(
        block_id=config.DAILY_LOGS_ARCHIVE_ID,
        children=[{
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": f"{date_str}: Daily scout run"}}],
                "children": summary_blocks,
            },
        }],
    )
