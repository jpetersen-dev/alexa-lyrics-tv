import React, { useEffect, useRef, useState } from 'react';
import type { SyncedPlaybackState } from '../types';

interface KaraokeViewProps {
  state: SyncedPlaybackState | null;
  positionMs: number;
  activeLineIndex: number;
  isConnected: boolean;
  onSeekTo?: (timestampMs: number) => void;
}

export const KaraokeView: React.FC<KaraokeViewProps> = ({
  state,
  positionMs,
  activeLineIndex,
  isConnected,
  onSeekTo,
}) => {
  const lineRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [currentTimeStr, setCurrentTimeStr] = useState<string>('');
  const [currentDateStr, setCurrentDateStr] = useState<string>('');

  // Reloj ambiental para pantalla inactiva
  useEffect(() => {
    function updateClock() {
      const now = new Date();
      setCurrentTimeStr(
        now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      );
      setCurrentDateStr(
        now.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })
      );
    }
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Desplazamiento suave centrado al cambiar la línea activa
  useEffect(() => {
    if (activeLineIndex >= 0 && lineRefs.current[activeLineIndex]) {
      lineRefs.current[activeLineIndex]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [activeLineIndex]);

  // Formato mm:ss
  const formatTime = (ms: number) => {
    const totalSec = Math.max(0, Math.floor(ms / 1000));
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  // --- MODO INACTIVO / AMBIENTAL ---
  const isIdle =
    !state ||
    state.lyrics_status === 'STOPPED' ||
    state.lyrics_status === 'IDLE' ||
    state.track === 'Sin reproducción';

  if (isIdle) {
    return (
      <div className="karaoke-ambient-container">
        <div className="ambient-glow" />
        <div className="ambient-clock-card">
          <div className="ambient-time">{currentTimeStr || '00:00'}</div>
          <div className="ambient-date">{currentDateStr}</div>
          <div className="ambient-status-badge">
            <span className={`status-dot ${isConnected ? 'online' : 'offline'}`} />
            {isConnected ? 'Alexa Lyrics TV — Esperando Reproducción' : 'Conectando con el servidor...'}
          </div>
          <p className="ambient-hint">
            Pide a Alexa reproducir una canción o usa el panel de control inferior para simular.
          </p>
        </div>
      </div>
    );
  }

  // Porcentaje de progreso
  const progressPct =
    state.duration_ms > 0
      ? Math.min(100, Math.max(0, (positionMs / state.duration_ms) * 100))
      : 0;

  return (
    <div className="karaoke-container">
      {/* Fondo con brillo dinámico suave */}
      <div className="karaoke-backdrop-glow" />

      {/* Barra de progreso superior discreta */}
      <div className="top-progress-bar">
        <div className="top-progress-fill" style={{ width: `${progressPct}%` }} />
      </div>

      {/* Cabecera de canción para TV */}
      <header className="karaoke-header">
        <div className="track-info">
          <div className="header-meta">
            <span className="live-badge">
              <span className={`pulse-indicator ${state.is_playing ? 'playing' : 'paused'}`} />
              {state.is_playing ? 'KARAOKE EN VIVO' : 'PAUSADO'}
            </span>
            {state.device_name && (
              <span className="device-tag">🔊 {state.device_name}</span>
            )}
          </div>
          <h1 className="track-title">{state.track}</h1>
          <h2 className="track-artist">
            {state.artist}
            {state.album && <span className="album-name"> • {state.album}</span>}
          </h2>
        </div>

        <div className="time-indicator">
          <span className="current-pos">{formatTime(positionMs)}</span>
          <span className="time-divider">/</span>
          <span className="total-dur">{formatTime(state.duration_ms)}</span>
        </div>
      </header>

      {/* Área Principal de Letras con Auto-Scroll */}
      <main className="lyrics-viewport">
        {state.lyrics_status === 'LOADING' && (
          <div className="status-message-container">
            <div className="spinner" />
            <p className="status-text">Buscando letra sincronizada en LRCLIB...</p>
          </div>
        )}

        {state.lyrics_status === 'NO_LYRICS' && (
          <div className="status-message-container">
            <div className="instrumental-icon">🎵</div>
            <h3 className="status-title">Pista Instrumental</h3>
            <p className="status-text">No se encontraron letras sincronizadas para esta canción.</p>
          </div>
        )}

        {state.lyrics_status === 'UNSYNCED' && (
          <div className="unsynced-lyrics-container">
            <p className="unsynced-badge">Letra no sincronizada</p>
            <div className="unsynced-text-flow">
              {state.lyrics_lines.length > 0 ? (
                state.lyrics_lines.map((l, i) => (
                  <p key={i} className="plain-line">{l.text}</p>
                ))
              ) : (
                <p className="plain-line">Letra disponible en modo texto plano.</p>
              )}
            </div>
          </div>
        )}

        {state.lyrics_status === 'SYNCED' && (
          <div className="lyrics-scroll-list">
            {/* Espaciador superior para que el primer verso empiece centrado */}
            <div className="lyrics-spacer" />

            {/* Mensaje de introducción instrumental */}
            {activeLineIndex === -1 && (
              <div className="intro-indicator">
                <span className="music-notes">♪ ♪ ♪</span>
                <span className="intro-text">Introducción Instrumental</span>
                {state.lyrics_lines.length > 0 && (
                  <span className="intro-countdown">
                    Primer verso en {formatTime(state.lyrics_lines[0].timestamp_ms)}
                  </span>
                )}
              </div>
            )}

            {/* Lista de Versos */}
            {state.lyrics_lines.map((line, index) => {
              const isActive = index === activeLineIndex;
              const isPast = index < activeLineIndex;
              const distance = Math.abs(index - activeLineIndex);

              return (
                <div
                  key={index}
                  ref={(el) => {
                    lineRefs.current[index] = el;
                  }}
                  className={`lyric-line-wrapper ${
                    isActive ? 'line-active' : isPast ? 'line-past' : 'line-future'
                  }`}
                  style={{
                    // Atenuación gradual según distancia del verso activo
                    opacity: isActive ? 1 : Math.max(0.2, 0.7 - distance * 0.12),
                  }}
                  onClick={() => onSeekTo && onSeekTo(line.timestamp_ms)}
                  title="Haz clic para saltar a esta línea"
                >
                  <p className="lyric-text">{line.text || '♪'}</p>
                </div>
              );
            })}

            {/* Espaciador inferior */}
            <div className="lyrics-spacer" />
          </div>
        )}
      </main>
    </div>
  );
};
