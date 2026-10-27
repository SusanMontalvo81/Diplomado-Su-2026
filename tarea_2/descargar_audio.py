"""Descarga el corpus de audio de la Tarea 2 (español peruano, licencias libres).

    python descargar_audio.py

Qué baja a datos/raw/audio/ (no se versiona en Git):

- Entrevistas y testimonios de Wikimedia Commons (CC BY-SA 4.0 / CC BY 4.0) grabados en Perú:
  calle en El Agustino, conferencia de Fenmucarinap, fiesta de la
  Santísima Trinidad de Chuyas, marchas en Lima, Fiestas Patrias 2022 y testimonios de WikiAcción Perú.
- Frases leídas de OpenSLR 73 (Google, CC BY-SA 4.0): solo las frases elegidas, leídas por partes
  con peticiones HTTP Range (como datos.py de la Sesión 13), no los 900 MB del zip.

Cada audio se guarda como clip_XXX.wav (mono, 16 kHz). El original de Commons queda en
datos/raw/audio/originales/. La fuente, licencia y autor de cada clip se escriben en
datos/raw/audio/atribucion_audio.csv; el notebook 01 los pasa a datos/fuentes.csv.

Seudonimización: varios títulos de Commons llevan el nombre real de la persona entrevistada.
Por eso los clips se nombran con un id y el enlace de la fuente usa el identificador numérico de
la página (https://commons.wikimedia.org/?curid=N), que lleva al mismo archivo sin escribir el nombre.
"""
import io
import json
import math
import random
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
import soundfile as sf
from scipy.signal import resample_poly

CARPETA = Path(__file__).resolve().parent / "datos" / "raw" / "audio"
SR = 16_000
UA = {"User-Agent": "diplomado-ds-python-tarea2/2026 (estudiante; https://github.com/SusanMontalvo81/Diplomado-Su-2026)"}
PAUSA = 1.5  # segundos entre solicitudes
API = "https://commons.wikimedia.org/w/api.php"

# id: (pageid de la página en Commons, descripción seudonimizada, condición de grabación)
# Se usa el pageid y no el título porque varios títulos llevan el nombre real de quien habla.
COMMONS = {
    "clip_001": (119251161, "Entrevista en la calle a una vendedora de frutas, El Agustino, Lima (2022)", "calle"),
    "clip_002": (119251160, "Entrevista en la calle a dos vendedoras de dulces, El Agustino, Lima (2022)", "calle, 2+ hablantes"),
    "clip_003": (121219890, "Dirigente de Fenmucarinap (sierra central) en conferencia de prensa, Lima (2022)", "conferencia"),
    "clip_004": (149433723, "Entrevista a una señora sobre la fiesta de la Santísima Trinidad de Chuyas, Lima (2024)", "fiesta, ruido"),
    "clip_005": (149433722, "Entrevista a una señora pomabambina sobre la misma fiesta, Lima (2024)", "fiesta, ruido"),
    "clip_006": (133964777, "Entrevistas en una marcha en Lima (2023), parte 1", "marcha, ruido"),
    "clip_007": (133964778, "Entrevistas en una marcha en Lima (2023), parte 2", "marcha, ruido"),
    "clip_008": (119950449, "Entrevista a una joven participante de una marcha en Lima (2022)", "marcha, ruido"),
    "clip_009": (121363454, "Entrevista por Fiestas Patrias, Lima (2022), 1", "calle"),
    "clip_010": (121363453, "Entrevista por Fiestas Patrias, Lima (2022), 2", "calle"),
    "clip_011": (121363455, "Entrevista por Fiestas Patrias, Lima (2022), 3", "calle"),
    "clip_012": (121363456, "Entrevista por Fiestas Patrias, Lima (2022), 4", "calle"),
    "clip_013": (149666948, "Testimonio de una participante de San Martín, proyecto Semillas de Conocimiento (2024)", "testimonio"),
    "clip_014": (192064376, "Testimonio de memoria sobre salas de cine, WikiAcción Perú (2026), 2", "testimonio"),
    "clip_015": (192064384, "Testimonio de memoria sobre salas de cine, WikiAcción Perú (2026), 4", "testimonio"),
}

OPENSLR73 = "https://www.openslr.org/resources/73/es_pe_{sexo}.zip"
N_OPENSLR_POR_SEXO = 3
SEMILLA = 7


def _get(url, rango=None):
    cab = dict(UA)
    if rango:
        cab["Range"] = f"bytes={rango[0]}-{rango[1]}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=180) as r:
        return r.read()


class ZipRemoto(io.RawIOBase):
    """Archivo remoto que se lee por partes (HTTP Range): zipfile solo pide los bytes que necesita."""

    BLOQUE = 1 << 20

    def __init__(self, url):
        self.url, self.pos, self.buf_ini, self.buf = url, 0, 0, b""
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA, method="HEAD"), timeout=60) as r:
            self.size = int(r.headers["Content-Length"])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        fin = self.pos + n
        if not (self.buf_ini <= self.pos and fin <= self.buf_ini + len(self.buf)):
            self.buf_ini = self.pos
            self.buf = _get(self.url, (self.pos, min(self.pos + max(n, self.BLOQUE), self.size) - 1))
        datos = self.buf[self.pos - self.buf_ini:fin - self.buf_ini]
        self.pos += len(datos)
        return datos


