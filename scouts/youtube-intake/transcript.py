import os
from collections import namedtuple
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

TranscriptResult = namedtuple("TranscriptResult", ["video_id", "text", "source"])

GEMINI_MODEL = "gemini-2.5-flash"

GEMINI_TRANSCRIPT_PROMPT = (
    "Transcribe the spoken audio of this video as accurately as possible. "
    "Return only the transcript text, no commentary, no timestamps."
)


def _load_gemini_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("GEMINI_API_KEY not found in environment or .env")


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
    except Exception:
        pass

    try:
        text = call_gemini_transcript(video_id)
        return TranscriptResult(video_id, text, "gemini")
    except Exception:
        return TranscriptResult(video_id, None, "failed")
