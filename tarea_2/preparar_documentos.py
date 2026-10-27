"""Prepara el corpus de documentos (Parte 1): de los originales a una imagen por documento.

    python preparar_documentos.py

Lee datos/raw/documentos/originales/ (capturas propias, no se versionan) y escribe en
datos/raw/documentos/:

- crudo/doc_XXX.png|jpg   respaldo crudo: la página completa tal como llegó.
- doc_XXX.png|jpg         recorte de trabajo que recibe el OCR.
- inventario.csv          id, tipo, origen, fuente, licencia, si la imagen se puede publicar y hash.

Tres tipos, 25 documentos:
- impreso (doc_001-008): páginas 2-9 de un PDF digital (catálogo de periódicos cusqueños, 1999).
  Se rasterizan a 200 dpi para que el OCR lea píxeles, como en un escaneo.
- manuscrito (doc_009-017): páginas 3-11 de una copia de partida registral (SUNARP Cusco).
  El recorte es el escaneo incrustado en el PDF: solo el recuadro manuscrito, sin el encabezado,
  el QR ni los números de solicitud. Tiene nombres reales: la imagen no se publica.
- foto (doc_018-025): fotos con celular, con sombra o inclinación, del Registro Oficial del
  Departamento (Cusco, 1857-1862), ordenadas por fecha.
"""
import hashlib
import io
import shutil
from pathlib import Path

import pandas as pd
import pymupdf
from PIL import Image, ImageOps

AQUI = Path(__file__).resolve().parent
DOCS = AQUI / "datos" / "raw" / "documentos"
ORIG = DOCS / "originales"
MAX_LADO = 3000  # px: las fotos del celular llegan a 4096; más grande solo hace lento el OCR en CPU

IMPRESO = ("Captura propia del PDF de Glave, L. M. (1999). Catálogo de periódicos cusqueños del siglo XIX. "
           "UNSAAC / Archivo Departamental del Cusco / CBC")
MANUSCRITO = "Captura propia: copia literal de partida registral, SUNARP Oficina Registral de Cusco (asientos 1911-1995)"
FOTO = "Foto propia con celular de un ejemplar del Registro Oficial del Departamento (Cusco, Imprenta del Estado)"

# foto original -> fecha del número fotografiado (para ordenarlas)
FOTOS = {
    "RODC 07-01-1857.jpg": "1857-01-07",
    "RODC 20-03-1857.jpg": "1857-03-20",
    "RODC 1858 deterioro.jpg": "1858",
    "RODC 11-01-1859.jpg": "1859-01-11",
    "RODC 10-01-1860.jpg": "1860-01-10",
    "RODC-LOET 1861 -02.jpg": "1861-02-08",
    "RODC 18-01-1862.jpg": "1862-01-18",
    "RODC 14-02-1862.jpg": "1862-02-14",
}


def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def achicar(img):
    img.thumbnail((MAX_LADO, MAX_LADO))
    return img


def main():
    (DOCS / "crudo").mkdir(parents=True, exist_ok=True)
    filas, n = [], 0

    pdf = pymupdf.open(ORIG / "impresos.pdf")
    for i, pagina in enumerate(pdf):
        n += 1
        did = f"doc_{n:03d}"
        crudo = DOCS / "crudo" / f"{did}.png"
        pagina.get_pixmap(dpi=200).save(crudo)
        shutil.copy(crudo, DOCS / f"{did}.png")
        filas.append({"id": did, "archivo": f"datos/raw/documentos/{did}.png", "tipo": "impreso",
                      "origen": f"impresos.pdf, página {i + 1} (pág. {i + 2} del catálogo)",
                      "fuente": IMPRESO, "licencia": "© Derechos reservados; uso académico del texto, imagen no publicada",
                      "imagen_publicable": False})

    pdf = pymupdf.open(ORIG / "manuscritos.pdf")
    for i, pagina in enumerate(pdf):
        n += 1
        did = f"doc_{n:03d}"
        pagina.get_pixmap(dpi=200).save(DOCS / "crudo" / f"{did}.png")
        xref = max(pagina.get_images(), key=lambda im: im[2] * im[3])[0]  # el escaneo del recuadro manuscrito
        recorte = Image.open(io.BytesIO(pymupdf.Pixmap(pdf, xref).tobytes("png")))
        achicar(recorte.convert("L")).save(DOCS / f"{did}.png")
        filas.append({"id": did, "archivo": f"datos/raw/documentos/{did}.png", "tipo": "manuscrito",
                      "origen": f"manuscritos.pdf, página {i + 1}", "fuente": MANUSCRITO,
                      "licencia": "Publicidad registral; contiene datos personales: texto seudonimizado, imagen no publicada",
                      "imagen_publicable": False})

    for original, fecha in sorted(FOTOS.items(), key=lambda x: x[1]):
        n += 1
        did = f"doc_{n:03d}"
        shutil.copy(ORIG / "fotos" / original, DOCS / "crudo" / f"{did}.jpg")
        img = ImageOps.exif_transpose(Image.open(ORIG / "fotos" / original))
        achicar(img.convert("RGB")).save(DOCS / f"{did}.jpg", quality=92)
        filas.append({"id": did, "archivo": f"datos/raw/documentos/{did}.jpg", "tipo": "foto",
                      "origen": f"fotos/{original} (número del {fecha})", "fuente": FOTO,
                      "licencia": "Dominio público (impreso de 1857-1862); foto propia, CC BY 4.0",
                      "imagen_publicable": True})

    tabla = pd.DataFrame(filas)
    tabla["hash_sha256"] = [sha256(AQUI / a) for a in tabla["archivo"]]
    tabla.to_csv(DOCS / "inventario.csv", index=False)
    print(tabla[["id", "tipo", "origen"]].to_string(index=False))
    print(f"\n{len(tabla)} documentos -> {DOCS / 'inventario.csv'}")


if __name__ == "__main__":
    main()
