"""
Tests unitarios para el parser de LRC y la función determinista get_active_line.
"""

import pytest
from src.lrc_parser import parse_lrc, get_active_line, parse_timestamp_ms
from src.lyrics_models import LyricLine


def test_parse_timestamp_ms():
    # Minutos, segundos, centésimas
    assert parse_timestamp_ms("01", "23", "45") == 83450
    # Décimas (frac_str="4" -> 400ms)
    assert parse_timestamp_ms("00", "05", "4") == 5400
    # Milésimas
    assert parse_timestamp_ms("02", "10", "123") == 130123
    # Sin fracción
    assert parse_timestamp_ms("00", "15", None) == 15000


def test_parse_lrc_standard():
    lrc = """
    [ti:Test Title]
    [ar:Test Artist]
    [00:05.50] Primera línea
    [00:12.00] Segunda línea
    [00:18.250] Tercera línea con milésimas
    """
    lines = parse_lrc(lrc)
    assert len(lines) == 3
    assert lines[0].timestamp_ms == 5500
    assert lines[0].text == "Primera línea"
    assert lines[1].timestamp_ms == 12000
    assert lines[1].text == "Segunda línea"
    assert lines[2].timestamp_ms == 18250
    assert lines[2].text == "Tercera línea con milésimas"


def test_parse_lrc_multiple_timestamps_and_sorting():
    lrc = """
    [00:30.00] Línea tardía
    [00:05.00][00:15.00] Coro repetido
    """
    lines = parse_lrc(lrc)
    assert len(lines) == 3
    # Debe estar ordenado cronológicamente
    assert lines[0].timestamp_ms == 5000
    assert lines[0].text == "Coro repetido"
    assert lines[1].timestamp_ms == 15000
    assert lines[1].text == "Coro repetido"
    assert lines[2].timestamp_ms == 30000
    assert lines[2].text == "Línea tardía"


def test_parse_lrc_with_offset():
    lrc = """
    [offset:+500]
    [00:10.00] Línea desplazada
    """
    lines = parse_lrc(lrc)
    assert len(lines) == 1
    assert lines[0].timestamp_ms == 10500


def test_get_active_line_deterministic():
    lines = [
        LyricLine(timestamp_ms=10000, text="Intro termina, verso 1"),
        LyricLine(timestamp_ms=20000, text="Verso 2"),
        LyricLine(timestamp_ms=30000, text="Coro final"),
    ]

    # 1. Antes del primer verso (Intro)
    res_intro = get_active_line(5000, lines)
    assert res_intro.index == -1
    assert res_intro.is_intro is True
    assert res_intro.line is None
    assert res_intro.next_line.text == "Intro termina, verso 1"

    # 2. Exactamente en el primer timestamp
    res_exact = get_active_line(10000, lines)
    assert res_exact.index == 0
    assert res_exact.line.text == "Intro termina, verso 1"
    assert res_exact.is_intro is False

    # 3. Entre el primer y segundo timestamp
    res_mid = get_active_line(15000, lines)
    assert res_mid.index == 0
    assert res_mid.line.text == "Intro termina, verso 1"
    assert res_mid.next_line.text == "Verso 2"

    # 4. Exactamente en el segundo timestamp
    res_v2 = get_active_line(20000, lines)
    assert res_v2.index == 1
    assert res_v2.line.text == "Verso 2"

    # 5. Después del último timestamp (Outro)
    res_outro = get_active_line(45000, lines)
    assert res_outro.index == 2
    assert res_outro.line.text == "Coro final"
    assert res_outro.is_outro is True
    assert res_outro.next_line is None


def test_get_active_line_empty():
    res = get_active_line(1000, [])
    assert res.index == -1
    assert res.line is None
    assert res.is_intro is True
