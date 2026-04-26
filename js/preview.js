import { state, videoClipAt, textClipsAt, totalDuration, emit } from './state.js';

const canvas = document.getElementById('preview');
const ctx = canvas.getContext('2d');
const timeDisplay = document.getElementById('time-display');

let rafId = null;
let lastFrameWall = 0;

export function initPreview() {
  drawFrame();
}

export function play() {
  if (state.playing) return;
  if (state.currentTime >= totalDuration() - 0.01) state.currentTime = 0;
  state.playing = true;
  lastFrameWall = performance.now();
  // Pre-roll: seek the active video clip so playback is in sync.
  syncActiveVideo(true);
  loop();
  emit('play');
}

export function pause() {
  state.playing = false;
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
  // Pause all videos.
  for (const m of state.media) m.video.pause();
  emit('pause');
}

export function togglePlay() {
  state.playing ? pause() : play();
}

function loop() {
  if (!state.playing) return;
  const now = performance.now();
  const dt = (now - lastFrameWall) / 1000;
  lastFrameWall = now;
  state.currentTime += dt;
  const dur = totalDuration();
  if (state.currentTime >= dur) {
    state.currentTime = dur;
    drawFrame();
    pause();
    return;
  }
  syncActiveVideo(false);
  drawFrame();
  emit('tick');
  rafId = requestAnimationFrame(loop);
}

let activeVideoId = null;
function syncActiveVideo(forceSeek) {
  const clip = videoClipAt(state.currentTime);
  if (!clip) {
    if (activeVideoId) {
      const prev = state.media.find(m => m.id === activeVideoId);
      if (prev) prev.video.pause();
      activeVideoId = null;
    }
    return;
  }
  const m = state.media.find(m => m.id === clip.mediaId);
  if (!m) return;
  const sourceTime = clip.in + (state.currentTime - clip.start);
  if (activeVideoId && activeVideoId !== m.id) {
    const prev = state.media.find(mm => mm.id === activeVideoId);
    if (prev) prev.video.pause();
  }
  activeVideoId = m.id;
  // Re-seek if drift > 0.15s or we just started.
  if (forceSeek || Math.abs(m.video.currentTime - sourceTime) > 0.15) {
    try { m.video.currentTime = sourceTime; } catch (_) {}
  }
  if (state.playing && m.video.paused) {
    m.video.muted = true; // we explicitly skip audio
    m.video.play().catch(() => {});
  } else if (!state.playing && !m.video.paused) {
    m.video.pause();
  }
}

export function drawFrame() {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const clip = videoClipAt(state.currentTime);
  if (clip) {
    const m = state.media.find(mm => mm.id === clip.mediaId);
    if (m && m.video.readyState >= 2) {
      // Letterbox/pillarbox to fit the canvas while preserving aspect.
      const vw = m.video.videoWidth || 16;
      const vh = m.video.videoHeight || 9;
      const scale = Math.min(canvas.width / vw, canvas.height / vh);
      const dw = vw * scale;
      const dh = vh * scale;
      const dx = (canvas.width - dw) / 2;
      const dy = (canvas.height - dh) / 2;
      try { ctx.drawImage(m.video, dx, dy, dw, dh); } catch (_) {}
    }
  }

  // Draw all visible text clips.
  for (const t of textClipsAt(state.currentTime)) {
    drawTextClip(t);
  }

  if (timeDisplay) {
    timeDisplay.textContent = `${fmt(state.currentTime)} / ${fmt(totalDuration())}`;
  }
}

function drawTextClip(t) {
  ctx.save();
  ctx.font = `${t.bold ? 'bold ' : ''}${t.fontSize}px ${t.font || 'Inter, sans-serif'}`;
  ctx.textAlign = t.align || 'center';
  ctx.textBaseline = 'middle';
  const x = (t.x / 100) * canvas.width;
  const y = (t.y / 100) * canvas.height;

  const lines = (t.text || '').split('\n');
  const lh = t.fontSize * 1.2;
  const totalH = lines.length * lh;

  if (t.bg && t.bg !== 'transparent') {
    const padX = t.fontSize * 0.4;
    const padY = t.fontSize * 0.2;
    let maxW = 0;
    for (const ln of lines) maxW = Math.max(maxW, ctx.measureText(ln).width);
    let bgX;
    if (t.align === 'left') bgX = x - padX;
    else if (t.align === 'right') bgX = x - maxW - padX;
    else bgX = x - maxW / 2 - padX;
    ctx.fillStyle = t.bg;
    ctx.fillRect(bgX, y - totalH / 2 - padY, maxW + padX * 2, totalH + padY * 2);
  }

  ctx.fillStyle = t.color || '#ffffff';
  if (t.shadow) {
    ctx.shadowColor = 'rgba(0,0,0,0.7)';
    ctx.shadowBlur = 6;
    ctx.shadowOffsetY = 2;
  }
  lines.forEach((ln, i) => {
    const ly = y - totalH / 2 + lh * (i + 0.5);
    ctx.fillText(ln, x, ly);
  });
  ctx.restore();
}

function fmt(s) {
  s = Math.max(0, s || 0);
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60).toString().padStart(2, '0');
  const cs = Math.floor((s % 1) * 100).toString().padStart(2, '0');
  return `${m.toString().padStart(2, '0')}:${sec}.${cs}`;
}
