# Macro Watch

Automated macro research system for tracking market and geopolitical signals against a long-term investment thesis.

## Problem

Tracking macro conditions (rates, oil, commodities, AI, crypto, geopolitics) across podcasts, filings, and structured data means manually cross-referencing new information against everything already known. That doesn't scale.

## Approach

Independent components, each watching one data source or handling one job, feeding a shared thesis:

1. Each source (YouTube, CFTC, FRED, SEC EDGAR, Congress) is monitored or queried, producing a signal
2. New signals are logged and drafted into a synthesis against the current thesis (confirms, contradicts, or introduces something new)
3. A human review step gates anything before it's merged into the thesis
4. A consensus layer (once multiple sources are live) flags when independent signals align
5. A Telegram bot exposes the whole thing conversationally: submit a source link, or ask what's happening this week

The thesis is never reset. Every new input is checked against what's already there.

## Roadmap

| Component | Status |
|---|---|
| [YouTube intake](scouts/youtube-intake/) | **Live** — deployed to Railway, daily cron 10:00 UTC, 4 channels including MacroVoices |
| [Telegram bot (intake + Q&A)](telegram-bot/) | Designed, on hold until the YouTube scout is proven out |
| [CFTC Commitment of Traders scout](scouts/cftc-cot/) | Planned |
| [FRED macro data scout](scouts/fred-macro-data/) | Planned |
| [Insider + institutional flow scout](scouts/sec-edgar-flow/) | Planned |
| [Congressional trading scout](scouts/congressional-trading/) | Planned |
| [Consensus layer](scouts/consensus-layer/) | Planned |

## Stack

Python, Claude (synthesis + Q&A), Notion (thesis storage), Telegram Bot API, Railway (bot hosting). Per-component data sources documented in each component's README.

## Status

YouTube intake is built and live (05 Aug 2026), checking new sources against the full rolling thesis on every run. Telegram bot has a full design spec, see [`docs/superpowers/specs/`](docs/superpowers/specs/), but is on hold. CFTC CoT scout is next in build order.
