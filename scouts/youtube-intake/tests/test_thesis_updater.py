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
