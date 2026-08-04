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

def test_create_episode_page_chunks_more_than_100_blocks():
    long_summary = "\n".join(f"Line {i}" for i in range(150))  # 150 non-empty lines -> 150 blocks
    with patch("notion_writer._client") as mock_client:
        mock_client.pages.create.return_value = {"id": "page-1", "url": "https://notion.so/page1"}
        notion_writer.create_episode_page(
            "Test Episode", "Some Speaker", datetime.date(2026, 8, 5), long_summary, "v1", "transcript text"
        )

    first_call_children = mock_client.pages.create.call_args_list[0].kwargs["children"]
    assert len(first_call_children) == 100

    append_calls = mock_client.blocks.children.append.call_args_list
    # at least one append batch carries the remaining 50 summary blocks (plus the transcript subpage's own create call)
    summary_append_batches = [c for c in append_calls if c.kwargs["block_id"] == "page-1"]
    assert len(summary_append_batches) >= 1
    total_appended = sum(len(c.kwargs["children"]) for c in summary_append_batches)
    assert total_appended == 50
