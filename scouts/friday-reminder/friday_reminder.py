"""Friday reminder (Elena, 17 Oct 2026): every Friday morning, tell Elena the weekly thesis
update is due and whether this week's MacroVoices episode is in Notion yet. It only reports.
It never processes, skips or decides anything on her behalf."""
from __future__ import annotations

import datetime
import os
import re
import xml.etree.ElementTree as ET

import requests
from notion_client import Client

MACROVOICES_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id=UCICRehoZjq3ZtAWgRJX118A"
SOURCES_DATA_SOURCE_ID = "263b6dcd-f245-4082-8c7d-11b9ee0f9f58"
THESIS_PAGE_ID = "3b1490cf-c56c-8015-9648-f388049211d1"
THESIS_URL = "https://app.notion.com/p/3b1490cfc56c80159648f388049211d1"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

_NS = {"atom": "http://www.w3.org/2005/Atom"}
EPISODE_RE = re.compile(r"^macrovoices\s*#(\d+)", re.IGNORECASE)


def latest_episode(xml_text: str) -> tuple[str, datetime.date] | None:
    """Newest numbered MacroVoices episode in the feed (skips Trading Desk clips)."""
    root = ET.fromstring(xml_text)
    best = None
    for entry in root.findall("atom:entry", _NS):
        title = entry.find("atom:title", _NS).text.strip()
        m = EPISODE_RE.match(title)
        if not m:
            continue
        published = datetime.datetime.fromisoformat(entry.find("atom:published", _NS).text).date()
        if best is None or int(m.group(1)) > best[0]:
            best = (int(m.group(1)), title, published)
    return (best[1], best[2]) if best else None


def episode_page_url(client: Client, title: str) -> str | None:
    number = EPISODE_RE.match(title).group(1)
    resp = client.data_sources.query(
        data_source_id=SOURCES_DATA_SOURCE_ID,
        filter={"property": "Name", "title": {"contains": f"#{number}"}},
    )
    results = resp.get("results", [])
    return results[0]["url"] if results else None


def compose_message(episode: tuple[str, datetime.date] | None, page_url: str | None,
                    thesis_edited: datetime.date) -> str:
    lines = ["Friday thesis update is due.", ""]
    if episode is None:
        lines.append("MacroVoices: couldn't read the YouTube feed. Check manually.")
    else:
        title, published = episode
        lines.append(f"MacroVoices: {title} (out {published:%a %d %b}).")
        if page_url:
            lines.append(f"In Notion: {page_url}")
        else:
            lines.append("NOT in Notion yet.")
    lines += [
        "",
        f"Thesis page last edited: {thesis_edited:%d %b}.",
        THESIS_URL,
        "",
        "Open a chat with Gina and say \"Friday update\".",
    ]
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    url = TELEGRAM_API_URL.format(token=os.environ["TELEGRAM_BOT_TOKEN"])
    resp = requests.post(url, json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Telegram sendMessage failed: {resp.status_code}")


def main() -> None:
    client = Client(auth=os.environ["NOTION_API_KEY"])
    try:
        resp = requests.get(MACROVOICES_RSS, timeout=15)
        resp.raise_for_status()
        episode = latest_episode(resp.text)
    except Exception:
        episode = None
    page_url = episode_page_url(client, episode[0]) if episode else None
    edited = client.pages.retrieve(page_id=THESIS_PAGE_ID)["last_edited_time"]
    thesis_edited = datetime.datetime.fromisoformat(edited.replace("Z", "+00:00")).date()
    send_telegram(compose_message(episode, page_url, thesis_edited))


if __name__ == "__main__":
    main()
