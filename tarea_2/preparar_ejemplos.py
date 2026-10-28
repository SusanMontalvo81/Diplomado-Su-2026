"""Copia a datos/ejemplos/ (documentos/ y audio/) las imágenes y audios que el dashboard puede
mostrar (Parte 3).

    python preparar_ejemplos.py

Solo se publica lo que tiene licencia que lo permite y no contiene datos personales:
- Imágenes: las 8 fotos del Registro Oficial del Departamento (Cusco, 1857-1862): el impreso es de
  dominio público y las fotos son propias (CC BY 4.0). Se reducen a 1400 px de lado mayor. Los impresos
  (catálogo de 1999, derechos reservados) y los manuscritos (partida registral con datos personales) no.
- Audios: los clips en los que nadie dice un nombre de persona: las 6 lecturas de OpenSLR 73
  (CC BY-SA 4.0), la conferencia clip_003 (CC BY-SA 4.0) y el testimonio clip_013 (CC BY 4.0). Los
  demás mencionan nombres, que en el texto están seudonimizados pero se oirían en el audio; clip_008
  también queda fuera porque el entrevistador dice su nombre.
"""
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image

AQUI = Path(__file__).resolve().parent
RAW = AQUI / "datos" / "raw"
EJEMPLOS = AQUI / "datos" / "ejemplos"
AUDIOS = ["clip_003", "clip_013", "clip_016", "clip_017", "clip_018", "clip_019", "clip_020", "clip_021"]

if __name__ == "__main__":
    (EJEMPLOS / "documentos").mkdir(parents=True, exist_ok=True)
    (EJEMPLOS / "audio").mkdir(parents=True, exist_ok=True)
    inv = pd.read_csv(RAW / "documentos" / "inventario.csv")
    for fila in inv[inv["imagen_publicable"]].itertuples():
        im = Image.open(AQUI / fila.archivo).convert("RGB")
        im.thumbnail((1400, 1400))
        im.save(EJEMPLOS / "documentos" / f"{fila.id}.jpg", quality=82)
    for c in AUDIOS:
        shutil.copy(RAW / "audio" / f"{c}.wav", EJEMPLOS / "audio" / f"{c}.wav")
    archivos = sorted(p for p in EJEMPLOS.rglob("*") if p.is_file() and p.name != ".gitkeep")
    print(f"{len(archivos)} archivos, {sum(p.stat().st_size for p in archivos) / 1e6:.1f} MB en {EJEMPLOS}")
