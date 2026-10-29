# Evaluación del MCP del BCRP

## Objetivo y método

El 28 de octubre de 2026 se evaluaron las mismas 10 preguntas en dos modos con Claude Haiku: `memoria`, sin herramientas MCP, y `mcp`, con el servidor BCRP. La ejecución se hizo con `uv run evaluar.py`. Cada respuesta se comparó con el valor oficial de `preguntas.csv` usando su tolerancia; una respuesta nula se clasificó como «no sabe».

## Resultados

| Modo | Acierta | Se equivoca | No sabe | Tiempo promedio por pregunta |
|---|---:|---:|---:|---:|
| Memoria | 0/10 | 0/10 | 10/10 | 10,9 s |
| MCP BCRP | 10/10 | 0/10 | 0/10 | 30,4 s |

Sin MCP, Claude indicó que no podía verificar cifras recientes y no estimó respuestas. Con el MCP, respondió correctamente las 10 preguntas dentro de la tolerancia. En esta medición, las respuestas con MCP tardaron en promedio 19,5 segundos más por pregunta (aproximadamente 2,8 veces el tiempo del modo memoria), consistente con el tiempo adicional de consultar datos externos.

## Verificación manual en el BCRP

Las dos preguntas agregadas se contrastaron directamente en las tablas oficiales de series mensuales:

- **IPC subyacente**, serie `PN01279PM`, setiembre de 2026: **2,85 %** ([tabla oficial del BCRP](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01279PM/html/2025-9/2026-9/)).
- **IPC de alimentos y energía**, serie `PN09819PM`, setiembre de 2026: **4,59 %** ([tabla oficial del BCRP](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN09819PM/html/2025-9/2026-9/)).

Ambos valores se usaron como verdad de referencia con una tolerancia de 0,02 puntos porcentuales.

## Conclusión y límites

En estas 10 preguntas, el MCP permitió obtener datos verificables y acertar todos los valores; sin herramientas, Claude prefirió abstenerse en lugar de inventar cifras. El beneficio observado vino con mayor latencia debido a las consultas al BCRP.

La prueba es pequeña y corresponde a un único modelo y una ejecución por pregunta y modo. No demuestra que el MCP siempre mejore cualquier respuesta ni que todas las series o periodos estén cubiertos. Los resultados detallados están en [`resultados.csv`](./resultados.csv).
