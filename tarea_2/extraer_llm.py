"""Extrae campos estructurados de los 45 textos con Gemini (Parte 2).

    python extraer_llm.py

Lee los textos publicados (ya seudonimizados) de datos/documentos.csv y datos/transcripciones.csv:
ningún nombre real sale hacia la API. Necesita GEMINI_API_KEY en tarea_2/.env.

Configuración fija: gemini-3.5-flash, temperatura 0, salida JSON con esquema (pydantic). Un campo que
no aparece en el texto debe ir en null. Se envían 3 textos de la misma modalidad por solicitud: la cuota
gratuita es de 20 solicitudes diarias por modelo, y así los 45 textos caben en 15. (El plan inicial era
gemini-3.8-flash con un texto por solicitud; su cuota se agotó a los 13 documentos y esas respuestas
se descartaron para no mezclar configuraciones.)

Cada respuesta se guarda en datos/raw/llm/<id>.json, así que al volver a correrlo solo consulta lo que
falta. Resultado: datos/extraccion_llm.csv con id, modalidad, campos_json, modelo_llm y fecha.
"""
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

AQUI = Path(__file__).resolve().parent
CRUDO = AQUI / "datos" / "raw" / "llm"
MODELO = "gemini-3.5-flash"
LOTE = 3

INSTRUCCIONES = """Eres un asistente de archivo. Recibes varios textos de {que} peruanos, cada uno
precedido por su id (### doc_001). Fueron obtenidos automáticamente con {como}, así que pueden traer
errores de lectura. Devuelve un elemento por texto, con su mismo id, y extrae los campos usando SOLO lo
que dice ese texto (no mezcles información entre textos):
- Si un campo no aparece en el texto, devuélvelo como null. No lo deduzcas ni lo inventes.
- Los nombres de persona ya fueron reemplazados por seudónimos (PERSONA_01...): consérvalos tal cual.
- tema: 2 a 6 palabras. resumen: 1 o 2 oraciones en español.
{extra}"""

EXTRA_DOC = """- emisor: persona o institución que emite o firma el documento, tal como aparece.
- fecha: la fecha del documento tal como aparece escrita (no la conviertas).
- lugar: ciudad o lugar donde se emite el documento.
- monto: cantidad de dinero mencionada con su moneda, tal como aparece; si hay varias, la principal."""

EXTRA_AUDIO = """- Las marcas [HABLANTE_1], [HABLANTE_2]... vienen de una separación automática de voces.
- numero_hablantes: cuántas marcas de hablante distintas aparecen.
- citas_clave: de 1 a 3 frases copiadas literalmente del texto que resuman lo más importante."""


class CamposDocumento(BaseModel):
    id: str
    modalidad: str = Field(description="siempre 'documento'")
    tema: str
    resumen: str
    emisor: str | None
    fecha: str | None
    lugar: str | None
    monto: str | None


class CamposAudio(BaseModel):
    id: str
    modalidad: str = Field(description="siempre 'audio'")
    tema: str
    resumen: str
    numero_hablantes: int | None
    citas_clave: list[str] | None


def pedir(cliente, sistema, textos, esquema, intentos=6):
    config = types.GenerateContentConfig(system_instruction=sistema, temperature=0,
                                         response_mime_type="application/json", response_schema=list[esquema])
    contenido = "\n\n".join(f"### {id_}\n{texto}" for id_, texto in textos)
    for i in range(intentos):
        try:
            return cliente.models.generate_content(model=MODELO, contents=contenido, config=config).parsed
        except Exception as e:  # 503 (alta demanda) o 429 por minuto: esperar y reintentar
            if i == intentos - 1 or "PerDay" in str(e) or not any(c in str(e) for c in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                raise
            time.sleep(20 * (i + 1))


if __name__ == "__main__":
    clave = next(l.split("=", 1)[1].strip() for l in (AQUI / ".env").read_text().splitlines()
                 if l.startswith("GEMINI_API_KEY="))
    cliente = genai.Client(api_key=clave)
    CRUDO.mkdir(parents=True, exist_ok=True)
    docs = pd.read_csv(AQUI / "datos" / "documentos.csv")
    clips = pd.read_csv(AQUI / "datos" / "transcripciones.csv")
    grupos = [("documento", list(zip(docs["id"], docs["texto_ocr"].fillna(""))), CamposDocumento,
               INSTRUCCIONES.format(que="documentos (impresos, fotos y manuscritos)", como="OCR", extra=EXTRA_DOC)),
              ("audio", list(zip(clips["id"], clips["texto_asr"].fillna(""))), CamposAudio,
               INSTRUCCIONES.format(que="audios (entrevistas y clips)", como="reconocimiento de voz", extra=EXTRA_AUDIO))]
    for modalidad, textos, esquema, sistema in grupos:
        pendientes = [t for t in textos if not (CRUDO / f"{t[0]}.json").exists()]
        for k in range(0, len(pendientes), LOTE):
            lote = pendientes[k:k + LOTE]
            respuesta = {c.id: c for c in pedir(cliente, sistema, lote, esquema)}
            for id_, _ in lote:
                if id_ not in respuesta:
                    print(id_, "sin respuesta: se reintenta en la próxima ejecución", flush=True)
                    continue
                campos = respuesta[id_].model_dump(exclude={"id"})
                (CRUDO / f"{id_}.json").write_text(json.dumps({"id": id_, "modalidad": modalidad, "modelo_llm": MODELO,
                                                               "fecha": date.today().isoformat(), "campos": campos},
                                                              ensure_ascii=False, indent=1), encoding="utf-8")
            print(", ".join(i for i, _ in lote), "ok", flush=True)
            time.sleep(5)  # pausa entre solicitudes (cuota gratuita por minuto)
    filas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CRUDO.glob("*.json"))]
    pd.DataFrame([{"id": f["id"], "modalidad": f["modalidad"], "campos_json": json.dumps(f["campos"], ensure_ascii=False),
                   "modelo_llm": f["modelo_llm"], "fecha": f["fecha"]} for f in filas]).to_csv(
        AQUI / "datos" / "extraccion_llm.csv", index=False)
    print(f"listo: datos/extraccion_llm.csv ({len(filas)} filas)")
