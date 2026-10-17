import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import friday_reminder as fr

FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
<entry><title>Trading Desk - October 22nd 2026</title><published>2026-10-22T12:00:00+00:00</published></entry>
<entry><title>MacroVoices #555 Guest: Topic</title><published>2026-10-22T12:00:00+00:00</published></entry>
<entry><title>MacroVoices #554 Yasir Arafat: Nuclear</title><published>2026-10-15T12:00:00+00:00</published></entry>
</feed>"""


def test_latest_episode_skips_trading_desk_and_picks_highest_number():
    assert fr.latest_episode(FEED) == ("MacroVoices #555 Guest: Topic", datetime.date(2026, 10, 22))


def test_message_flags_missing_episode():
    msg = fr.compose_message(("MacroVoices #555 Guest: Topic", datetime.date(2026, 10, 22)), None, datetime.date(2026, 10, 17))
    assert "NOT in Notion yet" in msg
    assert "#555" in msg
    assert "17 Oct" in msg


def test_message_links_episode_when_present():
    msg = fr.compose_message(("MacroVoices #555 Guest: Topic", datetime.date(2026, 10, 22)), "https://notion/x", datetime.date(2026, 10, 17))
    assert "In Notion: https://notion/x" in msg
    assert "NOT in Notion" not in msg


def test_message_when_feed_unreadable():
    assert "couldn't read the YouTube feed" in fr.compose_message(None, None, datetime.date(2026, 10, 17))
