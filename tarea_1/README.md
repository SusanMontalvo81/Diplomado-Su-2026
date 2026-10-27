# Tarea 1 · Recolección, clasificación y dashboard de noticias

## Estructura

```
tarea_1/
├── 01_recoleccion.ipynb     # Scraping, limpieza y EDA
├── 02_clasificacion.ipynb   # Modelado, LLM y evaluación
├── app.py                   # Aplicación interactiva Streamlit
├── requirements.txt         # Dependencias exactas
├── README.md                # Reporte y guía de ejecución
├── .gitignore               # Exclusión de archivos pesados
├── datos/
│   ├── noticias.csv         # Dataset recolectado (350+ filas)
│   └── etiquetas_llm.csv    # Clasificaciones generadas por el LLM
└── modelo/
    └── (configuraciones o artefactos ligeros del modelo)
```

## Guía de ejecución

Requiere Python 3.12.

```bash
cd tarea_1
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # y coloca tu GEMINI_API_KEY
```

1. Ejecutar `01_recoleccion.ipynb` → genera `datos/noticias.csv`.
2. Ejecutar `02_clasificacion.ipynb` → genera `datos/etiquetas_llm.csv`, entrena el modelo y lo guarda en `modelo/`.
3. Lanzar el dashboard:

   ```bash
   streamlit run app.py
   ```

## Reporte

### Fuentes y recolección
_Pendiente._

### Limpieza y EDA
_Pendiente._

### Clasificación con LLM
_Pendiente._

### Evaluación del modelo
_Pendiente._

### Conclusiones
_Pendiente._
