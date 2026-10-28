"""Sortea las 20 extracciones del LLM para la auditoría humana y prepara el material (Parte 2).

    python preparar_auditoria.py

Sorteo con semilla fija (2026): 10 documentos de 25 y 10 audios de 20.

- datos/auditoria_llm.csv: planilla que se completa a mano, una fila por extracción y una columna por
  campo, con "si" (correcto), "no" (incorrecto) o "na" (el campo no corresponde a esa modalidad). Si ya
  existe no se sobrescribe, para no borrar la auditoría.
- datos/raw/auditoria/auditoria.html: para leer cada texto de entrada junto a lo que extrajo el LLM.
  Incluye dos ayudas automáticas: si numero_hablantes coincide con las marcas [HABLANTE_n] y si cada cita
  aparece literal en el texto. Son solo ayudas: quien audita decide.

Criterio de corrección (se juzga contra el texto que recibió el LLM, porque es lo único que conocía):
- tema y resumen: describen el texto sin agregar hechos que no estén en él;
- emisor, fecha, lugar, monto: el valor está en el texto (se aceptan los errores de lectura del OCR),
  o es null porque el dato no aparece. Inventarlo o dejar null un dato que sí aparece es un error;
- numero_hablantes: igual al número de marcas de hablante distintas;
- citas_clave: copiadas del texto y representativas.
Una extracción es completamente correcta si todos sus campos están en "si" o "na".
"""
import html
import json
import re
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
SEMILLA = 2026
CAMPOS = ["tema", "resumen", "emisor", "fecha", "lugar", "monto", "numero_hablantes", "citas_clave"]
DE_DOC = {"emisor", "fecha", "lugar", "monto"}
DE_AUDIO = {"numero_hablantes", "citas_clave"}


def sin_espacios(t):
    return re.sub(r"[^\w]", "", (t or "").lower())


if __name__ == "__main__":
    ext = pd.read_csv(AQUI / "datos" / "extraccion_llm.csv").set_index("id")
    docs = pd.read_csv(AQUI / "datos" / "documentos.csv").set_index("id")
    clips = pd.read_csv(AQUI / "datos" / "transcripciones.csv").set_index("id")
    muestra = (sorted(docs.index.to_series().sample(10, random_state=SEMILLA))
               + sorted(clips.index.to_series().sample(10, random_state=SEMILLA)))

    planilla = AQUI / "datos" / "auditoria_llm.csv"
    if not planilla.exists():
        filas = []
        for i in muestra:
            m = ext.loc[i, "modalidad"]
            fila = {"id": i, "modalidad": m}
            for c in CAMPOS:
                fila[c] = "na" if (m == "documento" and c in DE_AUDIO) or (m == "audio" and c in DE_DOC) else ""
            fila["comentario"] = ""
            filas.append(fila)
        pd.DataFrame(filas).to_csv(planilla, index=False)
        print("planilla creada:", planilla)

    partes = []
    for n, i in enumerate(muestra, 1):
        campos = json.loads(ext.loc[i, "campos_json"])
        if i in docs.index:
            texto, origen = docs.loc[i, "texto_ocr"], f"documento · {docs.loc[i, 'tipo']} · texto OCR"
        else:
            texto, origen = clips.loc[i, "texto_asr"], f"audio · {clips.loc[i, 'duracion_seg']:.0f} s · texto ASR"
        ayudas = []
        if "numero_hablantes" in campos:
            marcas = len(set(re.findall(r"\[HABLANTE_\d+\]", texto)))
            ayudas.append(f"numero_hablantes: el texto tiene {marcas} marcas distintas → "
                          + ("coincide" if marcas == campos["numero_hablantes"] else "NO coincide"))
        for cita in campos.get("citas_clave") or []:
            ayudas.append(("cita literal" if sin_espacios(cita) in sin_espacios(texto) else "cita NO literal")
                          + f": «{html.escape(cita[:80])}»")
        filas_campos = "".join(f"<tr><th>{c}</th><td>{html.escape(json.dumps(v, ensure_ascii=False) if v is not None else 'null')}</td></tr>"
                               for c, v in campos.items() if c != "modalidad")
        partes.append(f"""<section id="{i}"><h2>{n}. {i} <small>{origen}</small></h2>
<div class="par"><pre>{html.escape(texto)}</pre><div><table>{filas_campos}</table>
<ul>{''.join(f'<li>{a}</li>' for a in ayudas)}</ul></div></div></section>""")
    pagina = f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>Auditoría LLM</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px;max-width:1300px}} .par{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
pre{{white-space:pre-wrap;background:#f6f6f6;padding:10px;max-height:420px;overflow:auto;font-size:13px}}
th{{text-align:left;vertical-align:top;padding-right:10px}} td{{padding-bottom:6px}} section{{border-top:2px solid #ccc;margin-top:24px}}
small{{color:#666;font-weight:normal}} @media (max-width:800px){{.par{{grid-template-columns:1fr}}}}</style>
<h1>Auditoría de 20 extracciones del LLM</h1>
<p>Izquierda: el texto que recibió Gemini. Derecha: lo que extrajo. Marca cada campo en <code>datos/auditoria_llm.csv</code>
con <b>si</b> o <b>no</b> según el criterio de <code>preparar_auditoria.py</code>.</p>
{''.join(partes)}</html>"""
    salida = AQUI / "datos" / "raw" / "auditoria"
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "auditoria.html").write_text(pagina, encoding="utf-8")
    print("muestra:", ", ".join(muestra))
    print("para leer:", salida / "auditoria.html")
