import React, { useState } from 'react';
import type { SyncedPlaybackState } from '../types';

interface DiagnosticPanelProps {
  state: SyncedPlaybackState | null;
  positionMs: number;
  activeLineIndex: number;
  isConnected: boolean;
  serverUrl: string;
}

export const DiagnosticPanel: React.FC<DiagnosticPanelProps> = ({
  state,
  positionMs,
  activeLineIndex,
  isConnected,
  serverUrl,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [customTitle, setCustomTitle] = useState<string>('Hotel California');
  const [customArtist, setCustomArtist] = useState<string>('Eagles');
  const [customAlbum, setCustomAlbum] = useState<string>('Hotel California');

  const sendPost = async (path: string, body?: any) => {
    try {
      await fetch(`${serverUrl}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      console.error(`Error en POST ${path}:`, err);
    }
  };

  const handlePlay = () => sendPost('/api/mock/play?start_ms=0');
  const handlePause = () => sendPost('/api/mock/pause');
  const handleResume = () => sendPost('/api/mock/resume');
  const handleSeek = (posMs: number) => sendPost('/api/mock/seek', { position_ms: posMs });
  const handleNext = () => sendPost('/api/mock/next');
  const handleLoadCustom = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customTitle || !customArtist) return;
    sendPost('/api/mock/load', {
      title: customTitle,
      artist: customArtist,
      album: customAlbum,
      duration_ms: 390000,
      start_position_ms: 0,
      is_playing: true,
    });
  };

  return (
    <div className={`diag-panel-container ${isOpen ? 'open' : 'closed'}`}>
      <button
        className="diag-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
        title="Mostrar/Ocultar Panel de Simulación (D)"
      >
        🛠️ {isOpen ? 'Ocultar Panel' : 'Panel Simulación'}
      </button>

      {isOpen && (
        <div className="diag-panel-content">
          <div className="diag-header">
            <h4>Panel de Control y Diagnóstico (Mock)</h4>
            <span className={`diag-badge ${isConnected ? 'online' : 'offline'}`}>
              {isConnected ? 'WS Online' : 'WS Offline'}
            </span>
          </div>

          <div className="diag-telemetry">
            <div>
              <strong>Posición:</strong> {(positionMs / 1000).toFixed(1)}s /{' '}
              {state ? (state.duration_ms / 1000).toFixed(1) : 0}s
            </div>
            <div>
              <strong>Línea Activa:</strong> #{activeLineIndex}{' '}
              {state?.active_line_text ? `("${state.active_line_text.slice(0, 20)}...")` : ''}
            </div>
            <div>
              <strong>Letras:</strong> {state?.lyrics_status || 'N/A'} (
              {state?.lyrics_lines?.length || 0} versos)
            </div>
          </div>

          <div className="diag-btn-group">
            <button className="btn-primary" onClick={handlePlay}>
              ▶ Iniciar (0s)
            </button>
            {state?.is_playing ? (
              <button className="btn-warning" onClick={handlePause}>
                ⏸ Pausar
              </button>
            ) : (
              <button className="btn-success" onClick={handleResume}>
                ▶ Reanudar
              </button>
            )}
            <button className="btn-secondary" onClick={handleNext}>
              ⏭ Siguiente Pista
            </button>
          </div>

          <div className="diag-seek-section">
            <span className="section-label">Saltos Rápidos (Seek):</span>
            <div className="seek-buttons">
              <button onClick={() => handleSeek(0)}>0s (Intro)</button>
              <button onClick={() => handleSeek(15000)}>15s</button>
              <button onClick={() => handleSeek(25000)}>25s (Coro)</button>
              <button onClick={() => handleSeek(42000)}>42s</button>
              <button onClick={() => handleSeek(60000)}>60s</button>
            </div>
          </div>

          <form className="diag-custom-form" onSubmit={handleLoadCustom}>
            <span className="section-label">Cargar Pista Real en LRCLIB:</span>
            <div className="form-row">
              <input
                type="text"
                placeholder="Título"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
              />
              <input
                type="text"
                placeholder="Artista"
                value={customArtist}
                onChange={(e) => setCustomArtist(e.target.value)}
              />
              <input
                type="text"
                placeholder="Álbum (opcional)"
                value={customAlbum}
                onChange={(e) => setCustomAlbum(e.target.value)}
              />
            </div>
            <button type="submit" className="btn-small">
              Cargar y Buscar Letra
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
