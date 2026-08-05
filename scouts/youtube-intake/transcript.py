from __future__ import annotations

import logging
import os
from collections import namedtuple
from pathlib import Path

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

TranscriptResult = namedtuple("TranscriptResult", ["video_id", "text", "source"])

GEMINI_MODEL = "gemini-2.5-flash"
TRANSCRIPT_IO_URL = "https://www.youtube-transcript.io/api/transcripts"

GEMINI_TRANSCRIPT_PROMPT = (
    "Transcribe the spoken audio of this video as accurately as possible. "
    "Return only the transcript text, no commentary, no timestamps."
)


def _load_env_key(name: str) -> str:
    key = os.getenv(name)
    if key:
        return key
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{name} not found in environment or .env")


def _load_gemini_api_key() -> str:
    return _load_env_key("GEMINI_API_KEY")


def call_transcript_io(video_id: str) -> str | None:
    """Fetch a transcript via youtube-transcript.io. Returns None for livestreams
    (no real transcript exists) or any video the API has no text for."""
    token = _load_env_key("YOUTUBE_TRANSCRIPT_IO_API_KEY")
    resp = requests.post(
        TRANSCRIPT_IO_URL,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        json={"ids": [video_id]},
        timeout=60,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    entry = results[0]
    if entry.get("isLive"):
        return None
    text = entry.get("text")
    return text or None


def call_gemini_transcript(video_id: str) -> str:
    client = genai.Client(api_key=_load_gemini_api_key())
    url = f"https://www.youtube.com/watch?v={video_id}"
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=types.Content(
            parts=[
                types.Part(file_data=types.FileData(file_uri=url)),
                types.Part(text=GEMINI_TRANSCRIPT_PROMPT),
            ]
        ),
    )
    return response.text


def get_transcript(video_id: str) -> TranscriptResult:
    try:
        api = YouTubeTranscriptApi()
        snippets = api.fetch(video_id)
        text = " ".join(s.text for s in snippets)
        return TranscriptResult(video_id, text, "captions")
    except Exception as e:
        logging.warning(f"Captions failed for video_id={video_id}, trying youtube-transcript.io: {e}")

    try:
        text = call_transcript_io(video_id)
        if text:
            return TranscriptResult(video_id, text, "transcript.io")
        logging.warning(f"youtube-transcript.io returned no transcript for video_id={video_id} (likely a livestream), falling back to Gemini")
    except Exception as e:
        logging.warning(f"youtube-transcript.io failed for video_id={video_id}, falling back to Gemini: {e}")

    try:
        text = call_gemini_transcript(video_id)
        return TranscriptResult(video_id, text, "gemini")
    except Exception as e:
        logging.warning(f"Gemini transcript failed for video_id={video_id}: {e}")
        return TranscriptResult(video_id, None, "failed")
