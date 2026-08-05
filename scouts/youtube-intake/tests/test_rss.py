import sys
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import rss
import config

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

def _feed_with_two_entries(old_date: str, recent_date: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>oldvideo0001</yt:videoId>
    <title>Old Video</title>
    <published>{old_date}T12:00:00+00:00</published>
  </entry>
  <entry>
    <yt:videoId>newvideo0001</yt:videoId>
    <title>Recent Video</title>
    <published>{recent_date}T12:00:00+00:00</published>
  </entry>
</feed>"""

def test_fetch_recent_videos_excludes_entries_older_than_cutoff():
    today = datetime.date.today()
    old_date = (today - datetime.timedelta(days=rss.MAX_VIDEO_AGE_DAYS + 5)).isoformat()
    recent_date = (today - datetime.timedelta(days=1)).isoformat()
    channel = config.CHANNELS[0]

    fake_response = MagicMock()
    fake_response.text = _feed_with_two_entries(old_date, recent_date)
    fake_response.raise_for_status.return_value = None

    with patch("rss.requests.get", return_value=fake_response):
        entries = rss.fetch_recent_videos(channel)

    assert len(entries) == 1
    assert entries[0].video_id == "newvideo0001"
