import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from rss import VideoEntry


class Ledger:
    def __init__(self, data: dict):
        self._data = data  # video_id -> notion_page_url

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        if path.exists():
            return cls(json.loads(path.read_text()))
        return cls({})

    def is_processed(self, video_id: str) -> bool:
        return video_id in self._data

    def mark_processed(self, video_id: str, notion_page_url: str) -> None:
        self._data[video_id] = notion_page_url

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._data, indent=2, sort_keys=True))


def group_new_videos(entries: list[VideoEntry], ledger: Ledger) -> dict[tuple[str, date], list[VideoEntry]]:
    groups = defaultdict(list)
    for entry in entries:
        if ledger.is_processed(entry.video_id):
            continue
        key = (entry.channel_name, entry.published)
        groups[key].append(entry)
    return dict(groups)
