# Tarea 2 · Voces y documentos peruanos

> El reporte completo (pregunta, corpus, resultados, hallazgos, limitaciones y cómo ejecutar) se agrega en la Parte 3.

## Nota de privacidad: seudonimización incompleta en una versión anterior

La versión de `datos/documentos.csv` subida en el commit `1e71c41` (Parte 1, 27/10/2026) tenía una seudonimización **incompleta** en el texto OCR de 6 manuscritos de la partida registral (`doc_009`, `doc_012` a `doc_016`). Los nombres completos sí se habían reemplazado por seudónimos, pero quedaron **15 restos de apellidos** junto a ellos. Eran apellidos mal leídos por el OCR que no coincidían con la lista revisada.

Se corrigió en el commit `1ce2e0a` (Parte 2):

- Se agregaron 19 variantes de nombres a la lista revisada.
- En los manuscritos se reemplaza, además del nombre completo, cada nombre o apellido suelto que se parezca a uno de la lista, y cada palabra con mayúscula pegada a un seudónimo.
- La verificación final, al final de la sección 4 de `02_evaluacion.ipynb`, comprueba los textos publicados de audio y manuscritos con la lista revisada y con el modelo NER.

**La versión válida es la actual.** Las versiones anteriores de `datos/documentos.csv` en el historial de Git no deben usarse ni citarse. La lista de nombres reales (`datos/raw/seudonimizacion/reemplazos.csv`) nunca se subió al repositorio.
