import { state, emit, getClip, clipDuration } from './state.js';

const inspector = document.getElementById('inspector');

export function renderInspector() {
  const clip = state.selectedId ? getClip(state.selectedId) : null;
  if (!clip) {
    inspector.innerHTML = '<p class="hint">Selecciona un clip en la línea de tiempo.</p>';
    return;
  }
  if (clip.type === 'video') renderVideoInspector(clip);
  else renderTextInspector(clip);
}

function renderVideoInspector(clip) {
  const m = state.media.find(mm => mm.id === clip.mediaId);
  inspector.innerHTML = `
    <div class="field">
      <label>Clip</label>
      <input type="text" value="${m ? m.name : ''}" disabled />
    </div>
    <div class="field-row">
      <div class="field">
        <label>Inicio (s)</label>
        <input type="number" step="0.05" min="0" id="f-start" value="${clip.start.toFixed(2)}" />
      </div>
      <div class="field">
        <label>Duración (s)</label>
        <input type="number" step="0.05" min="0.1" id="f-dur" value="${(clip.out - clip.in).toFixed(2)}" />
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>In origen (s)</label>
        <input type="number" step="0.05" min="0" id="f-in" value="${clip.in.toFixed(2)}" />
      </div>
      <div class="field">
        <label>Out origen (s)</label>
        <input type="number" step="0.05" min="0.1" id="f-out" value="${clip.out.toFixed(2)}" />
      </div>
    </div>
  `;
  const $ = (id) => inspector.querySelector('#' + id);
  $('f-start').addEventListener('input', e => { clip.start = +e.target.value; emit('timeline'); });
  $('f-in').addEventListener('input', e => {
    const v = Math.max(0, Math.min(clip.out - 0.1, +e.target.value));
    clip.in = v; emit('timeline');
  });
  $('f-out').addEventListener('input', e => {
    const max = m ? m.duration : Infinity;
    const v = Math.max(clip.in + 0.1, Math.min(max, +e.target.value));
    clip.out = v; emit('timeline');
  });
  $('f-dur').addEventListener('input', e => {
    const newDur = Math.max(0.1, +e.target.value);
    const max = m ? m.duration : Infinity;
    clip.out = Math.min(max, clip.in + newDur);
    emit('timeline');
  });
}

function renderTextInspector(clip) {
  inspector.innerHTML = `
    <div class="field">
      <label>Texto</label>
      <textarea id="t-text">${escapeHtml(clip.text || '')}</textarea>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Inicio (s)</label>
        <input type="number" step="0.05" min="0" id="t-start" value="${clip.start.toFixed(2)}" />
      </div>
      <div class="field">
        <label>Duración (s)</label>
        <input type="number" step="0.05" min="0.2" id="t-dur" value="${clip.duration.toFixed(2)}" />
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>X (%)</label>
        <input type="number" step="1" min="0" max="100" id="t-x" value="${clip.x}" />
      </div>
      <div class="field">
        <label>Y (%)</label>
        <input type="number" step="1" min="0" max="100" id="t-y" value="${clip.y}" />
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Tamaño (px)</label>
        <input type="number" step="1" min="8" id="t-size" value="${clip.fontSize}" />
      </div>
      <div class="field">
        <label>Alineación</label>
        <select id="t-align">
          <option value="left" ${clip.align === 'left' ? 'selected' : ''}>Izquierda</option>
          <option value="center" ${clip.align === 'center' ? 'selected' : ''}>Centro</option>
          <option value="right" ${clip.align === 'right' ? 'selected' : ''}>Derecha</option>
        </select>
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Color</label>
        <input type="color" id="t-color" value="${clip.color || '#ffffff'}" />
      </div>
      <div class="field">
        <label>Fondo</label>
        <input type="color" id="t-bg" value="${clip.bg && clip.bg !== 'transparent' ? clip.bg : '#000000'}" />
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label><input type="checkbox" id="t-bg-on" ${clip.bg && clip.bg !== 'transparent' ? 'checked' : ''}/> Fondo activo</label>
      </div>
      <div class="field">
        <label><input type="checkbox" id="t-bold" ${clip.bold ? 'checked' : ''}/> Negrita</label>
      </div>
    </div>
    <div class="field">
      <label><input type="checkbox" id="t-shadow" ${clip.shadow ? 'checked' : ''}/> Sombra</label>
    </div>
    <div class="field">
      <label>Fuente</label>
      <select id="t-font">
        ${['Inter, sans-serif', 'Arial, sans-serif', 'Georgia, serif', 'Courier New, monospace', 'Impact, sans-serif'].map(f =>
          `<option value="${f}" ${clip.font === f ? 'selected' : ''}>${f.split(',')[0]}</option>`
        ).join('')}
      </select>
    </div>
  `;
  const $ = (id) => inspector.querySelector('#' + id);
  const wire = (id, prop, parse = v => v) => {
    $(id).addEventListener('input', e => { clip[prop] = parse(e.target.value); emit('inspector'); });
  };
  wire('t-text', 'text');
  wire('t-start', 'start', v => +v);
  wire('t-dur', 'duration', v => Math.max(0.2, +v));
  wire('t-x', 'x', v => +v);
  wire('t-y', 'y', v => +v);
  wire('t-size', 'fontSize', v => Math.max(8, +v));
  wire('t-align', 'align');
  wire('t-color', 'color');
  wire('t-font', 'font');
  $('t-bold').addEventListener('change', e => { clip.bold = e.target.checked; emit('inspector'); });
  $('t-shadow').addEventListener('change', e => { clip.shadow = e.target.checked; emit('inspector'); });
  const updateBg = () => {
    clip.bg = $('t-bg-on').checked ? $('t-bg').value : 'transparent';
    emit('inspector');
  };
  $('t-bg').addEventListener('input', updateBg);
  $('t-bg-on').addEventListener('change', updateBg);
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
