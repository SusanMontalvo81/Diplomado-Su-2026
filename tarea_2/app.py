"""Dashboard: documentos y audios peruanos convertidos en texto estructurado y buscable.

Ejecutar con:  streamlit run app.py

Solo lee los CSV que generan 01_extraccion.ipynb y 02_evaluacion.ipynb (no corre OCR, ASR ni LLM).
Todos los textos que muestra están revisados y seudonimizados; las imágenes y audios de
datos/ejemplos/ son los únicos con licencia que permite publicarlos y sin datos personales.
"""
import html
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

RAIZ = Path(__file__).parent
DATOS = RAIZ / "datos"
EJEMPLOS = DATOS / "ejemplos"

TIPOS = ["impreso", "foto", "manuscrito"]
MODELOS_OCR = ["PaddleOCR por defecto (línea base)", "PaddleOCR ajustado (Parte 1)", "Tesseract 5.5"]
MODELOS_ASR = ["Whisper small (línea base)", "Whisper large-v3-turbo", "Qwen3-ASR 0.6B"]
COLORES = dict(zip(MODELOS_OCR + MODELOS_ASR, ["#9aa5b1", "#2a78d6", "#eb6834", "#9aa5b1", "#1baf7a", "#8e5bd6"]))
CAMPOS_DOC = ["tema", "resumen", "emisor", "fecha", "lugar", "monto"]
CAMPOS_AUDIO = ["tema", "resumen", "numero_hablantes", "citas_clave"]

st.set_page_config(page_title="Voces y documentos peruanos", page_icon="🗂️", layout="wide")


@st.cache_data
def cargar() -> dict[str, pd.DataFrame]:
    d = {n: pd.read_csv(DATOS / f"{n}.csv") for n in
         ["documentos", "transcripciones", "fuentes", "extraccion_llm", "auditoria_llm", "evaluacion_ocr",
          "evaluacion_asr", "metricas_modelos", "metricas_por_grupo", "metricas_llm"]}
    for n in ["documentos", "transcripciones", "auditoria_llm", "evaluacion_ocr", "evaluacion_asr"]:
        d[n] = d[n].fillna("")
    campos = {r.id: json.loads(r.campos_json) for r in d["extraccion_llm"].itertuples()}
    d["documentos"]["tema_llm"] = d["documentos"]["id"].map(lambda i: campos[i]["tema"])
    d["transcripciones"]["tema_llm"] = d["transcripciones"]["id"].map(lambda i: campos[i]["tema"])
    d["transcripciones"] = d["transcripciones"].merge(
        d["fuentes"][["id", "tipo", "autor", "licencia"]].rename(columns={"tipo": "condicion"}), on="id")
    d["documentos"] = d["documentos"].merge(d["fuentes"][["id", "licencia"]], on="id")
    d["campos"] = campos
    return d


def plano(texto: str) -> str:
    """Minúsculas y sin tildes, para que la búsqueda no dependa de cómo se escribió."""
    texto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def contiene(serie: pd.Series, buscado: str) -> pd.Series:
    return serie.map(lambda t: plano(buscado) in plano(t)) if buscado else pd.Series(True, index=serie.index)


def resaltar(texto: str, buscado: str) -> str:
    """Texto como HTML seguro, con las coincidencias de la búsqueda marcadas."""
    seguro = html.escape(str(texto))
    if buscado:
        partes, ultimo = [], 0
        for m in re.finditer(re.escape(plano(html.escape(buscado))), plano(seguro)):
            partes += [seguro[ultimo:m.start()], f"<mark>{seguro[m.start():m.end()]}</mark>"]
            ultimo = m.end()
        seguro = "".join(partes) + seguro[ultimo:]
    return seguro.replace("\n", "<br>")


