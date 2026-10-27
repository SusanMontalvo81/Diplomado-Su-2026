"""CER y WER con la normalización de la Parte 2 (la misma para referencia e hipótesis).

Sobre voz.normalizar (minúsculas, NFC, sin puntuación) agrega tres pasos, decididos antes de calcular
cualquier métrica:
- quita las marcas que no son texto leído ni hablado: [HABLANTE_n], [?], [inaudible];
- números a palabras (19 -> diecinueve), para que "siglo 19" y "siglo diecinueve" no cuenten como error;
- sin tildes ni diacríticos (á -> a, ñ -> n): las referencias manuales no marcan las tildes de forma
  pareja, y una tilde omitida al teclear no es un error de lectura del modelo.
"""
import re
import unicodedata

import jiwer
from num2words import num2words

MARCAS = re.compile(r"\[(?:HABLANTE_\d+|\?|inaudible)\]", re.IGNORECASE)


def normalizar(texto: str) -> str:
    texto = MARCAS.sub(" ", texto or "")
    texto = re.sub(r"\d+", lambda m: f" {num2words(int(m.group()), lang='es')} ", texto)
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def wer(referencias: list[str], hipotesis: list[str]) -> float:
    """Errores de palabra (sustituidas + borradas + insertadas) / palabras de la referencia, sumados sobre todos los casos."""
    return jiwer.wer([normalizar(r) for r in referencias], [normalizar(h) or "∅" for h in hipotesis])


def cer(referencias: list[str], hipotesis: list[str]) -> float:
    """Igual que el WER, pero contando caracteres."""
    return jiwer.cer([normalizar(r) for r in referencias], [normalizar(h) or "∅" for h in hipotesis])
