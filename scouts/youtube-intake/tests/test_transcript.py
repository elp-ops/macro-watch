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

def test_get_transcript_falls_back_to_gemini_on_captions_failure():
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_gemini_transcript", return_value="gemini transcript text") as mock_gemini:
            result = transcript.get_transcript("abc123")
    assert result.source == "gemini"
    assert result.text == "gemini transcript text"
    mock_gemini.assert_called_once_with("abc123")

def test_get_transcript_returns_failed_when_both_fail():
    with patch("transcript.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.fetch.side_effect = Exception("IpBlocked")
        with patch("transcript.call_gemini_transcript", side_effect=Exception("Gemini error")):
            result = transcript.get_transcript("abc123")
    assert result.source == "failed"
    assert result.text is None
