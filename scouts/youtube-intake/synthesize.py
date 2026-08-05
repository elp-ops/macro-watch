import os
import re
from collections import namedtuple

import anthropic

MODEL = "claude-sonnet-5"

VideoClassification = namedtuple("VideoClassification", ["video_id", "has_real_content", "reason"])

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def extract_text(response) -> str:
    """Anthropic responses can lead with a thinking block before the text block
    (e.g. extended thinking). content[0] is not reliably the text block, so scan for it."""
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError("No text block found in Anthropic response")

CLASSIFY_PROMPT = """You are screening a YouTube video transcript for inclusion in a macro/crypto investment thesis tracker.

Title: {title}
Transcript (may be truncated): {transcript}

Is there real, substantive market/trading/macro analysis here (specific claims, price levels, indicators, macro data, trade ideas)? Or is this primarily a promo/pitch for a paid course, bot, signal service, or Patreon with little to no actual analysis?

Respond in exactly this format:
REAL_CONTENT: true|false
REASON: <one sentence>"""

DIGEST_PROMPT = """You are writing a daily digest entry for {channel} covering {date}, for Elena's rolling macro/crypto investment thesis.

Below are transcripts of {count} video(s) from this channel on this day, already filtered to exclude pure promotional content.

{videos_block}

Write a Notion page body in this exact structure (markdown):

## AI Summary
[2-4 sentence overview of what this day's content covers]

## Key Claims
- [bulleted concrete claims: price levels, indicators, timeframes, reasoning - one bullet per video or per distinct claim]

## Bond/Fed relevance
[Any mention of Federal Reserve, interest rates, bond yields (10Y/2Y/30Y), inflation, or the dollar (DXY) - quote or closely paraphrase. If none, say "No bond/Fed/yield content."]

## Risks / Contradictions
[Caveats, low-confidence framing, internal contradictions]

## Filtered out
{filtered_out_block}

Do not invent claims not present in the transcripts. If a number or fact is unclear, say so rather than guessing."""

EPISODE_PROMPT = """You are writing a Notion page summary for a MacroVoices podcast episode, for Elena's rolling macro investment thesis.

Title: {title}
Speaker(s): {speaker}
Transcript: {transcript}

Write the page body in this exact structure (markdown), matching the depth and style of a professional research summary:

Macro scoreboard (week-over-week, gray-colored bullets, use <span color="gray">...</span> for each line)
Key near-term macro catalysts they flag
## What this episode is really about (plain English)
[2-3 sentences]
## [Speaker]'s core thesis
[Numbered points, each with sub-bullets, going deep on the actual argument and reasoning - not just a topic list]
## Bond / Fed / yield signals
[Dedicated section - any Fed/rates/yields/inflation/dollar content, prominent and precise. If none, say so explicitly.]
## Bottom line
[1-2 sentences]
## Soundbites / mental models worth keeping
[A few direct quotes or memorable framings]
## Open questions to carry into the rolling thesis
[Bulleted]

Do not invent claims, numbers, or analysis not present in the transcript. If a number is garbled or unclear in the transcript, flag the uncertainty rather than guessing a clean value."""


def classify_video(title: str, transcript_text: str) -> VideoClassification:
    prompt = CLASSIFY_PROMPT.format(title=title, transcript=transcript_text[:4000])
    response = _client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = extract_text(response)
    real_content = re.search(r"REAL_CONTENT:\s*(true|false)", text, re.IGNORECASE)
    reason = re.search(r"REASON:\s*(.+)", text)
    return VideoClassification(
        video_id="",
        has_real_content=(real_content.group(1).lower() == "true") if real_content else False,
        reason=reason.group(1).strip() if reason else "",
    )


def write_digest_summary(channel_name: str, date, videos: list[dict], filtered_out: list[dict] = None) -> str:
    videos_block = "\n\n".join(
        f"### Video: {v['title']}\n{v['transcript'][:8000]}" for v in videos
    )
    if filtered_out:
        filtered_out_block = "\n".join(f"- {v['title']}: {v['reason']}" for v in filtered_out)
    else:
        filtered_out_block = "Nothing filtered out today."
    prompt = DIGEST_PROMPT.format(
        channel=channel_name, date=date.isoformat(), count=len(videos), videos_block=videos_block,
        filtered_out_block=filtered_out_block,
    )
    response = _client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_text(response)


def write_episode_summary(title: str, speaker: str, transcript_text: str) -> str:
    prompt = EPISODE_PROMPT.format(title=title, speaker=speaker, transcript=transcript_text[:100000])
    response = _client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_text(response)
