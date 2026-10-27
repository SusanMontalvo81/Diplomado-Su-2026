"""OCR de los 25 documentos con PaddleOCR (Parte 1).

    .venv-ocr/bin/python ocr_corpus.py [--modelo paddle|tesseract] [--ids doc_001,doc_002]

Tesseract (Parte 2) necesita modelos/tessdata/spa.traineddata:
    curl -L -o modelos/tessdata/spa.traineddata https://github.com/tesseract-ocr/tessdata/raw/4.1.0/spa.traineddata

Configuración fija (decidida antes de ver métricas; no se ajusta con la muestra de evaluación):
- PaddleOCR 3.0.3 sobre PaddlePaddle 3.0.0 (lo último que corre en Mac Intel), CPU.
- Detección PP-OCRv5_mobile_det + reconocimiento PP-OCRv5_mobile_rec. Los modelos server se
  probaron primero: en este CPU (Intel i5 de 2 núcleos, Paddle sin MKL-DNN) tardaban más de
  10 min por página y el detector se caía (segfault) con imágenes de más de ~1500 px.
- La detección ve la página reducida a 1600 px de lado mayor (text_det_limit_side_len); el
  reconocimiento lee cada línea recortada de la imagen a resolución completa.
- Sin clasificación de orientación ni desdoblado de página: las fotos entran tal como se tomaron.
- Orden de lectura por columnas (ordenar_lineas): los periódicos tienen 2-3 columnas.

Por documento guarda en datos/raw/documentos/ocr/<modelo>/: JSON con cada línea (texto, confianza,
caja), TXT con el texto y la imagen con las cajas dibujadas. El resumen va a resumen_<modelo>.csv.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
DOCS = AQUI / "datos" / "raw" / "documentos"
CONFIG = {
    "paddle": "PaddleOCR 3.0.3 (PP-OCRv5_mobile_det + PP-OCRv5_mobile_rec, det 1600 px, CPU, sin orientación ni desdoblado)",
    "paddle-base": "PaddleOCR 3.0.3 por defecto (PP-OCRv5_mobile_det + PP-OCRv5_mobile_rec, orientación + desdoblado UVDoc + orientación de línea, CPU)",
    "tesseract": "Tesseract 5.5.1 (tesserocr 2.9.1, spa de tessdata 4.1.0, OEM LSTM, PSM 3 segmentación automática)",
}


def ordenar_lineas(cajas, ancho):
    """Orden de lectura para páginas a columnas.

    Las líneas angostas (< 55 % del ancho) marcan columnas: donde ninguna cubre el eje x hay un
    hueco entre columnas. Primero van las líneas anchas de arriba (títulos), luego cada columna de
    arriba abajo, y al final las líneas anchas de abajo. Sin columnas, queda de arriba abajo.
    """
    x0, y0, x1 = cajas[:, 0], cajas[:, 1], cajas[:, 2]
    angostas = (x1 - x0) < 0.55 * ancho
    cubierto = np.zeros(int(ancho) + 1, bool)
    for a, b in zip(x0[angostas], x1[angostas]):
        cubierto[int(a):int(b) + 1] = True
    usado = np.flatnonzero(cubierto)
    huecos = []
    if len(usado):
        for a, b in zip(usado[:-1], usado[1:]):
            if b - a > 0.01 * ancho:
                huecos.append((a + b) / 2)
    columna = np.searchsorted(huecos, (x0 + x1) / 2)
    cruza = np.array([any(a < h < b for h in huecos) for a, b in zip(x0, x1)])
    inicio_columnas = y0[~cruza].min() if (~cruza).any() else np.inf
    clave = []
    for i in range(len(cajas)):
        if cruza[i]:
            clave.append((0 if y0[i] <= inicio_columnas else 2, 0, y0[i]))
        else:
            clave.append((1, columna[i], y0[i]))
    return sorted(range(len(cajas)), key=lambda i: clave[i])


class OCRPaddle:
    def __init__(self):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(text_detection_model_name="PP-OCRv5_mobile_det",
                             text_recognition_model_name="PP-OCRv5_mobile_rec",
                             text_det_limit_side_len=1600, text_det_limit_type="max",
                             use_doc_orientation_classify=False, use_doc_unwarping=False,
                             use_textline_orientation=False)

    def leer(self, ruta, carpeta):
        r = self.ocr.predict(str(ruta))[0]
        r.save_to_img(str(carpeta))
        cajas = np.array(r["rec_boxes"], float).reshape(-1, 4)
        textos, conf = list(r["rec_texts"]), [float(s) for s in r["rec_scores"]]
        from PIL import Image
        orden = ordenar_lineas(cajas, Image.open(ruta).size[0]) if len(cajas) else []
        return [{"texto": textos[i], "confianza": conf[i], "caja": cajas[i].tolist()} for i in orden]


class OCRPaddleBase:
    """Línea base de la Parte 2: PaddleOCR sin personalizar. Solo se cambian los modelos server por
    los mobile (los server no corren en este CPU); el resto queda con los valores por defecto,
    incluido el orden de lectura que devuelve Paddle."""

    def __init__(self):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(text_detection_model_name="PP-OCRv5_mobile_det",
                             text_recognition_model_name="PP-OCRv5_mobile_rec")

    def leer(self, ruta, carpeta):
        r = self.ocr.predict(str(ruta))[0]
        r.save_to_img(str(carpeta))
        cajas = np.array(r["rec_boxes"], float).reshape(-1, 4)
        return [{"texto": t, "confianza": float(s), "caja": c.tolist()}
                for t, s, c in zip(r["rec_texts"], r["rec_scores"], cajas)]


class OCRTesseract:
    """Tesseract vía tesserocr (trae la librería incluida: no hace falta Homebrew).

    El orden de lectura lo da el análisis de página del propio Tesseract (PSM 3), que ya separa columnas.
    """

    def __init__(self):
        from tesserocr import OEM, PSM, PyTessBaseAPI
        self.api = PyTessBaseAPI(path=str(AQUI / "modelos" / "tessdata"), lang="spa", psm=PSM.AUTO, oem=OEM.LSTM_ONLY)

    def leer(self, ruta, carpeta):
        from PIL import Image
        from tesserocr import RIL, iterate_level
        self.api.SetImage(Image.open(ruta))
        self.api.Recognize()
        lineas = []
        for r in iterate_level(self.api.GetIterator(), RIL.TEXTLINE):
            texto = (r.GetUTF8Text(RIL.TEXTLINE) or "").strip()
            if texto:
                lineas.append({"texto": texto, "confianza": r.Confidence(RIL.TEXTLINE) / 100,
                               "caja": [float(v) for v in r.BoundingBox(RIL.TEXTLINE)]})
        return lineas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="paddle", choices=CONFIG)
    ap.add_argument("--ids", default="")
    args = ap.parse_args()
    inv = pd.read_csv(DOCS / "inventario.csv")
    if args.ids:
        inv = inv[inv["id"].isin(args.ids.split(","))]
    carpeta = DOCS / "ocr" / args.modelo
    carpeta.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    motor = {"paddle": OCRPaddle, "paddle-base": OCRPaddleBase, "tesseract": OCRTesseract}[args.modelo]()
    print(f"{args.modelo} cargado en {time.perf_counter() - t0:.0f} s", flush=True)
    for fila in inv.itertuples():
        salida = carpeta / f"{fila.id}.json"
        if salida.exists():
            continue
        t0 = time.perf_counter()
        lineas = motor.leer(AQUI / fila.archivo, carpeta)
        seg = time.perf_counter() - t0
        texto = "\n".join(l["texto"] for l in lineas)
        salida.write_text(json.dumps({"id": fila.id, "segundos": round(seg, 1), "modelo_ocr": CONFIG[args.modelo],
                                      "lineas": lineas}, ensure_ascii=False, indent=1), encoding="utf-8")
        (carpeta / f"{fila.id}.txt").write_text(texto, encoding="utf-8")
        conf = np.mean([l["confianza"] for l in lineas]) if lineas else 0
        print(f"{fila.id}  {fila.tipo:10s} {len(lineas):4d} líneas  {len(texto):6d} car.  conf {conf:.2f}  {seg:6.1f} s", flush=True)
    filas = []
    for j in sorted(carpeta.glob("doc_*.json")):
        d = json.loads(j.read_text(encoding="utf-8"))
        filas.append({"id": d["id"], "texto_ocr": "\n".join(l["texto"] for l in d["lineas"]),
                      "n_lineas": len(d["lineas"]), "confianza_media": round(float(np.mean([l["confianza"] for l in d["lineas"]])) if d["lineas"] else 0, 3),
                      "segundos": d["segundos"], "modelo_ocr": d["modelo_ocr"]})
    pd.DataFrame(filas).to_csv(DOCS / "ocr" / f"resumen_{args.modelo}.csv", index=False)
    print("listo:", DOCS / "ocr" / f"resumen_{args.modelo}.csv", flush=True)


if __name__ == "__main__":
    main()
