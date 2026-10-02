"""
Tests unitarios para PlaybackClock.
Verifica interpolación monotónica, congelamiento en pausa, recalibración y detección de seek.
"""

import time
import pytest
from src.playback_clock import PlaybackClock


def test_clock_interpolation_advances():
    clock = PlaybackClock()
    clock.update_observation(progress_ms=10000, is_playing=True, duration_ms=200000)

    pos_initial = clock.get_current_position_ms()
    assert 9900 <= pos_initial <= 10100

    # Simular paso de 150 ms
    time.sleep(0.15)
    pos_after = clock.get_current_position_ms()
    assert pos_after > pos_initial
    assert 10100 <= pos_after <= 10300


def test_clock_frozen_when_paused():
    clock = PlaybackClock()
    clock.update_observation(progress_ms=25000, is_playing=False, duration_ms=200000)

    pos_initial = clock.get_current_position_ms()
    assert pos_initial == 25000

    time.sleep(0.1)
    pos_after = clock.get_current_position_ms()
    assert pos_after == 25000  # Debe permanecer congelado exactamente en 25000


def test_clock_latency_compensation():
    clock = PlaybackClock()
    # Simular que recibimos progress=30000 con un retardo de red medido de 250 ms
    clock.update_observation(
        progress_ms=30000,
        is_playing=True,
        duration_ms=200000,
        network_latency_ms=250.0,
    )

    # La posición anclada debe compensar los 250 ms
    pos = clock.get_current_position_ms()
    assert 30200 <= pos <= 30350


def test_clock_seek_detection():
    clock = PlaybackClock(seek_threshold_ms=2000)
    clock.update_observation(progress_ms=10000, is_playing=True, duration_ms=200000)

    # 1. Salto pequeño normal (< 2000ms): no es seek
    is_seek = clock.update_observation(progress_ms=10500, is_playing=True, duration_ms=200000)
    assert is_seek is False

    # 2. Salto grande hacia adelante (seek a 90s): detecta seek
    is_seek_fwd = clock.update_observation(progress_ms=90000, is_playing=True, duration_ms=200000)
    assert is_seek_fwd is True
    assert 89900 <= clock.get_current_position_ms() <= 90100

    # 3. Salto hacia atrás (seek a 5s): detecta seek
    is_seek_bwd = clock.update_observation(progress_ms=5000, is_playing=True, duration_ms=200000)
    assert is_seek_bwd is True
    assert 4900 <= clock.get_current_position_ms() <= 5100
