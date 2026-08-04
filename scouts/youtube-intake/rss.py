import datetime
import xml.etree.ElementTree as ET
from collections import namedtuple

import requests

import config

VideoEntry = namedtuple("VideoEntry", ["video_id", "title", "published", "channel_name"])

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def parse_feed_xml(xml_text: str, channel_name: str) -> list[VideoEntry]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry_el in root.findall("atom:entry", _NS):
        video_id = entry_el.find("yt:videoId", _NS).text
        title = entry_el.find("atom:title", _NS).text
        published_raw = entry_el.find("atom:published", _NS).text
        published_date = datetime.datetime.fromisoformat(published_raw).date()
        entries.append(VideoEntry(video_id, title, published_date, channel_name))
    return entries


def fetch_recent_videos(channel: "config.Channel") -> list[VideoEntry]:
    url = config.RSS_URL_TEMPLATE.format(channel_id=channel.channel_id)
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return parse_feed_xml(response.text, channel_name=channel.name)
