import React from 'react';
import { useSyncedLyrics } from './hooks/useSyncedLyrics';
import { KaraokeView } from './components/KaraokeView';
import { DiagnosticPanel } from './components/DiagnosticPanel';

export const App: React.FC = () => {
  const {
    state,
    interpolatedPositionMs,
    activeLineIndex,
    isConnected,
    isCastMode,
    serverUrl,
  } = useSyncedLyrics();

  const handleSeekTo = async (timestampMs: number) => {
    try {
      await fetch(`${serverUrl}/api/mock/seek`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_ms: timestampMs }),
      });
    } catch (e) {
      console.error('Error enviando seek:', e);
    }
  };

  return (
    <div className="app-root">
      <KaraokeView
        state={state}
        positionMs={interpolatedPositionMs}
        activeLineIndex={activeLineIndex}
        isConnected={isConnected}
        onSeekTo={handleSeekTo}
      />

      <DiagnosticPanel
        state={state}
        positionMs={interpolatedPositionMs}
        activeLineIndex={activeLineIndex}
        isConnected={isConnected}
        isCastMode={isCastMode}
        serverUrl={serverUrl}
      />
    </div>
  );
};

export default App;
