// Display information for music cues without touching the original document.
import { MUSIC_LABELS } from './labels.js';

function clock(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0));
  const h = Math.floor(seconds / 3600), m = Math.floor(seconds / 60) % 60, s = seconds % 60;
  const two = n => String(n).padStart(2, '0');
  return h ? `${h}:${two(m)}:${two(s)}` : `${two(m)}:${two(s)}`;
}

export function musicRows(cues) {
  return (Array.isArray(cues) ? cues : []).slice().sort((a, b) => Number(a.start) - Number(b.start)).map(c => ({
    time: `${clock(c.start)}–${clock(c.end)}`, title: c.title || 'Không rõ tên', composer: c.composer || 'Không rõ tác giả',
    role: MUSIC_LABELS.roles[c.role] || '', url: c.audio_url || '',
  }));
}
