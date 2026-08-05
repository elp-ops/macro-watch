# scouts/youtube-intake/tests/test_thesis_updater.py
import sys
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import thesis_updater

def _fake_anthropic_response(text: str, lead_with_thinking_block: bool = False):
    fake_text_block = MagicMock()
    fake_text_block.type = "text"
    fake_text_block.text = text
    content = [fake_text_block]
    if lead_with_thinking_block:
        fake_thinking_block = MagicMock(spec=["type", "thinking"])  # no .text attribute, like the real SDK type
        fake_thinking_block.type = "thinking"
        content = [fake_thinking_block, fake_text_block]
    fake_response = MagicMock()
    fake_response.content = content
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

def test_assess_materiality_skips_leading_thinking_block():
    # Regression test: a live run hit 'ThinkingBlock' object has no attribute 'text' because
    # content[0] isn't reliably the text block when the model returns a thinking block first.
    with patch("thesis_updater._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response(
            "MATERIAL: true\nUPDATE:\n- New Fed hike signal confirmed", lead_with_thinking_block=True
        )
        result = thesis_updater.assess_materiality(["Fed hiked rates unexpectedly"], "full thesis text")
    assert result is not None
    assert "Fed hike" in result

def test_append_archive_entry_chunks_long_summary_into_multiple_blocks():
    long_summary = "x" * 5000  # exceeds the 1900-char safe margin under Notion's 2000-char rich_text cap
    with patch("thesis_updater._notion_client") as mock_client:
        thesis_updater.append_archive_entry(datetime.date(2026, 8, 5), long_summary)
    call_kwargs = mock_client.blocks.children.append.call_args.kwargs
    summary_blocks = call_kwargs["children"][0]["toggle"]["children"]
    assert len(summary_blocks) > 1
    for block in summary_blocks:
        content = block["paragraph"]["rich_text"][0]["text"]["content"]
        assert len(content) <= thesis_updater.RICH_TEXT_MAX_CHARS
    reassembled = "".join(b["paragraph"]["rich_text"][0]["text"]["content"] for b in summary_blocks)
    assert reassembled == long_summary

def test_assess_materiality_falls_back_when_update_text_unparseable():
    with patch("thesis_updater._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response("MATERIAL: true\nsomething is material but no marker line follows")
        result = thesis_updater.assess_materiality(["something happened"], "full thesis text")
    assert result is not None
    assert "something is material" in result

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

def test_fetch_page_plain_text_extracts_table_row_cells():
    with patch("thesis_updater._notion_client") as mock_client:
        page = {
            "results": [
                {
                    "id": "row1", "type": "table_row",
                    "table_row": {
                        "cells": [
                            [{"plain_text": "10Y danger band"}],
                            [{"plain_text": "4.6"}, {"plain_text": "-4.8%"}],
                        ]
                    },
                    "has_children": False,
                },
            ],
            "has_more": False,
            "next_cursor": None,
        }
        mock_client.blocks.children.list.return_value = page
        text = thesis_updater.fetch_page_plain_text("page-with-table")

    assert "10Y danger band" in text
    assert "4.6-4.8%" in text
    assert " | " in text
