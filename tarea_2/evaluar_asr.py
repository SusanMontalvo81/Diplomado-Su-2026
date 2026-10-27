"""Transcribe la muestra de evaluación con un modelo ASR y mide su latencia (Parte 2).

    python evaluar_asr.py faster-whisper-small clip_001,clip_005,...
    python evaluar_asr.py qwen3-asr-0.6b clip_001,clip_005,...

Cada modelo corre en su propio proceso: en Mac Intel, CTranslate2 (faster-whisper) y torch en el
mismo proceso hacen fallar en silencio las multiplicaciones de matrices (ver ner_personas.py).

Configuración fija, decidida antes de ver métricas: idioma español, VAD Silero, CPU, sin prompt de
contexto y sin diarización (el WER no usa hablantes). faster-whisper corta con su propio VAD; los
demás modelos reciben los tramos de voz.tramos_de_voz (máx. 12 s). La latencia se mide solo sobre
la transcripción (sin la carga del modelo) y el factor de tiempo real es segundos / duración.

Guarda un JSON por clip en datos/raw/audio/eval/<modelo>/ y el resumen en resumen.csv.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

import voz

AQUI = Path(__file__).resolve().parent
AUDIO = AQUI / "datos" / "raw" / "audio"

if __name__ == "__main__":
    clave, ids = sys.argv[1], sys.argv[2].split(",")
    carpeta = AUDIO / "eval" / clave
    carpeta.mkdir(parents=True, exist_ok=True)
    pendientes = [c for c in ids if not (carpeta / f"{c}.json").exists()]
    if pendientes:
        t = voz.Transcriptor(clave, device="cpu")
        print(f"{t} cargado en {t.segundos_carga:.0f} s", flush=True)
        for cid in pendientes:
            audio = voz.cargar_audio(AUDIO / f"{cid}.wav")
            t0 = time.perf_counter()
            segs = t.segmentos(audio, idioma="es")
            seg = time.perf_counter() - t0
            dur = len(audio) / voz.SR
            fila = {"id": cid, "modelo": voz.MODELOS[clave]["nombre"], "duracion_seg": round(dur, 1),
                    "segundos": round(seg, 1), "rtf": round(seg / dur, 3),
                    "texto": " ".join(s.texto for s in segs),
                    "segmentos": [[s.inicio, s.fin, s.texto] for s in segs]}
            (carpeta / f"{cid}.json").write_text(json.dumps(fila, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{cid}  {dur:6.1f} s audio  {seg:6.1f} s  RTF {seg / dur:.2f}", flush=True)
    filas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(carpeta.glob("clip_*.json"))]
    pd.DataFrame(filas).drop(columns="segmentos").to_csv(carpeta / "resumen.csv", index=False)
    print("listo:", carpeta / "resumen.csv", flush=True)
