# Cutbackito

Tu versión autohospedable de [cutback.video](https://cutback.video).

Sube N cámaras (cada una con su audio), Cutbackito las **sincroniza** por
cross-correlation de audio, las **transcribe** con Whisper local, detecta
**highlights** automáticos y te deja **editar por chat** usando tu cuenta de
**Claude Code** — sin API key, cubierto por tu plan Pro/Max.

## Stack

- **FastAPI + Jinja2 + JS vanilla** (cero build step)
- **ffmpeg + numpy/scipy** para sync multicam
- **faster-whisper** local (100+ idiomas, sin API externa)
- **Claude Code CLI** (`claude -p`) para el chat editor — usa tu suscripción
  Pro/Max, **no necesita `ANTHROPIC_API_KEY`**
- Empaquetado en Docker, desplegable en cualquier sitio

## Pre-requisitos

1. **Python 3.11+** y **ffmpeg** en el PATH.
2. **Claude Code instalado y logueado**:
   ```bash
   # Instalar (cualquier plataforma)
   npm install -g @anthropic-ai/claude-code
   # o sigue las instrucciones de https://claude.com/claude-code

   claude login        # autentica con tu cuenta Pro/Max
   claude --version    # confirma que está en PATH
   ```

## Quickstart local (Python nativo)

```bash
cd cutbackito
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # edita si quieres pinear modelo o cambiar timeouts

uvicorn app.main:app --reload
# abre http://localhost:8000
```

La primera transcripción descarga el modelo Whisper (`small` por defecto, ~500 MB).

## Quickstart con Docker

El Dockerfile incluye Node.js + Claude Code CLI, pero la **autenticación se
inherita del host** vía un bind-mount de `~/.claude`:

```bash
# Una vez en el host:
npm install -g @anthropic-ai/claude-code
claude login

# Luego:
cd cutbackito
docker compose up --build
# http://localhost:8000
```

En Windows reemplaza `~/.claude` por `%USERPROFILE%\.claude` en
`docker-compose.yml`.

## Despliegue (NO Vercel)

Como el cliente de Claude vive como subprocess, el host de despliegue
necesita poder ejecutar `claude` (Node.js + tu auth). Opciones:

| Plataforma          | Cómo                                                                |
|---------------------|---------------------------------------------------------------------|
| **Tu propio PC / VPS** | Lo más simple. `docker compose up -d` detrás de Caddy/Nginx.    |
| **Hetzner / DigitalOcean / Linode** | Igual: VPS + Docker + bind-mount de `~/.claude`.   |
| **Railway / Fly.io / Render** | Más complicado: necesitarías meter `~/.claude` como secret y configurarlo en startup. Para uso personal, el VPS propio es mejor. |

Variables de entorno relevantes (`.env`):

| Variable | Por defecto | Para qué |
|---|---|---|
| `CLAUDE_MODEL` | _vacío_ (default de Claude Code) | `claude-sonnet-4-6`, `claude-opus-4-7`, etc. |
| `CLAUDE_TIMEOUT_SECONDS` | `300` | Cuánto esperar a `claude -p` |
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cuda` si tienes GPU |
| `WHISPER_COMPUTE_TYPE` | `int8` | `float16` con CUDA |
| `WORKSPACE_DIR` | `./workspace` | Donde se guardan proyectos y exports |
| `MAX_UPLOAD_MB` | `2048` | Tamaño máximo por archivo subido |

## Flujo de uso

1. **+ Nuevo proyecto** en la home.
2. **Sube** tus N cámaras (cada archivo debe tener pista de audio).
3. **Calcular offsets**: FFT cross-correlation contra la primera fuente.
4. **Transcribir**: usa la cámara con mayor confianza de sync.
5. **Highlights** (opcional): heurística rápida sobre transcript + audio.
6. **Editar por chat**: pídele lo que quieras —
   *"dame los 3 momentos más graciosos como verticales 9:16 de 30s con
   captions"*. Claude devuelve un JSON con un EditPlan que se renderiza
   inmediatamente con ffmpeg.
7. Descarga los clips desde la sección **Exports**.

## Arquitectura

```
app/
  config.py           – Settings desde env / .env
  ffmpeg_utils.py     – probe, extract PCM, cut, concat, vertical 9:16
  multicam_sync.py    – FFT cross-correlation, common window
  transcription.py    – wrapper de faster-whisper, SRT
  highlights.py       – heurística audio + transcript
  chat_editor.py      – subprocess a `claude -p`, parser JSON
  exporter.py         – EditPlan → archivos mp4 (vertical o landscape)
  projects.py         – estado JSON por proyecto
  main.py             – endpoints FastAPI + UI
  templates/, static/ – Jinja + CSS/JS vanilla
```

## Por qué subprocess y no la API de Anthropic

La API de Claude (`api.anthropic.com`) se factura aparte de tu suscripción
Pro/Max. Si tu plan ya cubre Claude Code, lo correcto es invocar la CLI
oficial — `claude -p "prompt"` — desde Python como un subprocess. Es
exactamente como si tú escribieras el prompt en una terminal: cuenta contra
tu uso de Claude Code, no contra una cuenta API independiente.

El Agent SDK de Anthropic NO permite usar suscripciones Pro/Max programáticamente
(lo prohíbe explícitamente en sus términos), pero llamar a la CLI desde tu
propia máquina sí está permitido — es uso normal de Claude Code.

## Limitaciones conocidas

- Sync por audio asume audio compartido razonablemente reconocible entre
  cámaras (de cámara o externo). Si una cámara estaba en otra sala, ruido.
- Whisper `small` es buen balance calidad/velocidad. Sube a `medium` o
  `large-v3` si necesitas captions premium.
- El renderer vertical es center-crop simple. Para auto-framing por sujeto
  (estilo Opus AI Reframe) habría que añadir tracking facial.
- El subprocess a `claude -p` tiene cold-start de ~2-3s. Despreciable para
  prompts largos pero notable si haces muchas requests pequeñas.
- Sin multiusuario / auth. Para uso personal o detrás de un proxy.