def caja(texto: str, buscado: str = "", alto: int = 260):
    st.markdown(f"<div style='max-height:{alto}px;overflow-y:auto;padding:0.6rem 0.8rem;border:1px solid "
                f"rgba(128,128,128,0.35);border-radius:6px;font-size:0.9rem'>{resaltar(texto, buscado)}</div>",
                unsafe_allow_html=True)


def ficha_llm(campos: dict, orden: list[str]):
    filas = []
    for c in orden:
        v = campos.get(c)
        filas.append({"campo": c, "valor": "null (no aparece en el texto)" if v is None
                      else " · ".join(v) if isinstance(v, list) else str(v)})
    st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)


d = cargar()
docs, clips, metricas = d["documentos"], d["transcripciones"], d["metricas_modelos"]
llm = d["metricas_llm"].iloc[0]

# --- 1. Encabezado y contexto ---
st.title("¿Pueden convertirse documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?")
st.markdown(
    f"Se procesaron **{len(docs)} documentos peruanos** (impresos, fotos con sombra o inclinación y manuscritos) con OCR "
    f"y **{clips['duracion_seg'].sum() / 60:.1f} minutos de audio** en español peruano con reconocimiento de voz. "
    "Un LLM convirtió cada texto en una ficha con campos estructurados, y los modelos se evaluaron contra "
    "transcripciones hechas a mano."
)
with st.expander("Metodología"):
    st.markdown(
        """
1. **Corpus:** 25 documentos propios (8 impresos del *Catálogo de periódicos cusqueños* de 1999, 8 fotos de celular del
   *Registro Oficial del Departamento*, Cusco 1857–1862, y 9 asientos manuscritos de una partida registral) y 20 clips de
   Wikimedia Commons y OpenSLR 73 (calle, marchas, fiesta, testimonios, conferencia y lecturas de estudio).
2. **Extracción (Parte 1):** PaddleOCR 3.0.3 (PP-OCRv5 *mobile*) y faster-whisper `large-v3-turbo` con VAD y diarización;
   nombres de personas privadas reemplazados por seudónimos (`PERSONA_xx`) con NER y revisión humana.
3. **Evaluación (Parte 2):** CER y WER sobre **los mismos 10 documentos y 10 clips**, con referencias transcritas a mano.
   En documentos se evalúa un fragmento fijo (parte superior) de cada página. Se comparan 3 OCR y 3 modelos de voz.
4. **Extracción estructurada:** Gemini 3.5 Flash con esquema JSON fijo sobre los textos seudonimizados; se auditaron a mano
   20 fichas sorteadas.
"""
    )

# --- 2. Filtros y búsqueda ---
st.sidebar.header("Búsqueda y filtros")
buscado = st.sidebar.text_input("Buscar en los textos OCR y ASR", placeholder="Ej.: Cuzco, soles, marcha").strip()
tipos = st.sidebar.multiselect("Tipo de documento", TIPOS, default=TIPOS)
condiciones_todas = sorted(clips["condicion"].unique())
condiciones = st.sidebar.multiselect("Condición de grabación", condiciones_todas, default=condiciones_todas)
dur_max = float(clips["duracion_seg"].max())
duracion = st.sidebar.slider("Duración del audio (s)", 0.0, dur_max, (0.0, dur_max), step=5.0)
st.sidebar.markdown("**Modelos**")
modelos_ocr = st.sidebar.multiselect("OCR", MODELOS_OCR, default=MODELOS_OCR)
modelos_asr = st.sidebar.multiselect("Reconocimiento de voz", MODELOS_ASR, default=MODELOS_ASR)

docs_f = docs[docs["tipo"].isin(tipos) & contiene(docs["texto_ocr"], buscado)]
clips_f = clips[clips["condicion"].isin(condiciones) & clips["duracion_seg"].between(*duracion)
                & contiene(clips["texto_asr"], buscado)]
if buscado:
    st.sidebar.caption(f"«{buscado}» aparece en {len(docs_f)} documentos y {len(clips_f)} audios.")

