"""Dashboard interactivo de noticias clasificadas.

Ejecutar con:  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATOS = Path(__file__).parent / "datos"

st.set_page_config(page_title="Dashboard de noticias", page_icon="📰", layout="wide")


@st.cache_data
def cargar_csv(nombre: str) -> pd.DataFrame | None:
    ruta = DATOS / nombre
    return pd.read_csv(ruta) if ruta.exists() else None


st.title("📰 Dashboard de noticias")

noticias = cargar_csv("noticias.csv")
etiquetas = cargar_csv("etiquetas_llm.csv")

if noticias is None:
    st.info("Aún no existe `datos/noticias.csv`. Ejecuta primero `01_recoleccion.ipynb`.")
    st.stop()

df = etiquetas if etiquetas is not None else noticias

# --- Filtros ---
st.sidebar.header("Filtros")
columnas_categoricas = [c for c in df.columns if df[c].dtype == "object" and df[c].nunique() <= 30]
for col in columnas_categoricas:
    opciones = sorted(df[col].dropna().unique())
    seleccion = st.sidebar.multiselect(col, opciones, default=opciones)
    df = df[df[col].isin(seleccion)]

busqueda = st.sidebar.text_input("Buscar texto")
if busqueda:
    columnas_texto = df.select_dtypes("object").columns
    mascara = df[columnas_texto].apply(lambda s: s.str.contains(busqueda, case=False, na=False)).any(axis=1)
    df = df[mascara]

# --- Métricas ---
c1, c2, c3 = st.columns(3)
c1.metric("Noticias", len(df))
c2.metric("Columnas", df.shape[1])
c3.metric("Etiquetas LLM", "Sí" if etiquetas is not None else "Pendiente")

# --- Gráficos ---
if columnas_categoricas:
    col = st.selectbox("Distribución por", columnas_categoricas)
    conteo = df[col].value_counts().reset_index()
    conteo.columns = [col, "cantidad"]
    st.plotly_chart(px.bar(conteo, x=col, y="cantidad"), use_container_width=True)

st.subheader("Datos")
st.dataframe(df, use_container_width=True)
