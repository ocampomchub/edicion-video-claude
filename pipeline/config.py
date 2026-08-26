"""Constantes compartidas por todo el pipeline. Todos los umbrales vienen del spec de edición."""

from pathlib import Path

# ---- Rutas del proyecto (relativas a la raíz del pipeline) ----
ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = ROOT / "work"
OUTPUT_DIR = ROOT / "output"
LUTS_DIR = ROOT / "luts"
SFX_DIR = ROOT / "sfx"
MUSIC_DIR = ROOT / "music"
REMOTION_DIR = ROOT / "remotion"

TRANSCRIPT_PATH = WORK_DIR / "transcript.json"
CUTS_PATH = WORK_DIR / "cuts.json"
CLEAN_VIDEO_PATH = WORK_DIR / "clean.mp4"
RETENTION_MAP_PATH = WORK_DIR / "retention_map.json"
GRADE_LUT_PATH = LUTS_DIR / "grade.cube"
GRADE_PREVIEW_PATH = WORK_DIR / "grade_preview.png"
GRADED_VIDEO_PATH = WORK_DIR / "graded.mp4"
CAMERA_MOVES_PATH = WORK_DIR / "camera_moves.json"
MOVED_VIDEO_PATH = WORK_DIR / "moved.mp4"
TRANSITIONS_PATH = WORK_DIR / "transitions.json"
ASSEMBLED_VIDEO_PATH = WORK_DIR / "assembled.mp4"
SFX_TIMELINE_PATH = WORK_DIR / "sfx_timeline.json"
MUSIC_PROMPT_PATH = WORK_DIR / "music_prompt.json"
SUBTITLES_SCHEDULE_PATH = WORK_DIR / "subtitles_schedule.json"
GRAPHICS_SCHEDULE_PATH = WORK_DIR / "graphics_schedule.json"
SUBTITLES_SCHEDULE_FINAL_PATH = WORK_DIR / "subtitles_schedule.final.json"
GRAPHICS_SCHEDULE_FINAL_PATH = WORK_DIR / "graphics_schedule.final.json"
SUBTITLES_OVERLAY_PATH = WORK_DIR / "subtitles_overlay.mov"
GRAPHICS_OVERLAY_PATH = WORK_DIR / "graphics_overlay.mov"
MIXED_AUDIO_PATH = WORK_DIR / "mixed_audio.wav"
VOICE_ONLY_PATH = WORK_DIR / "voice_only.wav"
SFX_BED_PATH = WORK_DIR / "sfx_bed.wav"
FINAL_VIDEO_PATH = WORK_DIR / "final_composited.mp4"

# ---- Salida final ----
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_FPS = 30
OUTPUT_VCODEC = "libx264"
OUTPUT_ACODEC = "aac"
OUTPUT_ABITRATE = "192k"

# ---- PASO 2: corte de silencios ----
SILENCE_THRESHOLD_DB = -35  # umbral para ffmpeg silencedetect
MIN_SILENCE_DUR = 0.5  # s: por debajo de esto no se considera "silencio" a cortar
PAD_BEFORE = 0.15  # s de aire antes de cada frase
PAD_AFTER = 0.15  # s de aire después de cada frase
MAX_KEPT_SILENCE = 0.7  # s: tope al que se recorta cualquier silencio que se conserve
FILLERS = {"eh", "em", "ehm", "este", "o sea", "bueno"}
REPETITION_OVERLAP_THRESHOLD = 0.7  # solape de palabras entre frases consecutivas
FALSE_START_MAX_WORDS = 4  # frase sin verbo + corta -> candidata a falso arranque
FALSE_START_MAX_GAP = 1.5  # s entre falso arranque y reinicio de la misma idea
MIN_PHRASES_BETWEEN_CUTS = 2  # límite crítico: no cortar más de 1 vez cada 2 frases

# ---- PASO 3: mapa de retención ----
HOOK_DURATION = 3.0  # s
CTA_DURATION = 3.0  # s
KEY_LINE_MIN_SCORE = 2
TOPIC_SHIFT_MARKERS = [
    "por otro lado", "ahora bien", "cambiando de tema", "sin embargo",
    "pero fíjate", "eso sí", "en cambio", "dicho esto", "pasemos a",
    "hablemos de", "otra cosa", "por su parte",
]
PUNCHLINE_MARKERS = [
    "increíble", "una locura", "flipante", "brutal", "impresionante",
    "y aquí viene lo bueno", "lo que nadie te dice", "la sorpresa es",
    "resulta que", "al final",
]
LIST_MARKERS = [
    "primero", "segundo", "tercero", "cuarto", "quinto",
    "el primer paso", "el segundo paso", "número uno", "número dos",
    "en primer lugar", "en segundo lugar", "por último",
]
THESIS_MARKERS = [
    "te voy a enseñar", "te voy a contar", "la clave está",
    "el problema es", "lo que tienes que saber", "esto cambia todo",
    "el secreto es", "la razón por la que",
]
# Marcas/herramientas/conceptos conocidos que SIEMPRE cuentan como ENTITIES,
# aunque no vayan en mayúscula en la transcripción. Edítala por proyecto.
KNOWN_ENTITIES: set[str] = set()

