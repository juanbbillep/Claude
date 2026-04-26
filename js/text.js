import { state, uid, emit } from './state.js';

export function addTextClip() {
  const t = state.currentTime;
  const clip = {
    id: uid('tc'),
    type: 'text',
    start: t,
    duration: 3,
    text: 'Tu texto aquí',
    x: 50,
    y: 85,
    fontSize: 56,
    color: '#ffffff',
    font: 'Inter, sans-serif',
    align: 'center',
    bg: 'transparent',
    bold: true,
    shadow: true,
  };
  state.tracks.text.push(clip);
  state.tracks.text.sort((a, b) => a.start - b.start);
  state.selectedId = clip.id;
  emit('timeline');
}
