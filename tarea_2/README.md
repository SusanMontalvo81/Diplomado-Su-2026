# Tarea 2 · Voces y documentos peruanos

**Dashboard en línea:** https://voces-y-documentos-peruanos.streamlit.app/

## Pregunta del proyecto

**¿Pueden convertirse documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?**

Se extrajo texto de documentos peruanos con OCR y de entrevistas en español peruano con reconocimiento de voz (ASR). Un LLM convirtió cada texto en una ficha con campos estructurados. Cada etapa se evaluó contra transcripciones hechas a mano.

## Corpus, fuentes y licencias

Fecha de extracción: **27 de octubre de 2026**. La fuente, la licencia y la forma de recuperar cada archivo están en `datos/fuentes.csv`.

| Corpus | Cantidad | Fuente | Licencia y uso |
|---|---|---|---|
| Impresos | 8 | Captura propia del PDF de Glave (1999), *Catálogo de periódicos cusqueños del siglo XIX* (UNSAAC, Archivo Departamental del Cusco, CBC), págs. 2–9 | © Derechos reservados. Se publica solo el texto, con fines académicos, y no la imagen |
| Fotos con sombra o inclinación | 8 | Fotos propias con celular del *Registro Oficial del Departamento* (Cusco, 1857–1862) | Impreso en dominio público; fotos propias, CC BY 4.0 |
| Manuscritos | 9 | Captura propia de una copia literal de partida registral (SUNARP, Oficina Registral de Cusco), asientos de 1911 a 1995 | Publicidad registral con datos personales: texto seudonimizado e imagen no publicada |
| Audio | 15 clips | Entrevistas y testimonios de Wikimedia Commons (calle, marchas, fiesta, conferencia) | CC BY-SA 4.0 y CC BY 4.0, con autor y enlace por clip |
| Audio | 6 clips | OpenSLR 73, frases leídas por hablantes de Lima (Guevara-Rukoz et al., 2020) | CC BY-SA 4.0 |

Se descartó 1 clip sin voz (`clip_004`, música de fiesta). Quedan **20 clips y 32,3 minutos**, de los que uno tiene 4 hablantes y varios tienen 2 o más. No hubo documentos duplicados ni ilegibles.

## Metodología

1. **Extracción** (`01_extraccion.ipynb`):
   - OCR con PaddleOCR 3.0.3 (PP-OCRv5 *mobile*, detección a 1600 px y orden de lectura por columnas).
   - ASR con faster-whisper `large-v3-turbo` (int8, CPU, VAD Silero) y diarización con huellas de voz WeSpeaker.
   - Exportación a CSV, SRT y TXT.
   - Seudonimización con NER (`mrm8488/bert-spanish-cased-finetuned-ner`) y revisión humana de la lista de nombres.
2. **Evaluación** (`02_evaluacion.ipynb`):
   - **Muestra y configuraciones:** se fijaron 10 documentos (3 impresos, 3 fotos, 4 manuscritos) y 10 clips (7 fuentes, 5 condiciones) antes de medir. Cada cambio posterior quedó documentado en el notebook con su motivo.
   - **Referencias:** transcripciones manuales propias. En documentos, de un fragmento fijo (la parte superior de cada página).
   - **Métricas:** CER y WER con la misma normalización para la referencia y para el modelo: sin marcas de hablante, sin tildes y con los números en palabras.
   - **Modelos comparados:** 3 OCR (PaddleOCR por defecto como línea base, PaddleOCR ajustado y Tesseract 5.5) y 3 ASR (Whisper `small` como línea base, Whisper `large-v3-turbo` y Qwen3-ASR 0.6B).
3. **Extracción estructurada:**
   - Gemini 3.5 Flash con un esquema JSON fijo, aplicado a los 45 textos ya seudonimizados (`datos/extraccion_llm.csv`).
   - Auditoría manual de 20 fichas sorteadas (`datos/auditoria_llm.csv`).

## Resultados

Se evaluaron los mismos 10 documentos y 10 clips. Todo corrió en CPU, en un Intel i5 de 2 núcleos.

| Modalidad | Modelo | Error | Latencia |
|---|---|---|---|
| Documentos | PaddleOCR por defecto (línea base) | CER 0.417 | 65 s/doc |
| Documentos | PaddleOCR ajustado | **CER 0.352** | 32 s/doc |
| Documentos | Tesseract 5.5 | CER 0.379 | **1,5 s/doc** |
| Audio | Whisper `small` (línea base) | WER 0.320 | **RTF 0.53** |
| Audio | Whisper `large-v3-turbo` | **WER 0.302** | RTF 1.82 |
| Audio | Qwen3-ASR 0.6B | WER 0.379 | RTF 0.95 |

**Acuerdo LLM-humano:** 17 de 20 fichas completamente correctas (85 %). El tema y el resumen fueron correctos en las 20.

