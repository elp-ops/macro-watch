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

def test_process_channel_digest_write_failure_does_not_mark_ledger_and_logs_failed_entry():
    channel = config.CHANNELS[1]  # Krown, digest format
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    fake_entry = VideoEntry("v1", "Real Signal Video", datetime.date(2026, 8, 5), "Krown")

    with patch("run_daily.rss.fetch_recent_videos", return_value=[fake_entry]), \
         patch("run_daily.transcript.get_transcript", return_value=TranscriptResult("v1", "real transcript", "captions")), \
         patch("run_daily.synthesize.classify_video", return_value=VideoClassification("v1", True, "has price levels")), \
         patch("run_daily.synthesize.write_digest_summary", return_value="## AI Summary\ntest"), \
         patch("run_daily.notion_writer.create_digest_page", side_effect=RuntimeError("Notion API 500")):
        summaries = run_daily.process_channel(channel, led)

    assert not led.is_processed("v1")
    assert len(summaries) == 1
    assert summaries[0]["content"] == ""
    assert "Krown" in summaries[0]["one_liner"]
    assert "synthesis/write FAILED" in summaries[0]["one_liner"]
    assert "Notion API 500" in summaries[0]["one_liner"]

def test_process_channel_episode_write_failure_does_not_mark_ledger_and_logs_failed_entry():
    channel = config.CHANNELS[0]  # MacroVoices, episode format
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    fake_entry = VideoEntry("v1", "Real Signal Episode", datetime.date(2026, 8, 5), "MacroVoices")

    with patch("run_daily.rss.fetch_recent_videos", return_value=[fake_entry]), \
         patch("run_daily.transcript.get_transcript", return_value=TranscriptResult("v1", "real transcript", "captions")), \
         patch("run_daily.synthesize.classify_video", return_value=VideoClassification("v1", True, "has price levels")), \
         patch("run_daily.synthesize.write_episode_summary", return_value="## AI Summary\ntest"), \
         patch("run_daily.notion_writer.create_episode_page", side_effect=RuntimeError("rate limited")):
        summaries = run_daily.process_channel(channel, led)

    assert not led.is_processed("v1")
    assert len(summaries) == 1
    assert summaries[0]["content"] == ""
    assert "synthesis/write FAILED" in summaries[0]["one_liner"]
    assert "rate limited" in summaries[0]["one_liner"]

def test_process_channel_classification_failure_does_not_lose_other_groups():
    channel = config.CHANNELS[1]  # Krown, digest format
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    entry_day1 = VideoEntry("v1", "Video Day 1", datetime.date(2026, 8, 4), "Krown")
    entry_day2 = VideoEntry("v2", "Video Day 2", datetime.date(2026, 8, 5), "Krown")

    def fake_classify(title, transcript_text):
        if title == "Video Day 1":
            raise RuntimeError("Anthropic API error")
        return VideoClassification("v2", True, "has price levels")

    with patch("run_daily.rss.fetch_recent_videos", return_value=[entry_day1, entry_day2]), \
         patch("run_daily.transcript.get_transcript", side_effect=lambda vid: TranscriptResult(vid, "real transcript", "captions")), \
         patch("run_daily.synthesize.classify_video", side_effect=fake_classify), \
         patch("run_daily.synthesize.write_digest_summary", return_value="## AI Summary\nday2"), \
         patch("run_daily.notion_writer.create_digest_page", return_value="https://notion.so/day2"):
        summaries = run_daily.process_channel(channel, led)

    assert any(s["content"] == "## AI Summary\nday2" for s in summaries)
    assert any("FAILED" in s["one_liner"] and "Anthropic API error" in s["one_liner"] for s in summaries)
    assert not led.is_processed("v1")  # day 1's classification never completed, must retry next run
    assert led.is_processed("v2")  # day 2 succeeded despite day 1's failure

def test_process_channel_passes_filtered_out_videos_to_digest_summary():
    channel = config.CHANNELS[1]  # Krown, digest format
    led = ledger.Ledger.load(Path("/nonexistent/processed.json"))
    real_entry = VideoEntry("v1", "Real Signal Video", datetime.date(2026, 8, 5), "Krown")
    promo_entry = VideoEntry("v2", "Buy My Course", datetime.date(2026, 8, 5), "Krown")

    def fake_classify(title, transcript_text):
        if title == "Buy My Course":
            return VideoClassification("v2", False, "pure course promo")
        return VideoClassification("v1", True, "has price levels")

    with patch("run_daily.rss.fetch_recent_videos", return_value=[real_entry, promo_entry]), \
         patch("run_daily.transcript.get_transcript", side_effect=lambda vid: TranscriptResult(vid, "transcript", "captions")), \
         patch("run_daily.synthesize.classify_video", side_effect=fake_classify), \
         patch("run_daily.synthesize.write_digest_summary", return_value="## AI Summary\ntest") as mock_write, \
         patch("run_daily.notion_writer.create_digest_page", return_value="https://notion.so/newpage"):
        run_daily.process_channel(channel, led)

    assert mock_write.called
    filtered_out_arg = mock_write.call_args[0][3]
    assert filtered_out_arg == [{"title": "Buy My Course", "reason": "pure course promo"}]

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

def test_main_still_archives_when_materiality_check_fails():
    fake_channel = MagicMock()
    with patch("run_daily.config.CHANNELS", [fake_channel]), \
         patch("run_daily.ledger.Ledger.load"), \
         patch("run_daily.ledger.Ledger.save"), \
         patch("run_daily.process_channel", return_value=[
             {"one_liner": "Krown digest (2026-08-05): 1 video(s) -> https://notion.so/x", "content": "some content"}
         ]), \
         patch("run_daily.thesis_updater.fetch_page_plain_text", side_effect=RuntimeError("Notion 500")), \
         patch("run_daily.thesis_updater.append_archive_entry") as mock_archive:
        run_daily.main()

    assert mock_archive.called
    archived_summary = mock_archive.call_args[0][1]
    assert "Krown digest" in archived_summary  # the successful run summary must not be lost

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
