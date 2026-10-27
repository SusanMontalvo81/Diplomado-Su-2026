"""Dashboard: clasificación de titulares de El Comercio en 4 categorías.

Ejecutar con:  streamlit run app.py
"""
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

RAIZ = Path(__file__).parent
DATOS = RAIZ / "datos"
MODELO = RAIZ / "modelo"
MODELO_HF = "SusanSari/clasificador-titulares-elcomercio"  # copia pública de los pesos (no caben en GitHub)

NOMBRES = {
    "politica": "Política",
    "economia": "Economía",
    "deportes": "Deportes",
    "ciencia_tecnologia": "Ciencia y Tecnología",
}
COLORES = dict(zip(NOMBRES.values(), ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))  # mismos colores que el EDA

st.set_page_config(page_title="Clasificador de titulares", page_icon="📰", layout="wide")


@st.cache_data
def cargar_noticias() -> pd.DataFrame:
    noticias = pd.read_csv(DATOS / "noticias.csv")
    etiquetas = pd.read_csv(DATOS / "etiquetas_llm.csv")[["titular", "etiqueta_llm", "confianza"]]
    noticias = noticias.merge(etiquetas, on="titular", how="left")
    noticias["categoria"] = noticias["etiqueta"].map(NOMBRES)
    return noticias


@st.cache_data
def cargar_resultados() -> tuple[pd.DataFrame, dict]:
    comparativa = pd.read_csv(MODELO / "comparativa.csv", index_col=0)
    auditoria = json.loads((MODELO / "auditoria_humana.json").read_text())
    return comparativa, auditoria


@st.cache_resource(show_spinner="Cargando el modelo...")
def cargar_clasificador():
    """Modelo fine-tuned: local en modelo/ o, si no están los pesos (p. ej. en la nube), desde Hugging Face."""
    from transformers import pipeline

    if (MODELO / "model.safetensors").exists():
        origen = str(MODELO)
    else:
        origen = os.getenv("MODELO_HF", MODELO_HF)
    try:
        return pipeline("text-classification", model=origen, top_k=None)
    except OSError:  # no se encontró el modelo ni local ni en Hugging Face
        return None


noticias = cargar_noticias()
comparativa, auditoria = cargar_resultados()

# --- 1. Encabezado y contexto ---
st.title("¿Puede un modelo ligero, entrenado con etiquetas de un LLM, clasificar titulares de noticias?")
st.markdown(
    f"Se recolectaron **{len(noticias)} titulares** de *El Comercio* (Perú) en 4 secciones y se compararon tres "
    "formas de clasificarlos en **Política, Economía, Deportes y Ciencia y Tecnología**."
)
with st.expander("Metodología"):
    st.markdown(
        f"""
1. **Recolección:** sitemaps de noticias por sección + HTML de cada nota (`requests` + BeautifulSoup), 90 titulares
   por sección, publicados del {noticias['fecha'].min()} al {noticias['fecha'].max()}.
2. **Línea base zero-shot:** `xlm-roberta-large-xnli` sin entrenamiento, evaluado en 40 titulares.
3. **Supervisión débil:** Gemini (`gemini-3.5-flash-lite`) etiquetó los 360 titulares con un prompt estructurado;
   se auditaron 20 predicciones a mano.
4. **Fine-tuning:** DistilBERT multilingüe entrenado con las etiquetas del LLM (split 70/15/15) y evaluado en un
   conjunto de test aislado, contra la categoría de la sección donde se publicó cada noticia.
"""
    )

# --- 2. Filtros en la barra lateral ---
st.sidebar.header("Filtros")
medios = st.sidebar.multiselect("Medio", sorted(noticias["medio"].unique()), default=sorted(noticias["medio"].unique()))
categorias = st.sidebar.multiselect("Categoría", list(NOMBRES.values()), default=list(NOMBRES.values()))
filtradas = noticias[noticias["medio"].isin(medios) & noticias["categoria"].isin(categorias)]

