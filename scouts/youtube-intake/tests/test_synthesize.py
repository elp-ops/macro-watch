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
    fake_response.stop_reason = "end_turn"
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

def test_episode_prompt_demands_plain_language_for_the_summary_section():
    # Regression test for 10 Aug 2026: Elena called the "plain English" section "abstract AI
    # slop" -- jargon like "K-shaped economy" named but never explained. The prompt itself must
    # demand plain, jargon-defined language, not just label the section "plain English".
    assert "jargon" in synthesize.EPISODE_PROMPT.lower()
    assert "smart friend" in synthesize.EPISODE_PROMPT.lower()

def test_prompts_ban_em_dashes():
    # Elena's hard rule (CLAUDE.md, communication-style.md) applies to anything she reads,
    # including automated Notion output, not just chat replies.
    assert "em dash" in synthesize.EPISODE_PROMPT.lower()
    assert "em dash" in synthesize.DIGEST_PROMPT.lower()

def test_write_episode_summary_uses_a_large_enough_token_budget():
    # Regression test for the 10 Aug 2026 bug: max_tokens=4000, then 8000, both silently truncated
    # dense episode summaries mid-section (missing Bond/Fed, Bottom line, Soundbites, Open questions).
    with patch("synthesize._client") as mock_client:
        mock_client.messages.create.return_value = _fake_anthropic_response("## Bottom line\nfull summary")
        synthesize.write_episode_summary("Test Episode", "Speaker", "transcript text")
    assert mock_client.messages.create.call_args.kwargs["max_tokens"] >= 16000

def test_extract_text_raises_loudly_when_truncated_by_max_tokens():
    # Regression test for 10 Aug 2026: a raised max_tokens budget (8000) still got hit on one live
    # run and the partial text was silently returned and written to Notion incomplete. Must fail
    # loudly instead so run_daily.py's existing per-video error handling catches and retries it.
    fake_response = _fake_anthropic_response("partial text that got cut off mid")
    fake_response.stop_reason = "max_tokens"
    import pytest
    with pytest.raises(ValueError, match="cut off"):
        synthesize.extract_text(fake_response)

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