# --- 3. Indicadores clave ---
fila = metricas.set_index("modelo")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Documentos procesados", len(docs) if len(docs_f) == len(docs) else f"{len(docs_f)} de {len(docs)}",
          help="Con los filtros actuales")
c2.metric("Minutos de audio transcritos", f"{clips_f['duracion_seg'].sum() / 60:.1f}",
          help=f"De {clips['duracion_seg'].sum() / 60:.1f} min en total (20 clips; se descartó 1 sin voz)")
c3.metric("CER · Tesseract (elegido)", f"{fila.loc['Tesseract 5.5', 'error']:.2f}",
          delta=f"{fila.loc['Tesseract 5.5', 'error'] - fila.loc[MODELOS_OCR[0], 'error']:+.2f} vs. línea base",
          delta_color="inverse", help="Errores de caracteres en 10 documentos (menos es mejor)")
c4.metric("WER · Whisper small (elegido)", f"{fila.loc['Whisper small (línea base)', 'error']:.2f}",
          help="Errores de palabras en 10 clips (menos es mejor). Whisper turbo: "
               f"{fila.loc['Whisper large-v3-turbo', 'error']:.2f}, pero 3,4 veces más lento")
c5.metric("Acuerdo LLM vs. auditoría humana", f"{llm['acuerdo_llm_humano'] / llm['auditadas']:.0%}",
          help=f"{llm['acuerdo_llm_humano']} de {llm['auditadas']} fichas del LLM completamente correctas")

resultados, explorar_docs, explorar_audios = st.tabs(["📊 Resultados de los modelos", "📄 Documentos", "🎙️ Audios"])

# --- 4. Visualización: resultados de la evaluación ---
with resultados:
    grupos = d["metricas_por_grupo"]
    izq, der = st.columns(2)
    with izq:
        st.subheader("OCR: error por tipo de documento")
        g = grupos[(grupos["metrica"] == "CER") & grupos["grupo"].isin(tipos) & grupos["modelo"].isin(modelos_ocr)]
        if g.empty:
            st.info("Elige al menos un tipo de documento y un modelo de OCR.")
        else:
            fig = px.bar(g, x="grupo", y="error", color="modelo", barmode="group", text_auto=".2f",
                         color_discrete_map=COLORES, category_orders={"grupo": TIPOS, "modelo": MODELOS_OCR},
                         labels={"grupo": "", "error": "CER (menos es mejor)", "modelo": ""},
                         title="Ningún OCR gana en todo: Tesseract lidera en fotos y PaddleOCR en manuscritos")
            fig.update_layout(legend=dict(orientation="h", y=-0.2), margin=dict(t=60))
            st.plotly_chart(fig, use_container_width=True)
    with der:
        st.subheader("Voz: error por condición de grabación")
        g = grupos[(grupos["metrica"] == "WER") & grupos["grupo"].isin(condiciones) & grupos["modelo"].isin(modelos_asr)]
        if g.empty:
            st.info("Elige al menos una condición evaluada y un modelo de voz.")
        else:
            fig = px.bar(g, x="grupo", y="error", color="modelo", barmode="group", text_auto=".2f",
                         color_discrete_map=COLORES, category_orders={"modelo": MODELOS_ASR},
                         labels={"grupo": "", "error": "WER (menos es mejor)", "modelo": ""},
                         title="El ruido de marchas y fiestas multiplica el error frente a la lectura en estudio")
            fig.update_layout(legend=dict(orientation="h", y=-0.2), margin=dict(t=60))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Precisión frente a costo de cómputo")
    m = metricas[metricas["modelo"].isin(modelos_ocr + modelos_asr)]
    if not m.empty:
        fig = px.scatter(m, x="latencia", y="error", color="modelo", facet_col="modalidad", text="modelo",
                         color_discrete_map=COLORES, labels={"latencia": "Latencia", "error": "Error (CER o WER)"},
                         title="Tesseract y Whisper small: casi la misma precisión por una fracción del tiempo")
        fig.update_traces(textposition="top center", marker=dict(size=13))
        fig.update_xaxes(matches=None, rangemode="tozero")
        fig.for_each_annotation(lambda a: a.update(text={"modalidad=documentos": "Documentos (segundos por documento)",
                                                         "modalidad=audio": "Audio (factor de tiempo real)"}[a.text]))
        fig.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(m[["modalidad", "modelo", "rol", "metrica", "error", "latencia", "unidad_latencia"]],
                 hide_index=True, use_container_width=True,
                 column_config={"error": st.column_config.NumberColumn("Error", format="%.3f"),
                                "latencia": st.column_config.NumberColumn("Latencia", format="%.2f")})

    st.subheader("Auditoría de la extracción con LLM")
    aud = d["auditoria_llm"]
    campos_aud = CAMPOS_DOC + ["numero_hablantes", "citas_clave"]
    acierto = pd.DataFrame({c: {"correctos": (aud[c] == "si").sum(), "evaluados": (aud[c] != "na").sum()}
                            for c in campos_aud}).T
    acierto["acierto"] = 100 * acierto["correctos"] / acierto["evaluados"]
    st.markdown(f"**{llm['acuerdo_llm_humano']} de {llm['auditadas']}** fichas completamente correctas. El LLM acierta "
                "siempre el tema y el resumen; falla en campos puntuales de manuscritos y de páginas con varios "
                "documentos (toma anotaciones al margen como dato principal o elige un solo decreto).")
    st.dataframe(acierto.reset_index(names="campo"), hide_index=True, use_container_width=True,
                 column_config={"acierto": st.column_config.ProgressColumn("Acierto", format="%.0f%%", min_value=0, max_value=100)})

