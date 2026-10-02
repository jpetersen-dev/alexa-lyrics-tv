"""
Tests para LRCLIBLyricsProvider, normalización de títulos y caché SQLite.
"""

import os
import tempfile
import pytest

from src.lrclib_provider import LRCLIBLyricsProvider, normalize_title
from src.lyrics_models import LyricsStatus


def test_normalize_title():
    # Remastered con guión
    assert normalize_title("Bohemian Rhapsody - Remastered 2011") == "Bohemian Rhapsody"
    # Remastered entre paréntesis
    assert normalize_title("Karma Police (Remastered)") == "Karma Police"
    # Colaboración feat.
    assert normalize_title("Save Your Tears (feat. Ariana Grande)") == "Save Your Tears"
    # Live en corchetes
    assert normalize_title("Hotel California [Live]") == "Hotel California"
    # Título simple sin cambios
    assert normalize_title("Yesterday") == "Yesterday"


def test_lrclib_real_query_and_sqlite_cache():
    # Usar base de datos temporal
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        provider = LRCLIBLyricsProvider(db_path=db_path)

        # 1. Consulta real a LRCLIB (debe devolver letra sincronizada)
        res1 = provider.get_lyrics(artist="Queen", title="Bohemian Rhapsody")
        assert res1.status == LyricsStatus.SYNCED
        assert len(res1.lines) > 20
        assert res1.is_cached is False
        assert res1.lines[0].timestamp_ms >= 0

        # 2. Segunda consulta (debe resolverse instantáneamente desde SQLite)
        res2 = provider.get_lyrics(artist="Queen", title="Bohemian Rhapsody")
        assert res2.status == LyricsStatus.SYNCED
        assert len(res2.lines) == len(res1.lines)
        assert res2.is_cached is True
        assert res2.source == "CACHE_SQLITE"

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
