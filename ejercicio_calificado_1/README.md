# Ejercicio calificado 1 · Incendios en el Perú (últimos 60 días)

**Objetivo:** identificar las zonas del Perú más afectadas por incendios de vegetación entre el
29 de agosto y el 27 de octubre de 2026, y caracterizar qué tipo de cobertura se quemó.

## Resultados principales

- **91,954 focos de calor** en el Perú en 60 días; el **96.5 %** sobre vegetación natural.
- **Departamentos más afectados:** Ucayali, San Martín, Huánuco, Loreto y Junín, casi todos sobre bosque amazónico.
- **Distritos más afectados:** Raimondi y Nueva Requena (Ucayali), Puerto Inca (Huánuco), Río Tambo y Mazamari-Pangoa (Junín).
- **Mayor densidad de fuego:** distritos andinos sobre pastizal, como San Pedro de Cachora y Curahuasi (Apurímac) o Sihuas (Áncash).
- **ANP más afectadas:** Sub Cuenca del Cotahuasi, El Sira y Huascarán.
- **Qué se quemó:** 68 % bosque, 26 % pastizal, 2 % matorral, 1.5 % cultivo.

Hay dos paisajes del fuego: en la **selva**, muchos focos sobre lo que en 2021 era bosque (patrón de roza y
quema en la frontera agrícola); en la **sierra**, menos focos pero más concentrados, sobre pastizal.

## Archivos

| Archivo | Contenido |
|---|---|
| `incendios.ipynb` | Descarga, limpieza, cruce con WorldCover, distritos y ANP; rankings; limitaciones |
| `dashboard.html` | Dashboard interactivo: se abre con doble clic en el navegador |
| `dashboard_plantilla.html` | Diseño del dashboard; el notebook le inserta los datos |
| `datos/` | Focos limpios y rankings por distrito, departamento y ANP (CSV) |

## Fuentes

| Dato | Fuente |
|---|---|
| Focos de calor (375 m) | NASA FIRMS — VIIRS S-NPP, NOAA-20 y NOAA-21 (NRT) |
| Cobertura del suelo (10 m) | ESA WorldCover 2021 v200 |
| Límites distritales | INEI, vía dataset del curso en Hugging Face |
| Áreas naturales protegidas | SERNANP (copia publicada en ArcGIS Online) |

## Cómo reproducirlo

1. Pide una MAP_KEY gratuita en https://firms.modaps.eosdis.nasa.gov/api/map_key/
2. Créala en la raíz del repositorio, en un archivo `.env` (está en `.gitignore`):
   ```
   FIRMS_MAP_KEY=tu_clave
   ```
3. Entorno con conda-forge (en Mac Intel, `rasterio` no se instala bien con pip):
   ```bash
   conda create -n raster -c conda-forge python=3.12 rasterio geopandas huggingface_hub matplotlib ipykernel
   ```
4. Ejecuta `incendios.ipynb` de principio a fin. Al terminar, regenera `dashboard.html`.

## Limitaciones

Un foco no es un incendio; WorldCover es de 2021, así que en la selva "bosque" suele ser roza y quema;
VIIRS no ve fuegos pequeños, bajo dosel o con nubes; 60 días no cubren toda la temporada y no hay
comparación con años anteriores. El detalle está al final del notebook y del dashboard.
