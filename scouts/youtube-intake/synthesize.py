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
    if response.stop_reason == "max_tokens":
        # Fixed 10 Aug 2026: a raised max_tokens budget can still get hit on a verbose run
        # (happened even at 8000). Previously this silently returned the partial text and it got
        # written to Notion incomplete (see MV544 Viktor Shvets incident). Fail loudly instead so
        # the existing per-video error handling in run_daily.py catches it, logs it, and retries
        # next run rather than shipping broken content.
        raise ValueError("Response was cut off by the max_tokens limit; summary is incomplete")
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
[2-4 SHORT sentences, written like you're explaining it to a smart friend with zero finance
background, not a research analyst. No jargon left undefined ("K-shaped economy," "rolling
bubble," etc. must be explained in plain words in the same sentence, not just named). Say
concretely what happened and why it matters, not which school of thought it represents.]

## Key Claims
- [bulleted concrete claims: price levels, indicators, timeframes, reasoning - one bullet per video or per distinct claim]

## Bond/Fed relevance
[Any mention of Federal Reserve, interest rates, bond yields (10Y/2Y/30Y), inflation, or the dollar (DXY) - quote or closely paraphrase. If none, say "No bond/Fed/yield content."]

## Contradictions
[Only genuine self-contradictions: the speaker says one thing then contradicts it later in the
same video. These are sources Elena has already vetted and trusts - do not hedge on credibility,
question whether a claim is verified, or flag missing data/citations as a caveat. Report what they
said as fact. If there are no self-contradictions, say "None."]

## Filtered out
{filtered_out_block}

Do not invent claims not present in the transcripts. If a number or fact is unclear, say so rather than guessing. Never use em dashes anywhere in the page; use commas, periods, colons, or parentheses instead."""

EPISODE_PROMPT = """You are writing a Notion page summary for a MacroVoices podcast episode, for Elena's rolling macro investment thesis.

Title: {title}
Speaker(s): {speaker}
Transcript: {transcript}

Write the page body in this exact structure (markdown), matching the depth and style of a professional research summary:

Macro scoreboard (week-over-week, gray-colored bullets, use <span color="gray">...</span> for each line)
Key near-term macro catalysts they flag
## What this episode is really about (plain English)
[2-3 SHORT sentences, written like you're explaining it to a smart friend with zero finance
background, not a research analyst. No jargon left undefined: a term like "K-shaped economy" or
"rolling bubble" must be explained in plain words in the same sentence it's used, not just named.
Concrete, not conceptual: say what's actually happening and why it matters, not what abstract
framework or school of thought it represents. If a plain-language analogy exists, use it.]
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

Do not invent claims, numbers, or analysis not present in the transcript. If a number is garbled or unclear in the transcript, flag the uncertainty rather than guessing a clean value. Never use em dashes anywhere in the page; use commas, periods, colons, or parentheses instead."""


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
        max_tokens=8000,  # raised 10 Aug 2026: 4000 was cutting off digest writes (IntelligentCryptocurrency
        # hit this repeatedly). Same failure mode already fixed for episode summaries, see write_episode_summary.
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_text(response)


def write_episode_summary(title: str, speaker: str, transcript_text: str) -> str:
    # max_tokens history: 4000 -> 8000 -> 16000 on 10 Aug 2026. 4000 was silently truncating dense
    # episodes mid-generation (missing Bond/Fed, Bottom line, Soundbites, Open questions). 8000
    # still wasn't enough on one run (cut off in the middle of "Open questions"). extract_text now
    # also raises loudly on any max_tokens cutoff instead of returning partial text, so this can't
    # silently recur even if 16000 also proves insufficient someday -- see MV544 Viktor Shvets incident.
    prompt = EPISODE_PROMPT.format(title=title, speaker=speaker, transcript=transcript_text[:100000])
    response = _client.messages.create(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_text(response)
