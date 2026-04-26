import { state, emit, getClip, removeClip, clipDuration, totalDuration, uid } from './state.js';
import { addMediaToTimeline } from './media.js';

const ruler = document.getElementById('ruler');
const trackVideo = document.getElementById('track-video');
const trackText = document.getElementById('track-text');
const playhead = document.getElementById('playhead');
const rulerWrap = document.querySelector('.ruler-wrap');
const zoomInput = document.getElementById('zoom');

export function initTimeline() {
  zoomInput.addEventListener('input', () => {
    state.pxPerSec = parseInt(zoomInput.value, 10);
    render();
  });

  // Drag from media bin onto a track.
  for (const trackEl of [trackVideo, trackText]) {
    trackEl.addEventListener('dragover', e => {
      if (e.dataTransfer.types.includes('application/x-clipforge-media') && trackEl.dataset.track === 'video') {
        e.preventDefault();
        trackEl.classList.add('drop-active');
      }
    });
    trackEl.addEventListener('dragleave', () => trackEl.classList.remove('drop-active'));
    trackEl.addEventListener('drop', e => {
      trackEl.classList.remove('drop-active');
      const mediaId = e.dataTransfer.getData('application/x-clipforge-media');
      if (!mediaId || trackEl.dataset.track !== 'video') return;
      e.preventDefault();
      const rect = trackEl.getBoundingClientRect();
      const t = Math.max(0, (e.clientX - rect.left) / state.pxPerSec);
      addMediaToTimeline(mediaId, snap(t));
    });
  }

  // Click on ruler / track empty space to seek.
  rulerWrap.addEventListener('click', e => {
    if (e.target.closest('.clip')) return;
    const rect = trackVideo.getBoundingClientRect();
    const t = Math.max(0, (e.clientX - rect.left) / state.pxPerSec);
    seekTo(t);
  });

  render();
}

export function render() {
  drawRuler();
  renderTrack(trackVideo, state.tracks.video, 'video');
  renderTrack(trackText, state.tracks.text, 'text');
  updatePlayhead();
  resizeTracksToContent();
}

function resizeTracksToContent() {
  const dur = Math.max(totalDuration() + 5, 30);
  const w = dur * state.pxPerSec;
  trackVideo.style.width = w + 'px';
  trackText.style.width = w + 'px';
  ruler.width = w;
  drawRuler();
}

function drawRuler() {
  const ctx = ruler.getContext('2d');
  const w = ruler.width;
  const h = ruler.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#1f262e';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#3a424d';
  ctx.fillStyle = '#8b949e';
  ctx.font = '10px ui-monospace, monospace';
  ctx.textBaseline = 'top';

  const pps = state.pxPerSec;
  const stepSec = pps >= 120 ? 1 : pps >= 60 ? 2 : pps >= 30 ? 5 : 10;
  for (let s = 0, x = 0; x <= w; s += stepSec, x = s * pps) {
    ctx.beginPath();
    ctx.moveTo(x + 0.5, 0);
    ctx.lineTo(x + 0.5, h);
    ctx.stroke();
    ctx.fillText(formatTime(s), x + 4, 4);
    // half ticks
    for (let i = 1; i < 5; i++) {
      const subX = x + (stepSec * pps / 5) * i;
      ctx.beginPath();
      ctx.moveTo(subX + 0.5, h - 6);
      ctx.lineTo(subX + 0.5, h);
      ctx.stroke();
    }
  }
}

function renderTrack(trackEl, clips, kind) {
  trackEl.innerHTML = '';
  for (const clip of clips) {
    const el = document.createElement('div');
    el.className = 'clip' + (kind === 'text' ? ' text-clip' : '') + (state.selectedId === clip.id ? ' selected' : '');
    el.dataset.clipId = clip.id;
    el.style.left = (clip.start * state.pxPerSec) + 'px';
    el.style.width = (clipDuration(clip) * state.pxPerSec) + 'px';
    el.innerHTML = `
      <div class="clip-handle left"></div>
      <div class="clip-label">${labelFor(clip)}</div>
      <div class="clip-handle right"></div>
    `;
    attachClipInteractions(el, clip);
    trackEl.appendChild(el);
  }
}

