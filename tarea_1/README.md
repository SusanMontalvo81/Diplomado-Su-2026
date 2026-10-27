# Tarea 1 · Clasificación de titulares de noticias

**Dashboard en línea:** https://clasificador-titulares.streamlit.app/

## Pregunta del proyecto

**¿Puede un modelo ligero, entrenado solo con etiquetas generadas por un LLM, clasificar titulares de noticias
peruanas en 4 categorías (Política, Economía, Deportes, Ciencia y Tecnología) con calidad cercana a la del propio LLM,
pero más rápido y sin costo por uso?**

## Datos

| | |
|---|---|
| **Medio** | B · *El Comercio* (https://elcomercio.pe/) |
| **Secciones** | Economía, Política, Deporte Total y Tecnología (Ciencia y Tecnología): 90 titulares por sección |
| **Fecha de extracción** | 26/10/2026, 16:23 (hora de Lima) |
| **Fechas de publicación** | Del 12/10/2026 al 26/10/2026 |
| **Total** | 360 noticias · `datos/noticias.csv` (7 columnas) |

## Metodología

1. **Recolección** (`01_recoleccion.ipynb`): sitemap de noticias de cada sección + HTML de cada nota con `requests` y
   BeautifulSoup, con pausas entre peticiones y respaldo crudo en `datos/raw/`. Limpieza, EDA con Plotly y validación.
2. **Clasificación** (`02_clasificacion.ipynb`):
   - Línea base zero-shot con `joeddav/xlm-roberta-large-xnli` (40 titulares).
   - Supervisión débil: Gemini (`gemini-3.5-flash-lite`) etiquetó los 360 titulares → `datos/etiquetas_llm.csv`,
     con auditoría humana de 20 predicciones.
   - Split estratificado 70/15/15 (`random_state=42`) y fine-tuning de `distilbert-base-multilingual-cased` con las
     etiquetas del LLM (3 épocas, batch 8, mejor modelo por F1 macro).
   - Evaluación final en el test aislado, contra la categoría de la sección donde se publicó cada noticia.
3. **Dashboard** (`app.py`): exploración de los datos, métricas y un probador del clasificador en vivo.

## Resultados

| Modelo | Evaluado en | Accuracy | F1 macro | Segundos por titular |
|---|---|---|---|---|
| Zero-shot (`xlm-roberta-large-xnli`) | 40 titulares | 0.750 | 0.749 | 1.44 |
| LLM débil (`gemini-3.5-flash-lite`) | Test (54) | 0.963 | 0.964 | 0.14 |
| **Fine-tuned (DistilBERT)** | Test (54) | 0.889 | **0.891** | **0.03** |

Auditoría humana del LLM: **20/20 = 100 %** de acuerdo.

## Hallazgos

1. **La supervisión débil funciona.** El DistilBERT entrenado solo con etiquetas de Gemini, sin ninguna etiqueta
   humana, logra F1 macro 0.891 en test: 0.14 por encima del zero-shot. Además es unas 5 veces más rápido que el LLM y
   unas 46 veces más rápido que el zero-shot, y corre gratis en una laptop sin GPU. No supera al LLM (0.964) porque
   también aprende sus errores.
2. **Los errores se concentran en las fronteras entre temas.** Deportes se clasifica perfecto (F1 1.00) por su
   vocabulario propio, mientras Economía es la más difícil (F1 0.83): se confunde con Política cuando el titular nombra
   a ministros o instituciones. El LLM discrepó de la sección en 23 de 360 titulares (6.4 %); 13 de esos casos son
   entre Ciencia y Tecnología y Economía (El Niño, empresas tecnológicas, minería ilegal): la sección del diario no
   siempre es la única categoría válida.

## Limitaciones técnicas

1. **Datos acotados.** Un solo medio y dos semanas de noticias, con 90 por sección: Deportes cubre solo 3 días
   (9 de sus 90 titulares son sobre el Balón de Oro) y Ciencia y Tecnología 15. El test tiene 54 titulares, así que cada error mueve la
   accuracy casi 2 puntos. Los modelos solo ven el titular, sin la bajada, lo que deja casos ambiguos sin contexto.
2. **Restricciones de hardware y despliegue.** El trabajo se hizo en una Mac Intel sin GPU: la última versión de
   PyTorch para ese equipo es la 2.2.2, que obliga a usar NumPy 1.x y versiones anteriores de pandas, scikit-learn y
   transformers, y el entrenamiento en CPU limita el tamaño del modelo. Además, los pesos del modelo (516 MB) superan
   el límite de GitHub, por lo que no están en el repositorio: hay que reentrenarlo o alojarlo aparte para usar el
   probador.

## Estructura

```
tarea_1/
├── 01_recoleccion.ipynb     # Scraping, limpieza, EDA y exportación
├── 02_clasificacion.ipynb   # Zero-shot, LLM, fine-tuning y evaluación
├── app.py                   # Dashboard interactivo en Streamlit
├── requirements.txt         # Dependencias exactas
├── README.md                # Este reporte
├── .gitignore               # Excluye el entorno, la clave y los archivos pesados
├── .env.example             # Plantilla para GEMINI_API_KEY
├── datos/
│   ├── noticias.csv         # Dataset recolectado (360 filas)
│   ├── etiquetas_llm.csv    # Clasificaciones generadas por el LLM
│   └── raw/                 # Respaldo crudo (solo noticias_crudo.csv se sube a GitHub)
└── modelo/                  # Configuración, tokenizador y resultados del modelo
                             # (los pesos model.safetensors se generan al ejecutar el notebook 02)
```

## Ejecución en local

Requiere Python 3.12.

```bash
git clone https://github.com/SusanMontalvo81/Diplomado-Su-2026.git
cd Diplomado-Su-2026/tarea_1
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

El dashboard se abre en http://localhost:8501.

El **probador en vivo** necesita los pesos del modelo. Para generarlos:

1. Copia `.env.example` como `.env` y coloca tu `GEMINI_API_KEY` (gratis en https://aistudio.google.com/apikey).
   Solo hace falta si se vuelve a etiquetar: el notebook reutiliza `datos/etiquetas_llm.csv`.
2. Ejecuta `02_clasificacion.ipynb` completo (unos 15 minutos en CPU). El modelo se guarda en `modelo/`.

Para volver a recolectar las noticias, ejecuta `01_recoleccion.ipynb`. Ten en cuenta que reemplaza `datos/noticias.csv`
por las noticias más recientes.

## Despliegue

El dashboard está publicado en Streamlit Community Cloud: **https://clasificador-titulares.streamlit.app/**

Se despliega desde este repositorio con esta configuración:

- **Archivo principal:** `tarea_1/app.py` · **Python:** 3.12
- **Modelo:** como los pesos no caben en GitHub, están publicados en Hugging Face:
  https://huggingface.co/SusanSari/clasificador-titulares-elcomercio. Si `modelo/model.safetensors` no existe
  (como en el servidor), el probador descarga el modelo desde ahí.
- **Dependencias:** `requirements.txt` instala en Linux la versión de PyTorch sin GPU, para que la instalación sea
  más liviana.
