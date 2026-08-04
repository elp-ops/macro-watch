import sys
import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import rss

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
