// Global app state and tiny pub/sub.
const listeners = new Set();

export const state = {
  media: [],            // { id, name, file, url, duration, width, height, video, thumb }
  tracks: {
    video: [],          // { id, type:'video', mediaId, start, in, out }  (timeline coords in seconds)
    text: [],           // { id, type:'text', start, duration, text, x, y, fontSize, color, font, align, bg }
  },
  selectedId: null,
  currentTime: 0,
  playing: false,
  pxPerSec: 80,
  canvasWidth: 1280,
  canvasHeight: 720,
};

let nextId = 1;
export const uid = (prefix = 'id') => `${prefix}_${nextId++}_${Date.now().toString(36)}`;

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emit(evt = 'change') {
  for (const fn of listeners) fn(evt);
}

export function getClip(id) {
  return state.tracks.video.find(c => c.id === id) || state.tracks.text.find(c => c.id === id);
}

export function removeClip(id) {
  state.tracks.video = state.tracks.video.filter(c => c.id !== id);
  state.tracks.text = state.tracks.text.filter(c => c.id !== id);
  if (state.selectedId === id) state.selectedId = null;
}

export function totalDuration() {
  const all = [...state.tracks.video, ...state.tracks.text];
  if (!all.length) return 0;
  return Math.max(...all.map(c => c.start + clipDuration(c)));
}

export function clipDuration(c) {
  if (c.type === 'video') return c.out - c.in;
  return c.duration;
}

// Sort video clips by start time and return any clip active at time t.
export function videoClipAt(t) {
  for (const c of state.tracks.video) {
    if (t >= c.start && t < c.start + (c.out - c.in)) return c;
  }
  return null;
}

export function textClipsAt(t) {
  return state.tracks.text.filter(c => t >= c.start && t < c.start + c.duration);
}
