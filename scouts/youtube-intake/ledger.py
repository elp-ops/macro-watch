from __future__ import annotations

import datetime
import os
from collections import defaultdict

from notion_client import Client

import config
from rss import VideoEntry

_client = Client(auth=os.getenv("NOTION_API_KEY"))


def _rich_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


class Ledger:
    """Tracks which video IDs have already been processed. Backed by a Notion database
    (not a local file) so state survives Railway redeploys, which wipe local disk."""

    def __init__(self, data: dict):
        self._data = data  # video_id -> notion_page_url

    @classmethod
    def load(cls) -> "Ledger":
        data = {}
        cursor = None
        while True:
            kwargs = {"data_source_id": config.LEDGER_DATA_SOURCE_ID}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = _client.data_sources.query(**kwargs)
            for row in resp["results"]:
                props = row["properties"]
                video_id = "".join(rt["plain_text"] for rt in props["Video ID"]["title"])
                url = props.get("Page URL", {}).get("url") or ""
                data[video_id] = url
            if resp.get("has_more"):
                cursor = resp["next_cursor"]
            else:
                break
        return cls(data)

    def is_processed(self, video_id: str) -> bool:
        return video_id in self._data

    def mark_processed(
        self, video_id: str, notion_page_url: str, channel: str = "", date: datetime.date | None = None
    ) -> None:
        """Marks processed in memory and writes a row to Notion immediately (not batched), so a
        crash mid-run still leaves already-marked videos durable for the next run."""
        if video_id in self._data:
            return
        self._data[video_id] = notion_page_url

        properties: dict = {"Video ID": {"title": _rich_text(video_id)}}
        if notion_page_url:
            properties["Page URL"] = {"url": notion_page_url}
        if channel:
            properties["Channel"] = {"rich_text": _rich_text(channel)}
        if date:
            properties["Processed Date"] = {"date": {"start": date.isoformat()}}

        _client.pages.create(
            parent={"data_source_id": config.LEDGER_DATA_SOURCE_ID},
            properties=properties,
        )


def group_new_videos(entries: list[VideoEntry], ledger: Ledger) -> dict[tuple[str, datetime.date], list[VideoEntry]]:
    groups = defaultdict(list)
    for entry in entries:
        if ledger.is_processed(entry.video_id):
            continue
        key = (entry.channel_name, entry.published)
        groups[key].append(entry)
    return dict(groups)