**Decisión para un entorno real:**
- **Whisper `small` para audio.** Pierde 2 puntos de WER frente a turbo y es 3,4 veces más rápido.
- **Tesseract para documentos.** Es unas 20 veces más rápido que PaddleOCR y mejor en las fotos de periódico. Para los manuscritos conviene PaddleOCR ajustado.

```
Resultados Test: WER: 0.32 | CER: 0.38 | Acuerdo LLM-Humano: 17/20
```

## Hallazgos

1. **La condición del material pesa más que el modelo.**
   - **Documentos:** en los impresos modernos el CER es 0.01. En las fotos con sombra sube a 0.24–0.48 y en los manuscritos a 0.49–0.67.
   - **Audio:** el WER va de 0.04 en la lectura de estudio a 0.14–0.34 en la calle y los testimonios, y a 0.40–0.52 en marchas y fiestas.
   - En los dos casos, el peor tipo de material multiplica el error frente al mejor, mientras que los modelos difieren solo en pocos puntos entre sí.
2. **El modelo más grande o más lento no compensa.**
   - Whisper `large-v3-turbo` apenas mejora a `small` (0.30 frente a 0.32) y tarda casi el doble de lo que dura el audio. Además, **alucinó** la palabra "listo" 23 veces en el silencio final de un clip, aunque el VAD estaba activado.
   - PaddleOCR con su configuración por defecto (orientación y desdoblado de página incluidos) fue el peor y el más lento: CER 0.42 y 65 s por documento, frente a 0.35 y 32 s con la configuración ajustada.
   - En las fotos de periódico, Paddle **mezcla las dos columnas** y no lee los títulos decorativos, mientras que Tesseract las separa.
3. **El LLM tolera el ruido del OCR, pero eso lo lleva a errores puntuales.** Gemini captó bien el tema y el resumen incluso en manuscritos con CER cercano a 0.5, porque reconoce palabras deformadas y el "molde" de los documentos registrales. Sus errores típicos están en los campos puntuales:
   - **descifra o recorta** datos deformados: dejó un año incompleto;
   - **no distingue** el texto principal de una anotación al margen: tomó la fecha de la anotación;
   - **fuerza una sola ficha** en páginas que reúnen varios documentos: eligió el emisor y el monto de uno solo de varios decretos;
   - es **inconsistente** con los errores del OCR: a veces los copia ("LS57" por 1857) y a veces los corrige.

   Además, **el LLM puede deshacer la seudonimización**. Reconstruyó el nombre completo de un notario a partir de restos deformados del OCR, y agregó al resumen de un audio un nombre que no estaba en la transcripción. Por eso sus fichas también se seudonimizan antes de publicarse.

   Para un archivo buscable convendría una ficha por documento, y no por página, y separar la *fecha de publicación* de la *fecha del hecho*. Además, la auditoría mostró que la diarización subestima el número de voces cuando el entrevistador solo hace preguntas breves.

## Limitaciones técnicas

1. **Muestra de evaluación pequeña y referencias parciales.**
   - Por el costo de transcribir a mano, en documentos se evalúa un fragmento de unas 70 palabras por página. Ese fragmento tiene más títulos y encabezados que una página promedio.
   - Dentro de cada tipo se eligieron los documentos y audios más cortos.
   - En los audios con ruido, las referencias pueden omitir voces de fondo o preguntas del entrevistador, lo que sube el WER de los tres modelos por igual.
   - Las métricas comparan bien los modelos entre sí, pero sus valores absolutos son aproximados.
2. **Hardware y compatibilidad.**
   - Todo corrió en una Mac Intel sin GPU. En ella, PaddlePaddle 3.0.0 es la última versión que funciona, y sus modelos *server* se caían o tardaban más de 10 minutos por página, así que se usaron los *mobile*.
   - La línea base de Paddle se cortaba de forma intermitente y hubo que procesar cada documento en su propio proceso.
   - faster-whisper y torch no pueden convivir en el mismo proceso: el NER y Qwen corren aparte.
   - La cuota gratuita de Gemini (20 solicitudes diarias por modelo) obligó a cambiar de modelo y a enviar 3 textos por solicitud.

## Privacidad y seudonimización

- Los nombres de personas privadas que aparecen en los audios y en los manuscritos (entrevistados, entrevistadores, propietarios, notarios y registradores) se reemplazan por `PERSONA_xx`. La lista se armó con NER y revisión humana.
- Los impresos y los periódicos son publicaciones públicas o históricas y no se seudonimizan.
- La lista de nombres reales (`datos/raw/seudonimizacion/reemplazos.csv`) nunca se sube al repositorio.
- El dashboard solo muestra las imágenes de las fotos del periódico y los audios en los que nadie dice un nombre (`datos/ejemplos/`, generado con `preparar_ejemplos.py`).

### Nota: seudonimización incompleta en una versión anterior

