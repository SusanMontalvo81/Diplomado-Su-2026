# MCP del BCRP

Proyecto de la sesión 04: un servidor MCP con FastMCP para buscar, consultar y analizar series oficiales del Banco
Central de Reserva del Perú. Esta carpeta forma parte del repositorio `Diplomado-Su-2026`.

## Contenido

| Archivo | Propósito |
|---|---|
| `server.py` | Búsqueda de series, observaciones, resúmenes, comparación de series, recurso y prompt |
| `test_server.py` | Ocho pruebas de contrato con datos reales del BCRP; no modificar |
| `preguntas.csv` | Ocho preguntas iniciales con respuestas y tolerancias oficiales; agregar dos propias |
| `evaluar.py` | Compara respuestas de Claude sin MCP y con el MCP |
| `.mcp.json` | Configura los servidores BCRP y Fetch para Claude Code |
| `pyproject.toml`, `uv.lock` | Dependencias y versiones reproducibles del entorno |

## Requisitos y pruebas

Se necesita Python 3.11 o superior, [`uv`](https://docs.astral.sh/uv/), Claude Code con sesión iniciada e internet.
El entorno local `.venv/` se crea automáticamente con `uv`; el catálogo descargado y el entorno se excluyen de Git.

Desde esta carpeta:

```bash
uv run pytest -q
```

La meta es `8 passed`. La primera ejecución descarga el catálogo oficial del BCRP. Para iniciar el servidor en
terminal, ejecuta `uv run server.py`.

La dependencia `cryptography<49` está acotada para permitir la instalación en macOS Intel sin compilar OpenSSL; el
proyecto no la usa directamente.

## Conectar con Claude Code

Abre Claude Code desde esta carpeta y aprueba los servidores configurados en `.mcp.json` cuando lo solicite. Usa
`/mcp` para comprobar la conexión. El servidor `bcrp` ofrece:

- Herramientas: `buscar_series`, `serie`, `resumen` y `comparar_series`.
- Recurso: `bcrp://serie/{codigo}`; por ejemplo `@bcrp:bcrp://serie/PN01273PM`.
- Prompt: `informe(tema)`, disponible como `/mcp__bcrp__informe`.

Las fechas de `serie` y `resumen` son `YYYY-MM` para series mensuales, `YYYY-T1` para trimestrales, `YYYY-MM-DD` para
diarias y `YYYY` para anuales. Las respuestas incluyen el código y el enlace oficial de la fuente.

## Evaluación y entrega del curso

1. Añade dos preguntas a `preguntas.csv` sobre series que te interesen. Verifica sus valores en
   [estadisticas.bcrp.gob.pe](https://estadisticas.bcrp.gob.pe), no con el propio servidor, y define una tolerancia
   apropiada para redondeo.
2. Desde esta carpeta, ejecuta `uv run evaluar.py`. Se requiere Claude Code disponible en `PATH`; el script guarda
   `resultados.csv`. Para incluir búsqueda web, ejecuta `uv run evaluar.py --modos memoria web mcp`.
3. Escribe `informe.md` con aciertos, errores, respuestas desconocidas y tiempos por modo; analiza los fallos, incluye
   dos cifras verificadas manualmente en la web del BCRP, una figura `grafico.png` y una conclusión breve.
4. Conserva `test_server.py` sin cambios. Entrega `server.py`, `.mcp.json`, `preguntas.csv` con diez preguntas,
   `resultados.csv`, `informe.md` y `grafico.png`. No se incluye `datos/`: se descarga de nuevo automáticamente.

La rúbrica del curso suma 20 puntos: pruebas (6), herramienta propia (3), recurso y prompt (2), `.mcp.json` (2),
evaluación (4) e informe (3).