# --- 5a. Explorador de documentos ---
with explorar_docs:
    st.subheader(f"Documentos ({len(docs_f)})")
    tabla = docs_f[["id", "tipo", "tema_llm", "texto_ocr", "texto_referencia", "fuente", "licencia"]]
    st.dataframe(tabla, hide_index=True, use_container_width=True, height=280,
                 column_config={"tema_llm": "Tema (LLM)", "texto_ocr": "Texto OCR",
                                "texto_referencia": "Referencia manual (recorte)"})
    st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name="documentos_filtrados.csv", mime="text/csv")

    if not docs_f.empty:
        elegido = st.selectbox("Elige un documento", docs_f["id"],
                               format_func=lambda i: f"{i} · {docs.set_index('id').loc[i, 'tipo']} · {d['campos'][i]['tema']}")
        doc = docs.set_index("id").loc[elegido]
        imagen = EJEMPLOS / "documentos" / f"{elegido}.jpg"
        izq, der = st.columns([2, 3])
        with izq:
            if imagen.exists():
                st.image(str(imagen), caption=f"{elegido} · {doc['licencia']}", use_container_width=True)
            else:
                st.info("La imagen no se publica: " + ("el catálogo tiene derechos reservados."
                        if doc["tipo"] == "impreso" else "la partida registral contiene datos personales."
                        " El texto está seudonimizado."))
            st.markdown("**Ficha extraída por el LLM**")
            ficha_llm(d["campos"][elegido], CAMPOS_DOC)
        with der:
            st.markdown(f"**Texto OCR** · {doc['modelo_ocr']}")
            caja(doc["texto_ocr"], buscado, alto=420)
        evaluado = d["evaluacion_ocr"][(d["evaluacion_ocr"]["id"] == elegido) & d["evaluacion_ocr"]["modelo"].isin(modelos_ocr)]
        if doc["texto_referencia"]:
            st.markdown("**Evaluación sobre el recorte superior de la página**")
            cols = st.columns(len(evaluado) + 1)
            with cols[0]:
                st.markdown("*Referencia manual*")
                caja(doc["texto_referencia"], buscado)
            for col, r in zip(cols[1:], evaluado.itertuples()):
                with col:
                    st.markdown(f"*{r.modelo}* · CER **{r.cer:.2f}**")
                    caja(r.texto, buscado)
        else:
            st.caption("Este documento no está en la muestra de evaluación (10 de 25), así que no tiene referencia manual ni CER.")

