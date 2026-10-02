import { useState, useEffect, useRef } from 'react';
import type { SyncedPlaybackState, LyricLine } from '../types';

interface UseSyncedLyricsResult {
  state: SyncedPlaybackState | null;
  interpolatedPositionMs: number;
  activeLineIndex: number;
  isConnected: boolean;
  serverUrl: string;
}

function findActiveLineIndex(positionMs: number, lines: LyricLine[]): number {
  if (!lines || lines.length === 0) return -1;
  if (positionMs < lines[0].timestamp_ms) return -1;

  let low = 0;
  let high = lines.length - 1;
  let best = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (lines[mid].timestamp_ms <= positionMs) {
      best = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return best;
}

export function useSyncedLyrics(): UseSyncedLyricsResult {
  const [state, setState] = useState<SyncedPlaybackState | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [interpolatedPositionMs, setInterpolatedPositionMs] = useState<number>(0);
  const [activeLineIndex, setActiveLineIndex] = useState<number>(-1);

  // Anclas de tiempo locales para interpolación fluida a 60 fps
  const anchorPositionRef = useRef<number>(0);
  const anchorPerfTimeRef = useRef<number>(performance.now());
  const isPlayingRef = useRef<boolean>(false);
  const durationMsRef = useRef<number>(0);
  const linesRef = useRef<LyricLine[]>([]);

  // Determinar URL de WebSocket
  const host = window.location.hostname || 'localhost';
  const wsPort = window.location.port === '5173' ? '8000' : (window.location.port || '8000');
  const serverUrl = `http://${host}:${wsPort}`;
  const wsUrl = `ws://${host}:${wsPort}/ws/playback`;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let isDisposed = false;

    function connect() {
      if (isDisposed) return;

      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('[useSyncedLyrics] Conectado al servidor WebSocket:', wsUrl);
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data: SyncedPlaybackState = JSON.parse(event.data);
            setState(data);

            // Actualizar anclas de sincronización
            anchorPositionRef.current = data.position_ms;
            anchorPerfTimeRef.current = performance.now();
            isPlayingRef.current = data.is_playing;
            durationMsRef.current = data.duration_ms;
            linesRef.current = data.lyrics_lines || [];

            // Actualizar índice inicial
            const idx = findActiveLineIndex(data.position_ms, linesRef.current);
            setActiveLineIndex(idx);
            setInterpolatedPositionMs(data.position_ms);
          } catch (e) {
            console.error('[useSyncedLyrics] Error parseando mensaje WS:', e);
          }
        };

        ws.onclose = () => {
          console.warn('[useSyncedLyrics] Conexión WebSocket cerrada. Reintentando en 2s...');
          setIsConnected(false);
          if (!isDisposed) {
            reconnectTimer = window.setTimeout(connect, 2000);
          }
        };

        ws.onerror = (err) => {
          console.error('[useSyncedLyrics] Error en WebSocket:', err);
          ws?.close();
        };
      } catch (err) {
        console.error('[useSyncedLyrics] Error instanciando WebSocket:', err);
        if (!isDisposed) {
          reconnectTimer = window.setTimeout(connect, 2000);
        }
      }
    }

    connect();

    return () => {
      isDisposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [wsUrl]);

  // Bucle de interpolación local de alta precisión a 60 fps (requestAnimationFrame)
  useEffect(() => {
    let animFrameId: number;

    function loop() {
      if (isPlayingRef.current) {
        const elapsedMs = performance.now() - anchorPerfTimeRef.current;
        const currentMs = Math.min(
          durationMsRef.current,
          Math.max(0, anchorPositionRef.current + elapsedMs)
        );

        setInterpolatedPositionMs(currentMs);

        // Recalcular verso activo suavemente
        const idx = findActiveLineIndex(currentMs, linesRef.current);
        setActiveLineIndex(idx);
      } else {
        setInterpolatedPositionMs(anchorPositionRef.current);
        const idx = findActiveLineIndex(anchorPositionRef.current, linesRef.current);
        setActiveLineIndex(idx);
      }

      animFrameId = requestAnimationFrame(loop);
    }

    animFrameId = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(animFrameId);
    };
  }, []);

  return {
    state,
    interpolatedPositionMs,
    activeLineIndex,
    isConnected,
    serverUrl,
  };
}
