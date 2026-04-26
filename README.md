# ClipForge

Editor de video minimalista en el navegador, inspirado en la edición básica de Premiere Pro. Enfocado solo en **video + texto** (sin color grading ni mezcla de audio).

## Características

- **Importar videos** por arrastre o desde el botón Importar.
- **Línea de tiempo** con dos pistas: video y texto.
- **Edición**: arrastrar para reordenar, recortar desde los bordes, **cortar (S)** en el playhead, **borrar (Supr)**.
- **Texto** con tamaño, color, fondo, alineación, fuente, sombra y negrita; posicionable en porcentajes.
- **Preview** en canvas con reproducción en tiempo real (Espacio para play/pause; flechas para mover frame a frame).
- **Exportar** a `.webm` (VP9/VP8) usando `MediaRecorder` directamente sobre el canvas.

## Cómo correrlo

```bash
python3 server.py
# abre http://localhost:8000
```

(Necesita servirse por HTTP, no `file://`, para que funcionen los blob URLs y `MediaRecorder`.)

## Atajos

| Tecla | Acción |
| --- | --- |
| Espacio | Play / Pause |
| S | Cortar clip(s) en el playhead |
| Supr / ⌫ | Borrar clip seleccionado |
| ← / → | Mover 1 frame atrás/adelante (Shift = 1 s) |

## Limitaciones conocidas

- Exporta `.webm` (no `.mp4`) porque depende de `MediaRecorder`. Para MP4, conviértelo después con FFmpeg: `ffmpeg -i export.webm -c:v libx264 export.mp4`.
- El export sin audio (intencional — el alcance es solo video + texto).
- Solo una pista de video y una de texto en este MVP.
- Probado en Chrome/Edge recientes; Firefox debería funcionar pero `MediaRecorder` puede variar.

## Arquitectura

```
index.html         shell + layout
css/style.css      estilos del editor
js/app.js          bootstrap + atajos
js/state.js        estado global + pub/sub
js/media.js        importación + bandeja de medios
js/timeline.js     pistas, regla, drag/resize/split
js/preview.js     compositor canvas + playback
js/inspector.js    panel de propiedades del clip
js/text.js         creación de clips de texto
js/export.js       render frame-a-frame + MediaRecorder
server.py          servidor estático local
```
