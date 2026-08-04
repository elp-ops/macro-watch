import sys
import datetime
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
