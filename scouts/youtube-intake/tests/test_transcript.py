import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import transcript

def test_get_transcript_uses_captions_when_available():
    fake_snippet = MagicMock()
    fake_snippet.text = "hello world"
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.return_value = [fake_snippet]
        result = transcript.get_transcript("abc123")
    assert result.source == "captions"
    assert result.text == "hello world"
    assert result.video_id == "abc123"

def test_get_transcript_falls_back_to_transcript_io_on_captions_failure():
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_transcript_io", return_value="transcript.io text") as mock_tio:
            result = transcript.get_transcript("abc123")
    assert result.source == "transcript.io"
    assert result.text == "transcript.io text"
    mock_tio.assert_called_once_with("abc123")

def test_get_transcript_falls_back_to_gemini_when_transcript_io_has_no_text():
    """Covers livestreams: call_transcript_io returns None (isLive or no text), not an exception."""
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_transcript_io", return_value=None):
            with patch("transcript.call_gemini_transcript", return_value="gemini transcript text") as mock_gemini:
                result = transcript.get_transcript("abc123")
    assert result.source == "gemini"
    assert result.text == "gemini transcript text"
    mock_gemini.assert_called_once_with("abc123")

def test_get_transcript_falls_back_to_gemini_on_transcript_io_error():
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_transcript_io", side_effect=Exception("API error")):
            with patch("transcript.call_gemini_transcript", return_value="gemini transcript text") as mock_gemini:
                result = transcript.get_transcript("abc123")
    assert result.source == "gemini"
    mock_gemini.assert_called_once_with("abc123")

def test_get_transcript_returns_failed_when_all_three_fail():
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_transcript_io", return_value=None):
            with patch("transcript.call_gemini_transcript", side_effect=Exception("Gemini error")):
                result = transcript.get_transcript("abc123")
    assert result.source == "failed"
    assert result.text is None

def test_call_transcript_io_returns_none_for_livestream():
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "abc123", "text": "some text", "isLive": True}]
    with patch("transcript.requests.post", return_value=mock_response):
        with patch("transcript._load_env_key", return_value="fake-token"):
            result = transcript.call_transcript_io("abc123")
    assert result is None

def test_call_transcript_io_returns_text_for_normal_video():
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "abc123", "text": "real transcript", "isLive": False}]
    with patch("transcript.requests.post", return_value=mock_response):
        with patch("transcript._load_env_key", return_value="fake-token"):
            result = transcript.call_transcript_io("abc123")
    assert result == "real transcript"