# --- 5b. Explorador de audios ---
with explorar_audios:
    st.subheader(f"Audios ({len(clips_f)})")
    tabla = clips_f[["id", "condicion", "duracion_seg", "n_hablantes", "tema_llm", "texto_asr", "texto_referencia", "autor", "licencia"]]
    st.dataframe(tabla, hide_index=True, use_container_width=True, height=280,
                 column_config={"condicion": "Condición", "duracion_seg": st.column_config.NumberColumn("Duración (s)", format="%.0f"),
                                "n_hablantes": "Hablantes", "tema_llm": "Tema (LLM)", "texto_asr": "Texto ASR",
                                "texto_referencia": "Referencia manual"})
    st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name="audios_filtrados.csv", mime="text/csv")

    if not clips_f.empty:
        elegido = st.selectbox("Elige un audio", clips_f["id"],
                               format_func=lambda i: f"{i} · {clips.set_index('id').loc[i, 'condicion']} · {d['campos'][i]['tema']}")
        clip = clips.set_index("id").loc[elegido]
        audio = EJEMPLOS / "audio" / f"{elegido}.wav"
        izq, der = st.columns([2, 3])
        with izq:
            if audio.exists():
                st.audio(str(audio))
                st.caption(f"{clip['autor']} · {clip['licencia']}")
            else:
                st.info("El audio no se publica porque en él se dicen nombres de personas, que en el texto están "
                        "seudonimizados. Se puede consultar la transcripción.")
            st.markdown(f"**{clip['duracion_seg']:.0f} s · {clip['n_hablantes']} hablante(s) detectado(s)**")
            st.markdown("**Ficha extraída por el LLM**")
            ficha_llm(d["campos"][elegido], CAMPOS_AUDIO)
        with der:
            st.markdown(f"**Transcripción con marcas de hablante** · {clip['modelo_asr']}")
            caja(re.sub(r"\s*(\[HABLANTE_\d+\])", r"\n\1", clip["texto_asr"]).strip(), buscado, alto=420)
        evaluado = d["evaluacion_asr"][(d["evaluacion_asr"]["id"] == elegido) & d["evaluacion_asr"]["modelo"].isin(modelos_asr)]
        if clip["texto_referencia"]:
            st.markdown("**Comparación de modelos de voz** (sin marcas de hablante)")
            cols = st.columns(len(evaluado) + 1)
            with cols[0]:
                st.markdown("*Referencia manual*")
                caja(clip["texto_referencia"], buscado)
            for col, r in zip(cols[1:], evaluado.itertuples()):
                with col:
                    st.markdown(f"*{r.modelo}* · WER **{r.wer:.2f}** · RTF {r.rtf:.2f}")
                    caja(r.texto, buscado)
        else:
            st.caption("Este audio no está en la muestra de evaluación (10 de 20), así que no tiene referencia manual ni WER.")

with st.expander("Fuentes, licencias y privacidad"):
    st.markdown(
        "Cada archivo tiene su fuente, licencia y forma de recuperarlo en `datos/fuentes.csv`. Los nombres de personas "
        "privadas (entrevistados, propietarios, notarios) están reemplazados por seudónimos `PERSONA_xx`; los impresos "
        "y periódicos son publicaciones públicas o históricas y no se seudonimizan. Solo se muestran las imágenes de "
        "las fotos del periódico de 1857–1862 (dominio público; fotos propias, CC BY 4.0) y los audios en los que nadie "
        "dice un nombre (lecturas de OpenSLR 73 y dos clips de Wikimedia Commons)."
    )
    st.dataframe(d["fuentes"], hide_index=True, use_container_width=True,
                 column_config={"fuente_url": st.column_config.LinkColumn("Enlace")})
