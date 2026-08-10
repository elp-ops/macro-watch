# CFTC Commitment of Traders Scout

**Status:** Planned. One manual seed entry logged 11 Aug 2026 (see below) to confirm the data source and output format before building the automated version.

Tracks weekly CFTC Commitment of Traders data: positioning from commercial hedgers (producers, manufacturers, currency managers) across oil, gold, copper, bonds, indices, and currencies. Commercial positioning tends to be a strong signal at turning points.

**Source:** CFTC.gov public Socrata API (`publicreporting.cftc.gov`), free, no key needed, published weekly (Fridays). Two datasets used:
- Legacy Futures-Only (`6dca-aqww`) — financial futures (S&P 500, USD Index, Treasury notes). "Commercial" here is a looser bank/dealer hedging category, not pure directional hedgers.
- Disaggregated Futures-Only (`72hh-3qpy`) — physical commodities (WTI crude, gold). "Producer/Merchant" category = genuine commercial hedgers, the classic CoT signal.

**Output destination:** Same Notion database as the YouTube/MacroVoices transcripts — "MACRO Market Research – Sources" (data source ID `263b6dcd-f245-4082-8c7d-11b9ee0f9f58`), one page per report week, sub-page with the raw data table. Decided 11 Aug 2026: one place for everything feeding the thesis, don't build a separate table.

**Watchlist (5 assets), contract names confirmed against the live API:**
- WTI-Physical Crude Oil — NYMEX (Disaggregated)
- Gold — COMEX (Legacy)
- E-mini S&P 500 — CME (Legacy)
- USD Index — ICE US (Legacy)
- UST 10Y Note — CBOT (Legacy)

**Seed entry:** [Report Week 31, 2026 (data as of 04 Aug, published 07 Aug)](https://app.notion.com/p/3b8490cfc56c8128ba91c5cb073c719c?pvs=204) — pulled manually via `curl` against the Socrata API, not yet automated.

**Next step:** build `fetch.py` + `notion_writer.py` mirroring `scouts/youtube-intake/`, deploy to Railway on a Saturday cron.