La versión de `datos/documentos.csv` subida en el commit `1e71c41` (Parte 1, 27/10/2026) tenía una seudonimización **incompleta** en el texto OCR de 6 manuscritos de la partida registral (`doc_009`, `doc_012` a `doc_016`). Los nombres completos sí se habían reemplazado por seudónimos, pero quedaron **15 restos de apellidos** junto a ellos. Eran apellidos mal leídos por el OCR que no coincidían con la lista revisada.

Se corrigió en el commit `1ce2e0a` (Parte 2):

- Se agregaron 19 variantes de nombres a la lista revisada.
- En los manuscritos se reemplaza, además del nombre completo, cada nombre o apellido suelto que se parezca a uno de la lista, y cada palabra con mayúscula pegada a un seudónimo.
- La verificación final, al final de la sección 4 de `02_evaluacion.ipynb`, comprueba los textos publicados de audio y manuscritos con la lista revisada y con el modelo NER.

**La versión válida es la actual.** Las versiones anteriores de `datos/documentos.csv` en el historial de Git no deben usarse ni citarse.

### Nota: fichas del LLM sin seudonimizar en versiones anteriores

Las versiones de `datos/extraccion_llm.csv` subidas entre los commits `6f86e11` y `92383ef` (28/10/2026) publicaban la salida de Gemini sin seudonimizar. Contenían dos nombres:
- en `doc_014`, el nombre completo de un notario, que Gemini reconstruyó a partir de restos deformados del OCR;
- en `clip_003`, un nombre que Gemini agregó al resumen y que no está en la transcripción.

Desde el commit siguiente, `02_evaluacion.ipynb` seudonimiza las fichas de audios y manuscritos antes de guardarlas, y la verificación final también las revisa. Las versiones anteriores de ese archivo no deben usarse ni citarse.

## Estructura

```
tarea_2/
├── 01_extraccion.ipynb       # OCR, ASR, diarización, seudonimización, limpieza y EDA
├── 02_evaluacion.ipynb       # CER/WER, comparación de modelos, LLM, auditoría y decisión
├── app.py                    # Dashboard en Streamlit (solo lee los CSV)
├── requirements.txt          # Dependencias del dashboard
├── .env.example              # Plantilla para GEMINI_API_KEY
├── voz.py                    # Utilidades de audio de la Sesión 13 (VAD, ASR, diarización, seudonimización)
├── metricas.py               # Normalización y CER/WER de la Parte 2
├── descargar_audio.py · preparar_documentos.py           # Corpus
├── ocr_corpus.py · asr_corpus.py · ner_personas.py       # Extracción (Parte 1)
├── recortar_muestra.py · evaluar_asr.py · extraer_llm.py · preparar_auditoria.py   # Evaluación (Parte 2)
├── preparar_ejemplos.py      # Imágenes y audios publicables para el dashboard
├── evidencias_ia/            # Capturas de la conversación con Claude Code
└── datos/
    ├── documentos.csv · transcripciones.csv · fuentes.csv · extraccion_llm.csv
    ├── evaluacion_ocr.csv · evaluacion_asr.csv · auditoria_llm.csv · metricas_*.csv
    ├── ejemplos/             # Fotos y audios publicables
    └── raw/                  # Corpus original, salidas pesadas y referencias (no se sube a GitHub)
```

## Ejecución en local

### Dashboard
Requiere Python 3.12.

```bash
git clone https://github.com/susan-montalvo/Diplomado-Su-2026.git
cd Diplomado-Su-2026/tarea_2
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

El dashboard se abre en http://localhost:8501. No necesita modelos ni claves: lee los CSV de `datos/`.

**Despliegue:** Streamlit Community Cloud, desde este repositorio, con archivo principal `tarea_2/app.py` y Python 3.12. Usa el mismo `requirements.txt` y no necesita secretos.

### Notebooks
Los notebooks se entregan ejecutados. Para volver a correrlos se necesitan el corpus original y dos entornos:

1. **OCR** (Mac Intel, Python 3.12):
   ```bash
   uv venv .venv-ocr --python 3.12
   uv pip install --python .venv-ocr paddlepaddle==3.0.0 paddleocr==3.0.3 paddlex==3.0.3 tesserocr==2.9.1 --only-binary cryptography
   ```
   Hay que fijar `paddlex`: las versiones nuevas fallan con PaddlePaddle 3.0. El modelo `spa` de Tesseract se descarga con el comando del docstring de `ocr_corpus.py`.
2. **Audio y análisis:** el grupo `audio` del repositorio del curso (`uv sync --group audio`), con faster-whisper 1.2.1, pyannote.audio 4.0.7, transformers 5.20, jiwer, rapidfuzz, num2words y google-genai, registrado como kernel de Jupyter.

Orden de ejecución:
1. `python descargar_audio.py`, que descarga el audio de Commons y OpenSLR.
2. `01_extraccion.ipynb`.
3. `python extraer_llm.py`, que necesita `GEMINI_API_KEY` en `.env`; usa `.env.example` como plantilla.
4. `02_evaluacion.ipynb`.

Las referencias manuales y la lista de nombres no están en el repositorio.