function labelFor(clip) {
  if (clip.type === 'video') {
    const m = state.media.find(m => m.id === clip.mediaId);
    return m ? m.name : 'Video';
  }
  return clip.text || 'Texto';
}

function attachClipInteractions(el, clip) {
  el.addEventListener('mousedown', e => {
    if (e.button !== 0) return;
    const handle = e.target.classList.contains('clip-handle');
    state.selectedId = clip.id;
    emit('select');

    if (handle) {
      const side = e.target.classList.contains('left') ? 'left' : 'right';
      startResize(e, clip, side);
    } else {
      startMove(e, clip);
    }
  });
}

function startMove(e, clip) {
  const startX = e.clientX;
  const startStart = clip.start;
  const onMove = (ev) => {
    const dx = ev.clientX - startX;
    let newStart = Math.max(0, startStart + dx / state.pxPerSec);
    newStart = snap(newStart);
    clip.start = newStart;
    render();
  };
  const onUp = () => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    if (clip.type === 'video') state.tracks.video.sort((a, b) => a.start - b.start);
    emit('timeline');
  };
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

function startResize(e, clip, side) {
  const startX = e.clientX;
  const startStart = clip.start;
  const orig = { ...clip };
  const onMove = (ev) => {
    const dx = (ev.clientX - startX) / state.pxPerSec;
    if (clip.type === 'video') {
      if (side === 'left') {
        const newIn = Math.max(0, Math.min(orig.out - 0.1, orig.in + dx));
        clip.in = newIn;
        clip.start = startStart + (newIn - orig.in);
      } else {
        const m = state.media.find(m => m.id === clip.mediaId);
        const maxOut = m ? m.duration : orig.out;
        clip.out = Math.max(orig.in + 0.1, Math.min(maxOut, orig.out + dx));
      }
    } else {
      if (side === 'left') {
        const newDelta = dx;
        const newDur = Math.max(0.2, orig.duration - newDelta);
        clip.start = Math.max(0, startStart + (orig.duration - newDur));
        clip.duration = newDur;
      } else {
        clip.duration = Math.max(0.2, orig.duration + dx);
      }
    }
    render();
  };
  const onUp = () => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    emit('timeline');
  };
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

function snap(t) {
  // Snap to 0.05s for smoother positioning.
  return Math.round(t * 20) / 20;
}

export function updatePlayhead() {
  const x = state.currentTime * state.pxPerSec;
  playhead.style.left = x + 'px';
}

export function seekTo(t) {
  state.currentTime = Math.max(0, Math.min(totalDuration() || 0, t));
  emit('seek');
}

export function splitAtPlayhead() {
  const t = state.currentTime;
  let didSplit = false;
  // Split video clip if any covers t.
  for (const c of [...state.tracks.video]) {
    const end = c.start + (c.out - c.in);
    if (t > c.start + 0.05 && t < end - 0.05) {
      const offset = t - c.start;
      const right = {
        id: uid('vc'),
        type: 'video',
        mediaId: c.mediaId,
        start: t,
        in: c.in + offset,
        out: c.out,
      };
      c.out = c.in + offset;
      state.tracks.video.push(right);
      didSplit = true;
    }
  }
  for (const c of [...state.tracks.text]) {
    const end = c.start + c.duration;
    if (t > c.start + 0.05 && t < end - 0.05) {
      const offset = t - c.start;
      const right = { ...c, id: uid('tc'), start: t, duration: c.duration - offset };
      c.duration = offset;
      state.tracks.text.push(right);
      didSplit = true;
    }
  }
  if (didSplit) {
    state.tracks.video.sort((a, b) => a.start - b.start);
    state.tracks.text.sort((a, b) => a.start - b.start);
    emit('timeline');
  }
}

export function deleteSelected() {
  if (!state.selectedId) return;
  removeClip(state.selectedId);
  emit('timeline');
}

function formatTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60).toString().padStart(2, '0');
  return `${m}:${sec}`;
}
