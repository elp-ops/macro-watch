# Macro Watch

Automated macro research agent for tracking market and geopolitical signals against a long-term investment thesis.

## Problem

Tracking macro conditions (rates, oil, commodities, AI, crypto, geopolitics) across podcasts, articles, and research means manually cross-referencing new information against everything already known. That doesn't scale.

## Approach

An agent pipeline that:

1. Takes a trigger (scheduled or manual) with a topic or asset to research
2. Searches for current news and analysis (Tavily API)
3. Synthesises findings against a persistent, rolling thesis
4. Flags confirmations, contradictions, and shifts explicitly
5. Outputs a structured summary

The thesis is never reset. Every new input is checked against what's already there.

## Stack (planned)

Python, Tavily API (search), Anthropic Claude (synthesis), Notion (thesis storage).

## Status

Early stage. Core research loop not yet built. This repo tracks development as it happens.
