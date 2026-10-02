export interface LyricLine {
  timestamp_ms: number;
  text: string;
}

export type LyricsStatus =
  | 'SYNCED'
  | 'UNSYNCED'
  | 'NO_LYRICS'
  | 'LOADING'
  | 'STOPPED'
  | 'ERROR'
  | 'IDLE';

export interface SyncedPlaybackState {
  track: string;
  artist: string;
  album?: string;
  duration_ms: number;
  position_ms: number;
  is_playing: boolean;
  lyrics_status: LyricsStatus;
  lyrics_lines: LyricLine[];
  active_line_index: number;
  active_line_text?: string;
  next_line_text?: string;
  device_name?: string;
  generated_at?: number;
  reference_timestamp_ms: number;
}
