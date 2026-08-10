from __future__ import annotations

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


NOTION_MAX_CHILDREN_PER_CALL = 100
RICH_TEXT_MAX_CHARS = 1900  # safe margin under Notion's 2000-char rich_text content cap


def _create_page_with_chunked_children(parent: dict, icon: dict, properties: dict, children: list[dict]) -> dict:
    """pages.create only accepts up to 100 children blocks per call. Create with the first batch,
    then append the rest in batches of 100 via blocks.children.append."""
    first_batch, remaining = children[:NOTION_MAX_CHILDREN_PER_CALL], children[NOTION_MAX_CHILDREN_PER_CALL:]
    page = _client.pages.create(parent=parent, icon=icon, properties=properties, children=first_batch)
    for i in range(0, len(remaining), NOTION_MAX_CHILDREN_PER_CALL):
        batch = remaining[i:i + NOTION_MAX_CHILDREN_PER_CALL]
        _client.blocks.children.append(block_id=page["id"], children=batch)
    return page


def _chunk_text_blocks(text: str) -> list[dict]:
    """Splits arbitrary-length text into paragraph blocks, each under Notion's per-block rich_text
    cap. Fixed 10 Aug 2026: this used to be a single transcript_text[:1900] slice that silently
    dropped everything past the first ~1900 characters of every transcript ever saved."""
    return [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(text[i:i + RICH_TEXT_MAX_CHARS])}}
        for i in range(0, len(text), RICH_TEXT_MAX_CHARS)
    ]


def _find_existing_page_url(title: str) -> str | None:
    """Guards against duplicate source pages. Fixed 10 Aug 2026: a run that half-failed after
    creating a page but before ledger.mark_processed() left the video unmarked, so the next run
    reprocessed it from scratch and created a second page with the same title (MV544 Viktor
    Shvets incident)."""
    resp = _client.data_sources.query(
        data_source_id=config.NOTION_SOURCES_DATA_SOURCE_ID,
        filter={"property": "Name", "title": {"equals": title}},
    )
    results = resp.get("results", [])
    return results[0]["url"] if results else None


def _create_transcript_subpage(parent_page_id: str, title: str, transcript_text: str) -> str:
    guard_against_original_thesis(parent_page_id)
    children = _chunk_text_blocks(transcript_text) if transcript_text else _markdown_to_paragraph_blocks("(empty transcript)")
    page = _create_page_with_chunked_children(
        parent={"page_id": parent_page_id},
        icon={"type": "emoji", "emoji": "\U0001F4DD"},
        properties={"title": {"title": _rich_text(title)}},
        children=children,
    )
    return page["url"]


def create_digest_page(channel_name: str, date: datetime.date, summary_markdown: str, videos: list[dict]) -> str:
    date_str = date.strftime("%d %b %Y")
    title = f"{channel_name}: Daily Digest ({date_str})"
    existing_url = _find_existing_page_url(title)
    if existing_url:
        return existing_url
    page = _create_page_with_chunked_children(
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
    existing_url = _find_existing_page_url(title)
    if existing_url:
        return existing_url
    page = _create_page_with_chunked_children(
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