# ---- PASO 4: color ----
LUT_SIZE = 33
BLACK_LIFT = 0.06
SELECTIVE_SATURATION_BOOST = 0.15  # +15% en magenta/rojo/morado
SKIN_HUE_RANGE = (15, 45)  # grados, excluido del boost de saturación
BOOSTED_HUE_RANGES = [(280, 345), (345, 360), (0, 15)]  # magenta/rojo/morado (wrap 360->0)
NOISE_STRENGTH = 6
# Ángulo del filtro vignette de ffmpeg: cuanto MAYOR el ángulo, más suave el viñeteo
# (el default de ffmpeg es PI/5 ~0.628). Usamos algo mayor para que sea "muy suave".
VIGNETTE_ANGLE = "PI/2.5"

# ---- PASO 5: punch-ins ----
PUNCH_ZOOM_MIN = 1.08
PUNCH_ZOOM_MAX = 1.12
PUNCH_RAMP_DURATION = 0.4  # s, dentro del rango 0.3-0.5
MIN_SECONDS_BETWEEN_PUNCHES = 6.0
LATERAL_REFRAME_SHIFT = 0.04  # 4% en TOPIC_SHIFTS

# ---- PASO 6: subtítulos ----
SUBTITLE_FONT = "Playfair Display"
SUBTITLE_WEIGHT = 600
SUBTITLE_COLOR = "#F2B01E"
SUBTITLE_EMPHASIS_COLOR = "#F4EDE2"
SUBTITLE_SHADOW_OPACITY = 0.4
SUBTITLE_WORDS_MIN = 2
SUBTITLE_WORDS_MAX = 4
SUBTITLE_BOTTOM_SAFE_PCT = 0.22
SUBTITLE_ENTRY_RISE_PX = 12
SUBTITLE_ENTRY_FRAMES = 6
SUBTITLE_EMPHASIS_SCALE = 1.15
MIN_SECONDS_BETWEEN_EMPHASIS = 4.0

# ---- PASO 7: gráficos ----
GRAPHIC_PALETTE = {
    "amber": "#F2B01E",
    "malva": "#9B7EC8",
    "magenta": "#C4384F",
    "crema": "#F4EDE2",
}
GRAPHICS_MIN_PER_MIN = 4
GRAPHICS_MAX_PER_MIN = 8
NUMBER_COUNT_DURATION = 0.6
ENTITY_CHIP_DURATION = 2.5

# ---- PASO 8: transiciones ----
TRANSITION_WEIGHTS = {"cut": 0.70, "whip_pan": 0.20, "fade": 0.10}
WHIP_PAN_FRAMES = (4, 6)
FADE_FRAMES = 6
SHOT_SIMILARITY_THRESHOLD = 0.94  # correlación de histograma -> planos "casi idénticos"
BRIDGE_DURATION = 1.0

# ---- PASO 9: SFX ----
SFX_SAMPLE_RATE = 48000
CUT_SFX_VOLUME_RATIO = 0.55  # respecto al pico de voz, nunca por encima
MAX_IMPACTS_TOTAL = 2
MAX_SFX_SHORT_VIDEO = 8  # si el vídeo dura <30s

# ---- PASO 10: música ----
MUSICGEN_SEGMENT_SECONDS = 30
MUSICGEN_CROSSFADE = 2.0
MUSIC_DEFAULT_PROMPT = (
    "warm lo-fi instrumental, soft Rhodes piano, muted drums, "
    "vinyl texture, 90 BPM, no vocals"
)

# ---- PASO 11: mezcla ----
VOICE_LUFS = -14.0
VOICE_TRUE_PEAK = -1.5
MUSIC_LUFS = -26.0
SFX_LUFS = -20.0
MUSIC_FADE_IN = 1.5
MUSIC_FADE_OUT = 2.0
MASTER_LUFS = -14.0
MASTER_TRUE_PEAK = -1.0

# ---- PASO criterio_de_exito: verificación ----
MAX_SILENCE_FINAL = 0.7
CADENCE_MIN = 2.0
CADENCE_MAX = 4.0
MAX_GAP_NO_CHANGE = 4.0
SUBTITLE_SYNC_TOLERANCE = 0.1
LUFS_TOLERANCE = 0.5