def _guardar_16k(contenido, ruta):
    """Audio en bytes -> WAV mono de 16 kHz (la frecuencia que esperan los modelos de voz)."""
    x, sr = sf.read(io.BytesIO(contenido), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        g = math.gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g).astype("float32")
    sf.write(ruta, x, SR)
    return len(x) / SR


def _metadatos_commons(pageids):
    """Enlace al archivo, autor y licencia de cada página, en una sola consulta a la API de Commons."""
    params = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata",
              "iiextmetadatafilter": "LicenseShortName|Artist|DateTimeOriginal",
              "pageids": "|".join(str(p) for p in pageids)}
    d = json.loads(_get(API + "?" + urllib.parse.urlencode(params)))
    out = {}
    for p in d["query"]["pages"].values():
        ii = p["imageinfo"][0]
        md = ii["extmetadata"]
        limpio = lambda k: " ".join(re.sub("<[^>]+>", "", md.get(k, {}).get("value", "")).split())
        out[p["pageid"]] = {"url": ii["url"], "autor": limpio("Artist"), "licencia": limpio("LicenseShortName"),
                            "fecha_grabacion": limpio("DateTimeOriginal")[:10]}
    return out


def bajar_commons():
    originales = CARPETA / "originales"
    originales.mkdir(parents=True, exist_ok=True)
    meta = {}
    pageids = [p for p, _, _ in COMMONS.values()]
    for i in range(0, len(pageids), 20):
        meta.update(_metadatos_commons(pageids[i:i + 20]))
        time.sleep(PAUSA)
    filas = []
    for cid, (pageid, desc, condicion) in COMMONS.items():
        m = meta[pageid]
        original = originales / f"{cid}{Path(m['url']).suffix.lower()}"
        if not original.exists():
            original.write_bytes(_get(m["url"]))
            time.sleep(PAUSA)
        dur = _guardar_16k(original.read_bytes(), CARPETA / f"{cid}.wav")
        filas.append({"id": cid, "archivo_audio": f"datos/raw/audio/{cid}.wav", "duracion_seg": round(dur, 1),
                      "fuente": "Wikimedia Commons", "condicion": condicion, "descripcion": desc,
                      "autor": m["autor"], "licencia": m["licencia"], "fecha_grabacion": m["fecha_grabacion"],
                      "fuente_url": f"https://commons.wikimedia.org/?curid={pageid}",
                      "acceso": "Descarga directa desde la página de Commons (python descargar_audio.py)"})
        print(f"{cid}  {dur:6.1f} s  {m['licencia']}")
    return filas


def bajar_openslr73():
    """Frases leídas de español peruano, una por hablante, elegidas al azar con semilla fija."""
    filas, n = [], len(COMMONS)
    for sexo in ["female", "male"]:
        url = OPENSLR73.format(sexo=sexo)
        z = zipfile.ZipFile(ZipRemoto(url))
        lineas = z.read("line_index.tsv").decode("utf-8").strip().splitlines()
        tabla = pd.DataFrame([l.split("\t") for l in lineas], columns=["archivo", "texto"])
        tabla["hablante"] = tabla["archivo"].str.rsplit("_", n=1).str[0]
        tabla = tabla[tabla["texto"].str.split().str.len().between(8, 20)]
        hablantes = sorted(tabla["hablante"].unique())
        random.Random(SEMILLA).shuffle(hablantes)
        for h in hablantes[:N_OPENSLR_POR_SEXO]:
            fila = tabla[tabla["hablante"] == h].sample(1, random_state=SEMILLA).iloc[0]
            n += 1
            cid = f"clip_{n:03d}"
            dur = _guardar_16k(z.read(f"{fila['archivo']}.wav"), CARPETA / f"{cid}.wav")
            filas.append({"id": cid, "archivo_audio": f"datos/raw/audio/{cid}.wav", "duracion_seg": round(dur, 1),
                          "fuente": "OpenSLR 73", "condicion": "lectura, estudio",
                          "descripcion": f"Frase leída por un{'a' if sexo == 'female' else ''} hablante de Lima ({fila['archivo']})",
                          "autor": "Google (Guevara-Rukoz et al., 2020)", "licencia": "CC BY-SA 4.0",
                          "fecha_grabacion": "", "fuente_url": "https://www.openslr.org/73/",
                          "acceso": f"Archivo {fila['archivo']}.wav dentro de es_pe_{sexo}.zip (python descargar_audio.py)",
                          "transcripcion_openslr": fila["texto"].strip()})
            print(f"{cid}  {dur:6.1f} s  OpenSLR 73 {fila['archivo']}")
        time.sleep(PAUSA)
    return filas


if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    tabla = pd.DataFrame(bajar_commons() + bajar_openslr73())
    tabla.to_csv(CARPETA / "atribucion_audio.csv", index=False)
    print(f"\n{len(tabla)} clips, {tabla['duracion_seg'].sum() / 60:.1f} min -> {CARPETA / 'atribucion_audio.csv'}")
