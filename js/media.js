import { state, uid, emit } from './state.js';

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const mediaList = document.getElementById('media-list');

export function initMedia() {
  fileInput.addEventListener('change', e => handleFiles(e.target.files));

  ['dragenter', 'dragover'].forEach(evt =>
    dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach(evt =>
    dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove('drag'); }));
  dropzone.addEventListener('drop', e => handleFiles(e.dataTransfer.files));

  renderMediaList();
}

async function handleFiles(files) {
  for (const file of files) {
    if (!file.type.startsWith('video/')) continue;
    const item = await loadVideoFile(file);
    state.media.push(item);
  }
  renderMediaList();
  emit('media');
}

function loadVideoFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    video.preload = 'auto';
    video.muted = true;
    video.src = url;
    video.crossOrigin = 'anonymous';
    video.addEventListener('loadedmetadata', async () => {
      const duration = isFinite(video.duration) ? video.duration : await probeDuration(video);
      const thumb = await snapshotThumb(video);
      resolve({
        id: uid('m'),
        name: file.name,
        file,
        url,
        duration,
        width: video.videoWidth,
        height: video.videoHeight,
        video,
        thumb,
      });
    });
    video.addEventListener('error', () => reject(new Error('No se pudo cargar ' + file.name)));
  });
}

// Some webm/mkv files report Infinity duration until you seek past it.
function probeDuration(video) {
  return new Promise(resolve => {
    const onUpdate = () => {
      if (isFinite(video.duration)) {
        video.removeEventListener('durationchange', onUpdate);
        video.currentTime = 0;
        resolve(video.duration);
      }
    };
    video.addEventListener('durationchange', onUpdate);
    video.currentTime = 1e6;
  });
}

function snapshotThumb(video) {
  return new Promise(resolve => {
    const grab = () => {
      const c = document.createElement('canvas');
      const ratio = video.videoWidth / video.videoHeight || 16 / 9;
      c.width = 112;
      c.height = Math.round(112 / ratio);
      c.getContext('2d').drawImage(video, 0, 0, c.width, c.height);
      resolve(c.toDataURL('image/jpeg', 0.7));
    };
    if (video.readyState >= 2) {
      video.currentTime = Math.min(0.1, (video.duration || 1) * 0.1);
      video.addEventListener('seeked', grab, { once: true });
    } else {
      video.addEventListener('loadeddata', () => {
        video.currentTime = Math.min(0.1, (video.duration || 1) * 0.1);
        video.addEventListener('seeked', grab, { once: true });
      }, { once: true });
    }
  });
}

function renderMediaList() {
  mediaList.innerHTML = '';
  for (const m of state.media) {
    const li = document.createElement('li');
    li.className = 'media-item';
    li.draggable = true;
    li.dataset.mediaId = m.id;
    li.innerHTML = `
      <img class="media-thumb" src="${m.thumb}" alt="" />
      <div class="media-info">
        <div class="media-name" title="${m.name}">${m.name}</div>
        <div class="media-meta">${formatDur(m.duration)} · ${m.width}×${m.height}</div>
      </div>
    `;
    li.addEventListener('dragstart', e => {
      li.classList.add('dragging');
      e.dataTransfer.setData('application/x-clipforge-media', m.id);
      e.dataTransfer.effectAllowed = 'copy';
    });
    li.addEventListener('dragend', () => li.classList.remove('dragging'));
    li.addEventListener('dblclick', () => addMediaToTimeline(m.id));
    mediaList.appendChild(li);
  }
}

export function addMediaToTimeline(mediaId, atTime) {
  const m = state.media.find(x => x.id === mediaId);
  if (!m) return;
  const start = atTime ?? state.tracks.video.reduce((acc, c) => Math.max(acc, c.start + (c.out - c.in)), 0);
  const clip = {
    id: uid('vc'),
    type: 'video',
    mediaId,
    start,
    in: 0,
    out: m.duration,
  };
  state.tracks.video.push(clip);
  state.tracks.video.sort((a, b) => a.start - b.start);
  state.selectedId = clip.id;
  emit('timeline');
}

function formatDur(s) {
  if (!isFinite(s)) return '?';
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60).toString().padStart(2, '0');
  return `${m}:${sec}`;
}

export { renderMediaList };
