# Cutbackito

Tu versión de [cutback.video](https://cutback.video) — autohospedable.

Sube N cámaras (cada una con su audio), Cutbackito las **sincroniza** por
correlación cruzada de audio, las **transcribe** con Whisper, detecta
**highlights** automáticos y te deja **editar por chat** con Claude para
sacar clips verticales tipo OpusClip.

## Stack

- **FastAPI** + Jinja2 (UI sin build step)
- **ffmpeg** + numpy/scipy (sync multicam por FFT cross-correlation)
- **faster-whisper** (transcripción local, 100+ idiomas, sin API externa)
- **Anthropic Claude** (`claude-opus-4-7` por defecto, adaptive thinking +
  prompt caching) para el chat editing
- **HTML/CSS/JS vanilla** — cero build step
- Empaquetado en Docker, desplegable en cualquier sitio (NO Vercel)

## Quickstart local

Necesitas Python 3.11+, ffmpeg en el PATH y (opcional) una API key de Anthropic.

```bash
cd cutbackito
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edita .env y pega tu ANTHROPIC_API_KEY

uvicorn app.main:app --reload
# abre http://localhost:8000
```

La primera transcripción descarga el modelo Whisper (`small` por defecto, ~500 MB).

## Quickstart con Docker

```bash
cp .env.example .env   # añade tu ANTHROPIC_API_KEY
docker compose up --build
# http://localhost:8000
```

## Despliegue (NO Vercel)

Como se construyó con Docker plano, corre en cualquier infra:

| Plataforma     | Cómo                                                                |
|----------------|---------------------------------------------------------------------|
| **Railway**    | Conecta el repo. Detecta `railway.json`. Añade volumen en `/data`.  |
| **Fly.io**     | `fly launch --copy-config` (usa el `fly.toml` incluido).            |
| **Render**     | "New Web Service" → Docker. Disco persistente en `/data`.           |
| **Hetzner / VPS** | `docker compose up -d` detrás de Caddy o Nginx con HTTPS.        |
| **Hugging Face Spaces** | Tipo "Docker". Para demos públicas.                        |

Variables de entorno relevantes:

| Variable | Por defecto | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | _vacío_ | Habilita el chat editor. Sin esto, todo lo demás funciona. |
| `CLAUDE_MODEL` | `claude-opus-4-7` | Cualquier model id válido de Claude |
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cuda` si tienes GPU |
| `WHISPER_COMPUTE_TYPE` | `int8` | `float16` con CUDA |
| `WORKSPACE_DIR` | `./workspace` | Donde se guardan proyectos y exports |
| `MAX_UPLOAD_MB` | `2048` | Tamaño máximo por archivo subido |

## Flujo de uso

1. **+ Nuevo proyecto** en la home.
2. **Sube** tus 3 cámaras (cada archivo debe tener pista de audio — la de la
   cámara o un externo). El audio común es lo que se usa para alinear.
3. Pulsa **Calcular offsets**: Cutbackito genera un PCM mono 8 kHz por
   fuente, hace FFT cross-correlation contra la primera y devuelve el offset
   de cada cámara con su confianza.
4. **Transcribir**: usa la cámara con mayor confianza de sync como
   referencia.
5. **Highlights** (opcional): preview rápido por heurística (energía + risas
   + frases quotables + densidad léxica).
6. **Editar por chat**: pídele a Claude lo que quieras —
   *"dame los 3 momentos más graciosos como verticales 9:16 de 30s con
   captions"*. Claude devuelve un EditPlan estructurado (vía tool use) que se
   renderiza inmediatamente con ffmpeg.
7. Descarga los clips desde la sección **Exports**.

## Arquitectura

```
app/
  config.py           – Settings desde env / .env
  ffmpeg_utils.py     – probe, extract PCM, cut, concat, vertical 9:16
  multicam_sync.py    – FFT cross-correlation, common window
  transcription.py    – wrapper de faster-whisper, SRT
  highlights.py       – heurística audio + transcript
  chat_editor.py      – Claude con system prompt + tool `submit_edit_plan`
  exporter.py         – EditPlan → archivos mp4 (vertical o landscape)
  projects.py         – estado JSON por proyecto
  main.py             – endpoints FastAPI + UI
  templates/, static/ – Jinja + CSS/JS vanilla
```

El **chat editor** usa prompt caching en el contexto pesado (cámaras +
transcripción), así que la segunda iteración cuesta ~10× menos.

## Limitaciones conocidas

- Sync por audio asume un audio compartido razonablemente reconocible entre
  cámaras (audio de cámara, o un audio externo presente en todas las pistas).
  Si una cámara estaba en otra sala, el offset será ruidoso.
- Whisper `small` es buen balance calidad/velocidad pero no perfecto. Sube a
  `medium` o `large-v3` si necesitas captions de mayor calidad.
- El renderer vertical es center-crop simple. Para auto-framing por sujeto
  (estilo Opus AI Reframe) habría que añadir tracking facial.
- No hay multiusuario / auth. Pensado para uso personal o detrás de un proxy.
