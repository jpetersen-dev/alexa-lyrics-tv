import React, { useState } from 'react';
import type { SyncedPlaybackState } from '../types';

interface DiagnosticPanelProps {
  state: SyncedPlaybackState | null;
  positionMs: number;
  activeLineIndex: number;
  isConnected: boolean;
  isCastMode?: boolean;
  serverUrl: string;
}

interface CastDevice {
  name: string;
  model: string;
  host: string;
  port: number;
  uuid: string;
}

export const DiagnosticPanel: React.FC<DiagnosticPanelProps> = ({
  state,
  positionMs,
  activeLineIndex,
  isConnected,
  isCastMode,
  serverUrl,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [customTitle, setCustomTitle] = useState<string>('Hotel California');
  const [customArtist, setCustomArtist] = useState<string>('Eagles');
  const [customAlbum, setCustomAlbum] = useState<string>('Hotel California');

  // Estado de Cast
  const [castConnected, setCastConnected] = useState<boolean>(false);
  const [castDeviceName, setCastDeviceName] = useState<string | null>(null);
  const [castDevices, setCastDevices] = useState<CastDevice[]>([]);
  const [isScanningCast, setIsScanningCast] = useState<boolean>(false);
  const [manualIp, setManualIp] = useState<string>('');
  const [castAppId, setCastAppId] = useState<string>('CC1AD845');

  const sendPost = async (path: string, body?: any) => {
    try {
      const res = await fetch(`${serverUrl}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      return await res.json();
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

  const handleScanCast = async () => {
    setIsScanningCast(true);
    try {
      const res = await fetch(`${serverUrl}/api/cast/devices?timeout=3`);
      const data = await res.json();
      setCastDevices(data.devices || []);
    } catch (e) {
      console.error('Error buscando dispositivos Cast:', e);
    } finally {
      setIsScanningCast(false);
    }
  };

  const handleConnectCast = async (host?: string, name?: string) => {
    const res = await sendPost('/api/cast/connect', { host, name });
    if (res && res.device) {
      setCastConnected(true);
      setCastDeviceName(res.device);
    }
  };

  const handleLaunchCast = async () => {
    await sendPost('/api/cast/launch', { app_id: castAppId });
  };

  const handleDisconnectCast = async () => {
    await sendPost('/api/cast/disconnect');
    setCastConnected(false);
    setCastDeviceName(null);
  };


  // Estado de Proveedor y AutoCast
  const [activeProvider, setActiveProvider] = useState<string>('mock');
  const [autoCastEnabled, setAutoCastEnabled] = useState<boolean>(false);

  // Cargar estado inicial de proveedores
  React.useEffect(() => {
    fetch(`${serverUrl}/api/playback/provider`)
      .then((r) => r.json())
      .then((data) => {
        if (data.active_provider) setActiveProvider(data.active_provider);
        if (data.autocast) setAutoCastEnabled(data.autocast.enabled);
      })
      .catch(() => {});
  }, [serverUrl]);

  const handleSetProvider = async (provider: string) => {
    const res = await sendPost('/api/playback/provider', { provider });
    if (res) setActiveProvider(provider);
  };

  const handleToggleAutoCast = async () => {
    const nextState = !autoCastEnabled;
    const res = await sendPost('/api/autocast/config', { enabled: nextState });
    if (res) setAutoCastEnabled(nextState);
  };

  const handleSimulateAlexaWebhook = async () => {
    await sendPost('/api/playback/update', {
      title: customTitle,
      artist: customArtist,
      album: customAlbum,
      duration_ms: 354000,
      progress_ms: 12000,
      is_playing: true,
      device_name: 'Echo Dot Alexa (Salón)',
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
            <h4>Panel de Control y Diagnóstico</h4>
            <div style={{ display: 'flex', gap: '6px' }}>
              <span className={`diag-badge ${isConnected ? 'online' : 'offline'}`}>
                {isConnected ? 'WS Online' : 'WS Offline'}
              </span>
              <span className={`diag-badge ${isCastMode ? 'online' : 'secondary'}`}>
                {isCastMode ? 'Cast Receiver' : 'Web Mode'}
              </span>
            </div>
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

          {/* Selector de Fuente de Audio */}
          <div style={{ marginTop: '10px', padding: '6px', background: '#12121a', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span className="section-label">Fuente de Audio:</span>
              <span style={{ fontSize: '11px', color: '#38bdf8' }}>{state?.device_name || 'Sin altavoz'}</span>
            </div>
            <div style={{ display: 'flex', gap: '4px' }}>
              {['mock', 'webhook', 'homeassistant', 'spotify'].map((p) => (
                <button
                  key={p}
                  className={`btn-small ${activeProvider === p ? 'btn-primary' : ''}`}
                  onClick={() => handleSetProvider(p)}
                  style={{ fontSize: '11px', padding: '2px 6px' }}
                >
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
            {activeProvider === 'webhook' && (
              <button
                className="btn-small"
                onClick={handleSimulateAlexaWebhook}
                style={{ marginTop: '6px', width: '100%', background: '#3b82f6', color: '#fff' }}
              >
                📡 Simular Push de Alexa Echo
              </button>
            )}
            {activeProvider === 'spotify' && (
              <div style={{ marginTop: '6px', display: 'flex', gap: '6px' }}>
                <a
                  href="/api/spotify/login"
                  target="_self"
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    background: '#1db954',
                    color: '#fff',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    textDecoration: 'none',
                    fontWeight: 'bold',
                  }}
                >
                  🟢 Vincular Cuenta de Spotify
                </a>
                <button
                  className="btn-small"
                  onClick={async () => {
                    await fetch('/api/spotify/disconnect', { method: 'POST' });
                    window.location.reload();
                  }}
                  style={{ fontSize: '11px', background: '#374151', color: '#f87171' }}
                >
                  Desvincular
                </button>
              </div>
            )}
          </div>

          {/* Sección de Gestión de Google Cast */}
          <div className="diag-cast-section" style={{ marginTop: '12px', borderTop: '1px solid #333', paddingTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="section-label">📺 Google Cast (Televisor):</span>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', cursor: 'pointer' }}>
                <input type="checkbox" checked={autoCastEnabled} onChange={handleToggleAutoCast} />
                <span>AutoCast TV</span>
              </label>
            </div>

            {castConnected ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                <div style={{ color: '#4ade80', fontSize: '13px' }}>
                  Conectado a: <strong>{castDeviceName}</strong>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <input
                    type="text"
                    placeholder="App ID"
                    value={castAppId}
                    onChange={(e) => setCastAppId(e.target.value)}
                    style={{ width: '100px' }}
                  />
                  <button className="btn-success" onClick={handleLaunchCast}>
                    Lanzar en TV
                  </button>
                  <button className="btn-danger" onClick={handleDisconnectCast}>
                    Desconectar
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button className="btn-small" onClick={handleScanCast} disabled={isScanningCast}>
                    {isScanningCast ? 'Buscando...' : '🔍 Buscar en Wi-Fi'}
                  </button>
                  <input
                    type="text"
                    placeholder="IP ej. 192.168.1.150"
                    value={manualIp}
                    onChange={(e) => setManualIp(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button
                    className="btn-small"
                    onClick={() => handleConnectCast(manualIp)}
                    disabled={!manualIp}
                  >
                    Conectar IP
                  </button>
                </div>
                {castDevices.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                    {castDevices.map((d) => (
                      <div
                        key={d.uuid}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          background: '#1a1a24',
                          padding: '4px 8px',
                          borderRadius: '4px',
                        }}
                      >
                        <span style={{ fontSize: '12px' }}>
                          {d.name} ({d.model})
                        </span>
                        <button
                          className="btn-small"
                          onClick={() => handleConnectCast(undefined, d.name)}
                        >
                          Conectar
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <form className="diag-custom-form" onSubmit={handleLoadCustom} style={{ marginTop: '10px' }}>
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

