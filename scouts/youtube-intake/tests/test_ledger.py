import sys
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import ledger
from rss import VideoEntry


def _query_response(rows, has_more=False, next_cursor=None):
    return {"results": rows, "has_more": has_more, "next_cursor": next_cursor}


def _ledger_row(video_id: str, url: str = "https://notion.so/page1") -> dict:
    return {
        "properties": {
            "Video ID": {"title": [{"plain_text": video_id}]},
            "Page URL": {"url": url},
        }
    }


def test_new_ledger_has_no_processed_videos():
    with patch("ledger._client") as mock_client:
        mock_client.data_sources.query.return_value = _query_response([])
        led = ledger.Ledger.load()
    assert not led.is_processed("abc123")


def test_load_reads_existing_rows_from_notion():
    with patch("ledger._client") as mock_client:
        mock_client.data_sources.query.return_value = _query_response([_ledger_row("abc123")])
        led = ledger.Ledger.load()
    assert led.is_processed("abc123")


def test_load_paginates_through_all_results():
    with patch("ledger._client") as mock_client:
        mock_client.data_sources.query.side_effect = [
            _query_response([_ledger_row("v1")], has_more=True, next_cursor="cursor-1"),
            _query_response([_ledger_row("v2")], has_more=False),
        ]
        led = ledger.Ledger.load()
    assert led.is_processed("v1")
    assert led.is_processed("v2")
    assert mock_client.data_sources.query.call_count == 2


def test_mark_processed_then_is_processed():
    with patch("ledger._client"):
        led = ledger.Ledger({})
        led.mark_processed("abc123", "https://notion.so/page1")
    assert led.is_processed("abc123")


def test_mark_processed_writes_a_row_to_notion():
    with patch("ledger._client") as mock_client:
        led = ledger.Ledger({})
        led.mark_processed("abc123", "https://notion.so/page1", channel="Krown", date=datetime.date(2026, 8, 5))
    assert mock_client.pages.create.called
    kwargs = mock_client.pages.create.call_args.kwargs
    assert kwargs["parent"] == {"data_source_id": ledger.config.LEDGER_DATA_SOURCE_ID}
    assert kwargs["properties"]["Channel"]["rich_text"][0]["text"]["content"] == "Krown"
    assert kwargs["properties"]["Processed Date"]["date"]["start"] == "2026-08-05"


def test_mark_processed_is_idempotent_no_duplicate_write():
    with patch("ledger._client") as mock_client:
        led = ledger.Ledger({})
        led.mark_processed("abc123", "https://notion.so/page1")
        led.mark_processed("abc123", "https://notion.so/page1")
    assert mock_client.pages.create.call_count == 1


def test_group_new_videos_by_channel_and_date():
    entries = [
        VideoEntry("v1", "Title 1", datetime.date(2026, 8, 1), "Krown"),
        VideoEntry("v2", "Title 2", datetime.date(2026, 8, 1), "Krown"),
        VideoEntry("v3", "Title 3", datetime.date(2026, 8, 2), "Krown"),
    ]
    led = ledger.Ledger({})
    groups = ledger.group_new_videos(entries, led)
    assert len(groups[("Krown", datetime.date(2026, 8, 1))]) == 2
    assert len(groups[("Krown", datetime.date(2026, 8, 2))]) == 1


def test_group_new_videos_excludes_already_processed():
    entries = [
        VideoEntry("v1", "Title 1", datetime.date(2026, 8, 1), "Krown"),
        VideoEntry("v2", "Title 2", datetime.date(2026, 8, 1), "Krown"),
    ]
    with patch("ledger._client"):
        led = ledger.Ledger({})
        led.mark_processed("v1", "https://notion.so/page1")
    groups = ledger.group_new_videos(entries, led)
    assert len(groups[("Krown", datetime.date(2026, 8, 1))]) == 1
    assert groups[("Krown", datetime.date(2026, 8, 1))][0].video_id == "v2"
