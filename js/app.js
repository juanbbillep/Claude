import { state, subscribe, emit } from './state.js';
import { initMedia } from './media.js';
import { initTimeline, render as renderTimeline, splitAtPlayhead, deleteSelected, seekTo, updatePlayhead } from './timeline.js';
import { initPreview, drawFrame, togglePlay, play, pause } from './preview.js';
import { renderInspector } from './inspector.js';
import { addTextClip } from './text.js';
import { startExport } from './export.js';

initMedia();
initTimeline();
initPreview();
renderInspector();

document.getElementById('btn-add-text').addEventListener('click', addTextClip);
document.getElementById('btn-split').addEventListener('click', splitAtPlayhead);
document.getElementById('btn-delete').addEventListener('click', deleteSelected);
document.getElementById('btn-export').addEventListener('click', startExport);

document.getElementById('btn-play').addEventListener('click', togglePlay);
document.getElementById('btn-rewind').addEventListener('click', () => { pause(); seekTo(0); });
document.getElementById('btn-end').addEventListener('click', () => { pause(); seekTo(Infinity); });

document.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
  if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
  else if (e.key === 's' || e.key === 'S') { splitAtPlayhead(); }
  else if (e.key === 'Delete' || e.key === 'Backspace') { deleteSelected(); }
  else if (e.key === 'ArrowLeft') { pause(); seekTo(state.currentTime - (e.shiftKey ? 1 : 1/30)); }
  else if (e.key === 'ArrowRight') { pause(); seekTo(state.currentTime + (e.shiftKey ? 1 : 1/30)); }
});

subscribe((evt) => {
  if (evt === 'tick') { updatePlayhead(); return; }
  if (evt === 'seek') { drawFrame(); updatePlayhead(); return; }
  // Anything else is a structural change.
  renderTimeline();
  renderInspector();
  drawFrame();
  updatePlayhead();
  // Update play button label.
  const btn = document.getElementById('btn-play');
  if (btn) btn.textContent = state.playing ? '⏸' : '▶';
});

// Initial paint.
emit('init');
