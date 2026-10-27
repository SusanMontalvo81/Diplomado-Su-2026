"""Detecta nombres de persona (NER) en textos, en un proceso aparte.

    python ner_personas.py entrada.json salida.json

entrada.json: {"id": "texto", ...}  ->  salida.json: {"id": ["nombre", ...], ...}

Va en su propio proceso porque, en Mac Intel, si faster-whisper (CTranslate2) ya se cargó en el
mismo proceso, las multiplicaciones de matrices de torch fallan ("Intel MKL ERROR ... SGEMM") y el
modelo devuelve etiquetas sin sentido sin lanzar ningún error.

Modelo: mrm8488/bert-spanish-cased-finetuned-ner (BETO afinado en CoNLL-2002). Se guardan las
entidades PER con confianza >= 0,8 que parecen un nombre (ver es_nombre).
"""
import json
import re
import sys

from transformers import pipeline


def bloques(texto, maximo=500):
    # corta en espacios para no partir nombres y no pasar los 512 tokens de BERT
    actual = ""
    for palabra in texto.split():
        if len(actual) + len(palabra) + 1 > maximo:
            yield actual
            actual = ""
        actual += " " + palabra
    if actual.strip():
        yield actual


def es_nombre(texto):
    """Descarta restos que no pueden ser un nombre: sin mayúscula inicial, con dígitos o símbolos,
    o una sola palabra de 3 letras o menos (con la comparación difusa reemplazarían palabras comunes)."""
    if not re.fullmatch(r"[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚáéíóúÑñÜü.\- ]*", texto) or re.search(r"\d", texto):
        return False
    return len(texto.split()) > 1 or len(texto) > 3


if __name__ == "__main__":
    # "first": une las sub-palabras de BERT (Qui ##s ##pe -> Quispe) antes de etiquetar
    ner = pipeline("ner", model="mrm8488/bert-spanish-cased-finetuned-ner", aggregation_strategy="first")
    textos = json.load(open(sys.argv[1], encoding="utf-8"))
    salida = {i: [e["word"].strip() for b in bloques(t or "") for e in ner(b)
                  if e["entity_group"] == "PER" and e["score"] >= 0.8 and es_nombre(e["word"].strip())]
              for i, t in textos.items()}
    json.dump(salida, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
