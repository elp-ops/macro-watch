from collections import namedtuple

Channel = namedtuple("Channel", ["name", "handle", "channel_id", "format"])

CHANNELS = [
    Channel("MacroVoices", "@macrovoices7508", "UCICRehoZjq3ZtAWgRJX118A", "episode"),
    Channel("Krown", "@ECKrown", "UCnwxzpFzZNtLH8NgTeAROFA", "digest"),
    Channel("Dirk", "@intelligentcryptocurrency", "UCRF2-5W_uwflhpj6Hf6r4Jw", "digest"),  # channel is "IntelligentCryptocurrency", run by Dirk (Crypto Diggy) - Elena wants him referred to by name, not channel name (10 Aug 2026)
    Channel("IvanOnTech", "@IvanOnTech", "UCrYmtJBtLdtm2ov84ulV-yg", "digest"),
]

NOTION_SOURCES_DATA_SOURCE_ID = "263b6dcd-f245-4082-8c7d-11b9ee0f9f58"
LEDGER_DATA_SOURCE_ID = "ff513c31-a884-42dd-9ecb-f3ab2fe6cb2d"  # "YouTube Scout Ledger" database, under Finance Hub
THESIS_PAGE_ID = "3b1490cf-c56c-8015-9648-f388049211d1"
ORIGINAL_THESIS_PAGE_ID = "2ec490cf-c56c-80f7-a4d7-caafc4466a93"
DAILY_LOGS_ARCHIVE_ID = "3b8490cf-c56c-83f0-a521-81c81778d9bd"

RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