# --- 3. Indicadores clave ---
fine_tuned, zero_shot = comparativa.loc["Fine-tuned"], comparativa.loc["Zero-shot"]
col1, col2, col3 = st.columns(3)
col1.metric(
    "Noticias recolectadas",
    len(noticias) if len(filtradas) == len(noticias) else f"{len(filtradas)} de {len(noticias)}",
    help="Con los filtros actuales",
)
col2.metric(
    "F1 macro del modelo en test",
    f"{fine_tuned['f1_macro']:.3f}",
    delta=f"{fine_tuned['f1_macro'] - zero_shot['f1_macro']:+.3f} vs. zero-shot",
    help=f"DistilBERT fine-tuned, evaluado en {fine_tuned['n']} titulares de test",
)
col3.metric(
    "Concordancia LLM vs. auditoría humana",
    f"{auditoria['aciertos'] / auditoria['revisadas']:.0%}",
    help=f"{auditoria['aciertos']} de {auditoria['revisadas']} predicciones del LLM revisadas a mano fueron correctas",
)

# --- 4. Visualización y exploración ---
st.subheader("Distribución de categorías")
if filtradas.empty:
    st.warning("No hay noticias con los filtros seleccionados.")
else:
    conteo = filtradas["categoria"].value_counts().reindex(categorias).dropna().reset_index()
    conteo.columns = ["categoria", "noticias"]
    fig = px.bar(
        conteo, x="noticias", y="categoria", color="categoria", orientation="h", text="noticias",
        color_discrete_map=COLORES, labels={"noticias": "Número de noticias", "categoria": ""},
    )
    fig.update_layout(showlegend=False, barcornerradius=4, margin=dict(t=10, b=10), height=80 + 60 * len(conteo))
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(categorias)))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Noticias")
tabla = filtradas[["titular", "bajada", "categoria", "etiqueta_llm", "confianza", "seccion_original", "fecha", "medio", "url"]]
st.dataframe(
    tabla,
    use_container_width=True,
    hide_index=True,
    column_config={
        "categoria": "Categoría (sección)",
        "etiqueta_llm": "Etiqueta LLM",
        "confianza": st.column_config.NumberColumn("Confianza LLM", format="%.2f"),
        "seccion_original": "Sección original",
        "url": st.column_config.LinkColumn("Enlace", display_text="Abrir"),
    },
)
st.download_button(
    "Descargar CSV", tabla.to_csv(index=False).encode("utf-8-sig"),
    file_name="noticias_filtradas.csv", mime="text/csv",
)

with st.expander("Comparativa de modelos"):
    st.dataframe(
        comparativa[["modelo", "evaluado_en", "accuracy", "f1_macro", "seg_por_titular"]],
        use_container_width=True,
        column_config={"seg_por_titular": st.column_config.NumberColumn("Segundos por titular", format="%.3f")},
    )

# --- 5. Probador en vivo ---
st.subheader("Prueba el clasificador")
st.caption("Escribe o pega un titular nuevo. Lo clasifica el modelo DistilBERT fine-tuned.")
with st.form("probador"):
    titular = st.text_input("Titular", placeholder="Ej.: Dólar cierra a la baja y se cotiza en S/ 3,45 tras datos de inflación en EE.UU.")
    clasificar = st.form_submit_button("Clasificar", type="primary")

if clasificar:
    if not titular.strip():
        st.warning("Escribe un titular primero.")
    else:
        clasificador = cargar_clasificador()
        if clasificador is None:
            st.error("No se encontró el modelo. Ejecuta `02_clasificacion.ipynb` para entrenarlo y guardarlo en `modelo/`.")
        else:
            probabilidades = pd.DataFrame(clasificador(titular)[0])
            probabilidades["categoria"] = probabilidades["label"].map(NOMBRES)
            probabilidades = probabilidades.sort_values("score", ascending=False)
            mejor = probabilidades.iloc[0]

            st.success(f"**{mejor['categoria']}** · probabilidad {mejor['score']:.0%}")
            fig = px.bar(
                probabilidades, x="score", y="categoria", color="categoria", orientation="h",
                color_discrete_map=COLORES, text=probabilidades["score"].map("{:.0%}".format),
                labels={"score": "Probabilidad", "categoria": ""},
            )
            fig.update_layout(showlegend=False, barcornerradius=4, margin=dict(t=10, b=10), height=260)
            fig.update_xaxes(range=[0, 1], tickformat=".0%")
            fig.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig, use_container_width=True)
