import { state, totalDuration, videoClipAt, textClipsAt } from './state.js';

const modal = document.getElementById('export-modal');
const statusEl = document.getElementById('export-status');
const progressEl = document.getElementById('export-progress');
const cancelBtn = document.getElementById('export-cancel');
const downloadLink = document.getElementById('export-download');

let cancelled = false;

export async function startExport() {
  const dur = totalDuration();
  if (dur <= 0) {
    alert('No hay nada que exportar. Añade clips a la línea de tiempo.');
    return;
  }
  cancelled = false;
  modal.classList.remove('hidden');
  downloadLink.classList.add('hidden');
  statusEl.textContent = 'Renderizando…';
  progressEl.value = 0;

  cancelBtn.onclick = () => { cancelled = true; };

  const offCanvas = document.createElement('canvas');
  offCanvas.width = state.canvasWidth;
  offCanvas.height = state.canvasHeight;
  const octx = offCanvas.getContext('2d');

  const fps = 30;
  const stream = offCanvas.captureStream(fps);
  let mime = 'video/webm;codecs=vp9';
  if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/webm;codecs=vp8';
  if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/webm';

  const chunks = [];
  const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6_000_000 });
  recorder.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
  const recordingDone = new Promise(res => { recorder.onstop = () => res(); });
  recorder.start();

  const frameCount = Math.ceil(dur * fps);
  const frameDur = 1 / fps;

  // Pause all videos and seek-render frame by frame.
  for (const m of state.media) { m.video.pause(); m.video.muted = true; }

  for (let i = 0; i < frameCount; i++) {
    if (cancelled) break;
    const t = i * frameDur;
    await renderFrameAt(t, octx, offCanvas);
    progressEl.value = ((i + 1) / frameCount) * 100;
    statusEl.textContent = `Renderizando… ${Math.round(progressEl.value)}% (${(t).toFixed(1)}s / ${dur.toFixed(1)}s)`;
    // Throttle to roughly real-time so MediaRecorder captures distinct frames.
    await sleep(1000 / fps);
  }

  recorder.stop();
  await recordingDone;

  if (cancelled) {
    statusEl.textContent = 'Cancelado.';
    return;
  }

  const blob = new Blob(chunks, { type: mime });
  const url = URL.createObjectURL(blob);
  downloadLink.href = url;
  downloadLink.download = `clipforge_${Date.now()}.webm`;
  downloadLink.classList.remove('hidden');
  statusEl.textContent = `Listo: ${(blob.size / 1e6).toFixed(2)} MB`;
}

async function renderFrameAt(t, ctx, canvas) {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const clip = videoClipAt(t);
  if (clip) {
    const m = state.media.find(mm => mm.id === clip.mediaId);
    if (m) {
      const sourceTime = clip.in + (t - clip.start);
      await seekVideo(m.video, sourceTime);
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

  for (const tx of textClipsAt(t)) {
    drawTextClip(ctx, canvas, tx);
  }
}

function seekVideo(video, time) {
  return new Promise(resolve => {
    if (Math.abs(video.currentTime - time) < 0.01) { resolve(); return; }
    const onSeeked = () => { video.removeEventListener('seeked', onSeeked); resolve(); };
    video.addEventListener('seeked', onSeeked);
    try { video.currentTime = Math.max(0, time); } catch (_) { resolve(); }
  });
}

function drawTextClip(ctx, canvas, t) {
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

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

export function closeExportModal() {
  modal.classList.add('hidden');
}

cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));
