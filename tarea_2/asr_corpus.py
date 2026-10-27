"""Transcribe y diariza los clips del corpus de audio (Parte 1).

    python asr_corpus.py

Para cada datos/raw/audio/clip_XXX.wav:
1. faster-whisper large-v3-turbo (int8, CPU), idioma fijado en español y filtro VAD (Silero),
   para no transcribir silencio ni música (la causa típica de las alucinaciones de Whisper).
2. Diarización con huellas de voz WeSpeaker + clustering (voz.diarizar, umbral 0,7): da el número
   de hablantes y marca cada segmento con H1, H2...
3. Exporta CSV (segmentos), SRT (subtítulos) y TXT (turnos) en datos/raw/audio/salidas/.

Los resultados se guardan clip por clip: si se corta, al volver a correrlo sigue donde quedó.
El resumen (texto, tiempos, hablantes) queda en datos/raw/audio/salidas/resumen_asr.csv.
"""
import json
import time
from pathlib import Path

import pandas as pd

import voz

AQUI = Path(__file__).resolve().parent
AUDIO = AQUI / "datos" / "raw" / "audio"
SALIDAS = AUDIO / "salidas"
MODELO = "faster-whisper"  # large-v3-turbo en CTranslate2
CONFIG = "faster-whisper large-v3-turbo (int8, CPU, language=es, VAD on, beam=5) + diarización WeSpeaker (umbral 0,7)"


def procesar(t, ruta):
    audio = voz.cargar_audio(ruta)
    t0 = time.perf_counter()
    segs = t.segmentos(audio, idioma="es")
    seg_asr = time.perf_counter() - t0
    t0 = time.perf_counter()
    segs = voz.diarizar(audio, segs) if segs else []
    seg_diar = time.perf_counter() - t0
    cid = ruta.stem
    voz.a_tabla(segs).to_csv(SALIDAS / f"{cid}.csv", index=False)
    (SALIDAS / f"{cid}.srt").write_text(voz.a_srt(segs), encoding="utf-8")
    (SALIDAS / f"{cid}.txt").write_text(voz.a_texto(segs), encoding="utf-8")
    return {"id": cid, "duracion_seg": round(len(audio) / voz.SR, 1), "n_segmentos": len(segs),
            "n_hablantes": len({s.hablante for s in segs}),
            "texto_asr": " ".join(f"[{s.hablante}] {s.texto}" for s in segs),
            "segundos_asr": round(seg_asr, 1), "segundos_diarizacion": round(seg_diar, 1),
            "modelo_asr": CONFIG}


if __name__ == "__main__":
    SALIDAS.mkdir(parents=True, exist_ok=True)
    hechos = SALIDAS / "resumen_asr.jsonl"
    listos = {json.loads(l)["id"] for l in hechos.read_text().splitlines()} if hechos.exists() else set()
    clips = sorted(p for p in AUDIO.glob("clip_*.wav") if p.stem not in listos)
    print(f"{len(listos)} clips ya transcritos, faltan {len(clips)}", flush=True)
    if clips:
        t = voz.Transcriptor(MODELO)
        print(f"{t} cargado en {t.segundos_carga:.0f} s", flush=True)
        for ruta in clips:
            fila = procesar(t, ruta)
            with hechos.open("a", encoding="utf-8") as f:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            print(f"{fila['id']}  {fila['duracion_seg']:6.1f} s audio  {fila['segundos_asr']:6.1f} s ASR  "
                  f"RTF {fila['segundos_asr'] / fila['duracion_seg']:.2f}  {fila['n_hablantes']} hablantes", flush=True)
    filas = [json.loads(l) for l in hechos.read_text().splitlines()]
    pd.DataFrame(filas).sort_values("id").to_csv(SALIDAS / "resumen_asr.csv", index=False)
    print("listo:", SALIDAS / "resumen_asr.csv")
