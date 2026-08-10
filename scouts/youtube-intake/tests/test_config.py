import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config

def test_only_macrovoices_active():
    assert len(config.CHANNELS) == 1
    assert config.CHANNELS[0].name == "MacroVoices"

def test_macrovoices_is_episode_format():
    mv = [c for c in config.CHANNELS if c.name == "MacroVoices"][0]
    assert mv.format == "episode"
    assert mv.channel_id == "UCICRehoZjq3ZtAWgRJX118A"

def test_krown_is_deferred_digest_format():
    krown = [c for c in config.DEFERRED_CHANNELS if c.name == "Krown"][0]
    assert krown.format == "digest"
    assert krown.channel_id == "UCnwxzpFzZNtLH8NgTeAROFA"

def test_thesis_page_ids_are_distinct():
    assert config.THESIS_PAGE_ID != config.ORIGINAL_THESIS_PAGE_ID
