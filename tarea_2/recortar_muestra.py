"""Recorta la parte superior de los 10 documentos de evaluación (Parte 2).

    .venv-ocr/bin/python recortar_muestra.py

La transcripción manual de páginas completas (~2 400 palabras) no era viable, así que se evalúa un
fragmento fijo de cada documento: desde arriba hasta ~70 palabras, estimadas con la cantidad de palabras
que dio el OCR de la Parte 1 (solo se usa el tamaño, no el contenido). Los documentos con menos de
90 palabras van completos. Para no partir una línea, el corte se mueve a la fila más clara (menos tinta)
dentro de ±6 % de la altura alrededor del punto calculado.

En 4 páginas esa estimación falla (títulos grandes o márgenes amplios ocupan altura sin aportar palabras),
así que el corte se eligió a mano mirando solo la imagen, en un espacio entre líneas (CORTES_MANUALES,
fracción de la altura; luego se ajusta a la fila más clara dentro de ±0,5 %):
- doc_004: título y primer párrafo de la presentación;
- doc_018 y doc_019: cabecera del periódico y primeras líneas de las dos columnas;
- doc_015: las 9 primeras líneas del asiento manuscrito.

Los 3 OCR se vuelven a correr sobre estos recortes (ocr_corpus.py --recortes) y la referencia manual
transcribe exactamente el recorte. Salida: datos/raw/documentos/recortes/<id>.png y recortes.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

AQUI = Path(__file__).resolve().parent
DOCS = AQUI / "datos" / "raw" / "documentos"
MUESTRA = ["doc_001", "doc_002", "doc_004", "doc_018", "doc_019", "doc_020", "doc_009", "doc_015", "doc_016", "doc_017"]
OBJETIVO, MINIMO = 70, 90
CORTES_MANUALES = {"doc_004": 0.342, "doc_018": 0.448, "doc_019": 0.385, "doc_015": 0.226}

if __name__ == "__main__":
    salida = DOCS / "recortes"
    salida.mkdir(exist_ok=True)
    inv = pd.read_csv(DOCS / "inventario.csv").set_index("id")
    palabras = pd.read_csv(AQUI / "datos" / "documentos.csv").set_index("id")["texto_ocr"].str.split().str.len()
    filas = []
    for i in MUESTRA:
        im = Image.open(AQUI / inv.loc[i, "archivo"]).convert("RGB")
        alto = im.height
        if palabras[i] < MINIMO:
            corte = alto
        else:
            gris = np.asarray(im.convert("L"), float)
            tinta = (gris < gris.mean() - 2 * gris.std() / 3).mean(axis=1)  # proporción de píxeles oscuros por fila
            con_texto = np.flatnonzero(tinta > 0.01)
            arriba, abajo = con_texto[0], con_texto[-1]
            if i in CORTES_MANUALES:
                meta, v = int(alto * CORTES_MANUALES[i]), int(alto * 0.005)
            else:
                meta, v = int(arriba + (abajo - arriba) * OBJETIVO / palabras[i]), int(alto * 0.06)
            suave = np.convolve(tinta, np.ones(9) / 9, mode="same")
            corte = meta - v + int(np.argmin(suave[meta - v:meta + v]))
        im.crop((0, 0, im.width, corte)).save(salida / f"{i}.png")
        filas.append({"id": i, "tipo": inv.loc[i, "tipo"], "palabras_pagina_estimadas": int(palabras[i]),
                      "alto_px": alto, "corte_px": corte, "fraccion": round(corte / alto, 3)})
        print(f"{i}  {inv.loc[i, 'tipo']:10s} {palabras[i]:4d} palabras  corte {corte:5d}/{alto} px ({corte / alto:.0%})")
    pd.DataFrame(filas).to_csv(salida / "recortes.csv", index=False)
