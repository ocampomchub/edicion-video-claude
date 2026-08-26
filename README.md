# edicion-video-claude — pipeline de edición vertical de retención

Pipeline de 12 pasos para editar vídeo vertical (Reels/TikTok/Shorts) al estilo de
alta retención: corte de silencios, mapa de retención, color, punch-ins, subtítulos
y gráficos quemados (Remotion), transiciones, SFX y música sintetizados localmente,
mezcla de audio y export final — con verificación automática de los 7 checks del
criterio de éxito.

**Este código no se ejecutó en el entorno donde se escribió** (contenedor Linux sin
Mac/MLX, sin `ffmpeg`, sin vídeo real). Está escrito para correr en tu Mac con
Apple Silicon, con el pipeline instalado en `~/video-pipeline` (o donde clones este
repo). Cada módulo se probó de forma aislada donde fue posible (lógica de cortes,
mapa de retención, síntesis DSP de los 6 SFX, generación de la LUT) pero **el flujo
completo con `ffmpeg`/`mlx-whisper`/`musicgen-mlx`/Remotion reales necesita tu
verificación en máquina** antes de confiar en él para un vídeo real.

## Instalación (macOS, Apple Silicon)

```bash
# Python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# ffmpeg y sox (SFX se sintetizan con numpy, pero ffmpeg hace falta para todo lo demás)
brew install ffmpeg sox

# Remotion (subtítulos y gráficos quemados)
cd remotion && npm install && cd ..
```

`mlx-whisper` y `musicgen-mlx` (PASOS 1 y 10) requieren Apple Silicon. Si tu versión
de `musicgen-mlx` expone una API distinta a la que asume
`pipeline/musicgen_backend.py`, ajusta esa función — está documentado ahí mismo.

## Uso

```bash
python -m pipeline.cli init --input /ruta/al/video.mp4 --platform Reels
python -m pipeline.cli run          # corre hasta el próximo checkpoint
```

El pipeline PARA (checkpoints obligatorios) al terminar los PASOS 2, 3, 4 y 10, y
pide una confirmación explícita (`run --force`) antes del render final del PASO 12.
Revisa la tabla/preview que imprime cada checkpoint y vuelve a correr `run` para
continuar. En el checkpoint del PASO 10 (música), antes de continuar elige variante:

```bash
python -m pipeline.cli choose-music a   # o b
python -m pipeline.cli run
```

`python -m pipeline.cli status` muestra en qué paso vas. Los pasos individuales
también se pueden re-ejecutar llamando directamente a su módulo
(`python -m pipeline.step4_color ...` no existe como CLI propio; para debug, usa un
REPL e importa `pipeline.stepN_xxx` directamente — cada paso es una función `run()`
independiente).

## Estructura

```
pipeline/            orquestador + los 12 pasos (Python)
  config.py           todas las constantes del spec (umbrales, colores, timings)
  cli.py               orquestador con checkpoints
  step1_transcribe.py  ffmpeg -> WAV 16k mono -> mlx-whisper (word timestamps)
  step2_cuts.py        silencios/muletillas/repeticiones/falsos arranques -> clean.mp4
  step3_retention_map.py  HOOK/KEY_LINES/NUMBERS/LISTS/ENTITIES/TOPIC_SHIFTS/...
  step4_color.py       LUT 33pt generada por código + grano + viñeta
  step5_punchins.py    punch-ins (rostro) + reencuadres laterales, vía zoompan
  step6_subtitles.py   scheduler de tarjetas de subtítulo (Remotion las renderiza)
  step7_graphics.py    scheduler de gráficos (Remotion los renderiza)
  step8_transitions.py tipo de transición por corte + puentes en planos idénticos
  step9_sfx.py          síntesis de los 6 SFX (numpy) + colocación en la timeline
  step10_music.py       prompt de MusicGen desde el tono + 2 variantes
  step11_mix.py          voz/música(sidechain)/SFX -> máster -14 LUFS
  step12_export.py       composición final + render a specs
  verify.py               los 7 checks del criterio de éxito
  dsp.py, timeline.py, text_utils.py, models.py, utils.py   utilidades compartidas
remotion/             proyecto Remotion: subtítulos y gráficos quemados (con alfa)
sfx/, music/, luts/    librerías generadas (no se versionan, ver .gitignore)
work/, output/         artefactos por corrida y vídeo final
```

## Decisiones de implementación (documentadas para que las ajustes)

- **SFX con numpy, no con `sox`/`ffmpeg` encadenados.** El spec pide sintetizarlos
  con sox y ffmpeg; en su lugar se sintetizan con DSP en numpy (ruido rosa, un
  state-variable filter para los barridos de band-pass, envolventes exponenciales)
  y se escriben directamente a WAV. Da control exacto sobre las frecuencias y
  envolventes del spec, sin descargar nada de internet. Si prefieres la cadena
  real de sox/ffmpeg, `pipeline/dsp.py` es el único lugar a tocar.
- **Bridges y timeline con desplazamientos.** Cuando el PASO 8 detecta dos planos
  casi idénticos e inserta un puente de 1s, el resto de artefactos (subtítulos,
  gráficos, SFX) se calcularon contra la línea de tiempo *previa* al puente.
  `pipeline/timeline.py` traduce esos timestamps sumando los desplazamientos
  registrados en `work/transitions.json` antes de renderizar/colocar nada en la
  línea de tiempo final.
- **Detección de rostro opcional.** Si `opencv-python-headless` no está instalado,
  los punch-ins usan un encuadre por defecto (centro, 38% desde arriba) en vez de
  fallar.
- **`musicgen-mlx`**: la interfaz exacta del paquete varía; `musicgen_backend.py`
  prueba varias convenciones de API y cae a CLI si existe. Ajusta esa función a tu
  instalación si no coincide.

## Reglas críticas (heredadas del spec, no las relajes)

- Nunca se sobrescribe ni se borra el vídeo de entrada.
- El pipeline no toca nada fuera de este directorio y la ruta del vídeo de entrada.
- Nunca se descarga audio/música/SFX de internet — todo se sintetiza o genera
  localmente (`pipeline/dsp.py`, `musicgen_backend.py`).
- Si un filtro de ffmpeg falla, se propaga el comando exacto y el stderr
  (`pipeline/utils.py::FFmpegError`) — el pipeline nunca improvisa un filtro
  alternativo en silencio.
