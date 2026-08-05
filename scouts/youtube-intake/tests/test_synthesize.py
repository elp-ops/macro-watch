import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

import synthesize

def _fake_anthropic_response(text: str, lead_with_thinking_block: bool = False):
    fake_text_block = MagicMock()
    fake_text_block.type = "text"
    fake_text_block.text = text
    content = [fake_text_block]
    if lead_with_thinking_block:
        fake_thinking_block = MagicMock(spec=["type", "thinking"])  # no .text attribute, like the real SDK type
        fake_thinking_block.type = "thinking"
        content = [fake_thinking_block, fake_text_block]
    fake_response = MagicMock()
    fake_response.content = content
    return fake_response

def test_classify_video_parses_real_content_true():
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response(
            'REAL_CONTENT: true\nREASON: discusses specific BTC price levels'
        )
        result = synthesize.classify_video("Some Title", "transcript about bitcoin price levels")
    assert result.has_real_content is True
    assert "price levels" in result.reason

def test_classify_video_parses_real_content_false():
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response(
            'REAL_CONTENT: false\nREASON: pure course promo, no market content'
        )
        result = synthesize.classify_video("Buy My Course", "sign up now for my trading bot")
    assert result.has_real_content is False

def test_write_digest_summary_includes_channel_and_date():
    import datetime
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response("## AI Summary\nTest summary content")
        result = synthesize.write_digest_summary(
            "Krown", datetime.date(2026, 8, 5), [{"title": "Test Video", "transcript": "some transcript"}]
        )
    assert "AI Summary" in result

def test_extract_text_skips_leading_thinking_block():
    # Regression test: a live run hit 'ThinkingBlock' object has no attribute 'text' because
    # content[0] isn't reliably the text block when the model returns a thinking block first.
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response(
            'REAL_CONTENT: true\nREASON: has price levels', lead_with_thinking_block=True
        )
        result = synthesize.classify_video("Some Title", "transcript")
    assert result.has_real_content is True

def test_extract_text_raises_if_no_text_block_present():
    fake_thinking_block = MagicMock(spec=["type", "thinking"])
    fake_thinking_block.type = "thinking"
    fake_response = MagicMock()
    fake_response.content = [fake_thinking_block]
    import pytest
    with pytest.raises(ValueError):
        synthesize.extract_text(fake_response)
