"""Servidor MCP del BCRP. Empiecen aquí: buscar_series ya funciona; completen los TODO hasta que pasen las pruebas.

    uv run pytest                                           # el contrato: las 8 pruebas deben pasar
    uv run server.py                                        # el servidor, por stdio
    claude mcp add --scope project bcrp -- uv run server.py # conectarlo a Claude Code

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from httpx import HTTPStatusError, RequestError

AQUI = Path(__file__).parent
CATALOGO = AQUI / "datos" / "catalogo_bcrp.csv"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

mcp = FastMCP("bcrp", instructions=(
    "Series oficiales del Banco Central de Reserva del Perú (BCRP). Primero busca el código con buscar_series; "
    "luego usa resumen para variaciones, promedios y extremos, y serie para los datos. No calcules a mano: "
    "cita siempre el código de la serie y el periodo."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    """El catálogo oficial: 17 mil series en unos 7 MB. Se baja una vez y queda en datos/."""
    if not CATALOGO.exists():
        CATALOGO.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_CATALOGO, timeout=120)
        r.raise_for_status()
        CATALOGO.write_text(r.content.decode("latin-1"), encoding="utf-8")
    df = pd.read_csv(CATALOGO, sep=";", dtype=str).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria", "Grupo de serie": "grupo",
                            "Nombre de serie": "nombre", "Frecuencia": "frecuencia",
                            "Fecha de actualización": "actualizada", "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def _ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ToolError(f"No existe el código de serie {codigo!r}. Búsquenlo con buscar_series.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}", "categoria": f.categoria,
            "frecuencia": f.frecuencia, "inicio": f.inicio, "actualizada": f.actualizada}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_series(texto: str, frecuencia: str | None = None, limite: int = 10) -> list[dict]:
    """Busca series del BCRP por palabras: todas deben aparecer en la categoría, el grupo o el nombre.

    Ejemplos: "ipc 12 meses", "tipo de cambio interbancario venta", "reservas internacionales netas",
    "tasa de referencia", "cobre precio". frecuencia: "Diaria", "Mensual", "Trimestral" o "Anual".
    Devuelve el código, el nombre completo, la frecuencia y desde cuándo hay datos. Si no hay resultados,
    prueben con menos palabras.
    """
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    # primero las series vigentes y, entre ellas, las de nombre más corto (las más generales)
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025", largo=(sel.grupo + sel.nombre).str.len())
    return [_ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


# TODO 1 · serie(codigo, desde, hasta) -> {"codigo", "nombre", "frecuencia", "datos": [{"periodo", "valor"}], "fuente"}
#   La API se llama así: f"{API}/{codigo}/json/{desde}/{hasta}" y responde
#   {"config": {...}, "periods": [{"name": "Ene.2025", "values": ["0.81"]}, ...]}
#   - Fechas que pide la API: 2025-1 (mensual y trimestral), 2025-01-15 (diaria), 2025 (anual).
#   - Nombres que devuelve: "Ene.2025" (mensual), "01.Oct.26" (diaria), "T1.25" (trimestral), "2025" (anual).
#     Setiembre viene como "Set". Devuelvan el periodo como "2025-01", "2026-10-01", "2025-T1" o "2025".
#   - Salten los valores "n.d." y usen la frecuencia de _ficha(codigo) para saber qué formato pedir.
#   - Si recibe muchos pedidos seguidos, la API responde una página HTML en vez de JSON: esperen unos segundos y
#     reintenten (y guarden en caché lo que ya bajaron).
#   - Un código que no existe debe dar un ToolError que diga el código.

# TODO 2 · resumen(codigo, desde, hasta): primero, ultimo, cambio, variacion_pct, promedio, maximo y minimo
#   (los tres últimos con su periodo). Úsenla para que el modelo nunca haga cuentas a mano.

# TODO 3 · Una herramienta suya, bien descrita. Ideas:
#   - comparar_paises con la API del Banco Mundial, que tampoco pide clave:
#     https://api.worldbank.org/v2/country/PER;CHL;COL/indicator/NY.GDP.MKTP.KD.ZG?format=json&date=2015:2025
#   - correlacion(codigo_a, codigo_b, desde, hasta)
#   - grafico(codigo, desde, hasta) que guarde un PNG en salidas/ y devuelva la ruta

# TODO 4 · Un recurso, por ejemplo la plantilla bcrp://serie/{codigo} con la ficha de la serie.

# TODO 5 · Un prompt, por ejemplo informe(tema) que pida citar el código y el periodo de cada cifra.


def _fecha_api(fecha: str, frecuencia: str) -> str:
    frecuencia = frecuencia.lower()
    if "diari" in frecuencia:
        try:
            return pd.Timestamp(fecha).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            raise ToolError(f"Fecha diaria inválida: {fecha!r}. Usen YYYY-MM-DD.") from None

    mensual = re.fullmatch(r"(\d{4})-(\d{1,2})", fecha)
    if mensual and "mensual" in frecuencia:
        mes = int(mensual.group(2))
        if not 1 <= mes <= 12:
            raise ToolError(f"Mes inválido en {fecha!r}.")
        return f"{mensual.group(1)}-{mes}"

    trimestral = re.fullmatch(r"(\d{4})-T([1-4])", fecha, re.IGNORECASE)
    if trimestral and "trimestral" in frecuencia:
        return f"{trimestral.group(1)}-{trimestral.group(2)}"

    if re.fullmatch(r"\d{4}", fecha) and "anual" in frecuencia:
        return fecha

    raise ToolError(
        f"Fecha {fecha!r} incompatible con la frecuencia {frecuencia!r}. "
        "Usen YYYY-MM para mensual, YYYY-T1 para trimestral, YYYY-MM-DD para diaria o YYYY para anual."
    )


def _periodo_api(nombre: str, frecuencia: str) -> str:
    frecuencia = frecuencia.lower()
    meses = {
        "ene": "01", "jan": "01", "feb": "02", "mar": "03", "abr": "04",
        "apr": "04", "may": "05", "jun": "06", "jul": "07", "ago": "08",
        "aug": "08", "set": "09", "sep": "09", "oct": "10", "nov": "11",
        "dic": "12", "dec": "12",
    }

    if "diari" in frecuencia:
        match = re.fullmatch(r"(\d{2})\.([A-Za-zÁÉÍÓÚáéíóú]{3})\.(\d{2})", nombre)
        if match:
            dia, mes, anio = match.groups()
            numero_mes = meses.get(mes.lower())
            if numero_mes:
                prefijo_anio = "20" if int(anio) < 69 else "19"
                return f"{prefijo_anio}{anio}-{numero_mes}-{dia}"

    if "mensual" in frecuencia:
        match = re.fullmatch(r"([A-Za-zÁÉÍÓÚáéíóú]{3})\.(\d{4})", nombre)
        if match:
            mes, anio = match.groups()
            numero_mes = meses.get(mes.lower())
            if numero_mes:
                return f"{anio}-{numero_mes}"

    if "trimestral" in frecuencia:
        match = re.fullmatch(r"T([1-4])\.(\d{2})", nombre)
        if match:
            trimestre, anio = match.groups()
            prefijo_anio = "20" if int(anio) < 69 else "19"
            return f"{prefijo_anio}{anio}-T{trimestre}"

    if "anual" in frecuencia and re.fullmatch(r"\d{4}", nombre):
        return nombre
    raise ToolError(f"El BCRP devolvió un periodo no reconocido: {nombre!r}.")


@cache
def _descargar(codigo: str, desde: str, hasta: str, frecuencia: str) -> list[dict]:
    url = f"{API}/{codigo}/json/{desde}/{hasta}"
    for intento in range(3):
        try:
            respuesta = httpx.get(url, timeout=60)
            respuesta.raise_for_status()
            payload = respuesta.json()
        except HTTPStatusError as exc:
            if (exc.response.status_code == 429 or exc.response.status_code >= 500) and intento < 2:
                time.sleep(2 * (intento + 1))
                continue
            raise ToolError(
                f"El BCRP respondió HTTP {exc.response.status_code} al consultar {codigo}."
            ) from exc
        except RequestError as exc:
            if intento < 2:
                time.sleep(2 * (intento + 1))
                continue
            raise ToolError(f"No se pudo consultar la API del BCRP: {exc}") from exc
        except ValueError as exc:
            if intento < 2:
                time.sleep(2 * (intento + 1))
                continue
            raise ToolError("El BCRP no devolvió JSON válido tras tres intentos.") from exc

        periodos = payload.get("periods")
        if not isinstance(periodos, list):
            raise ToolError(f"La respuesta del BCRP no contiene periodos para {codigo}.")

        datos = []
        for periodo in periodos:
            valores = periodo.get("values", [])
            valor = valores[0] if valores else None
            if valor is None or str(valor).strip().lower() in {"", "n.d.", "n.d", "nd"}:
                continue
            try:
                numero = float(str(valor).replace(",", "."))
            except ValueError as exc:
                raise ToolError(
                    f"El BCRP devolvió un valor no numérico para {periodo.get('name')!r}: {valor!r}."
                ) from exc
            datos.append({"periodo": _periodo_api(periodo["name"], frecuencia), "valor": numero})
        return datos

    raise ToolError(f"No se pudieron descargar los datos de la serie {codigo}.")


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Descarga observaciones oficiales de una serie del BCRP entre dos fechas, ambas incluidas.

    Usa YYYY-MM para series mensuales, YYYY-T1 para trimestrales, YYYY-MM-DD para diarias y YYYY para anuales.
    Devuelve los datos, la ficha de la serie y el enlace reproducible a la fuente oficial.
    """
    ficha = _ficha(codigo)
    inicio = _fecha_api(desde, ficha["frecuencia"])
    fin = _fecha_api(hasta, ficha["frecuencia"])
    datos = _descargar(codigo, inicio, fin, ficha["frecuencia"])
    return {
        "codigo": ficha["codigo"],
        "nombre": ficha["nombre"],
        "frecuencia": ficha["frecuencia"],
        "datos": datos,
        "fuente": f"{API}/{codigo}/json/{inicio}/{fin}",
    }


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Calcula estadísticas exactas de una serie: extremos, cambio, variación y promedio del periodo."""
    resultado = serie(codigo, desde, hasta)
    datos = resultado["datos"]
    if not datos:
        raise ToolError(f"No hay observaciones para {codigo} entre {desde} y {hasta}.")

    primero, ultimo = datos[0], datos[-1]
    cambio = ultimo["valor"] - primero["valor"]
    variacion = cambio / primero["valor"] * 100 if primero["valor"] else None
    return {
        "codigo": codigo,
        "nombre": resultado["nombre"],
        "frecuencia": resultado["frecuencia"],
        "periodo": {"desde": primero["periodo"], "hasta": ultimo["periodo"]},
        "primero": primero,
        "ultimo": ultimo,
        "cambio": cambio,
        "variacion_pct": variacion,
        "promedio": sum(p["valor"] for p in datos) / len(datos),
        "maximo": max(datos, key=lambda p: p["valor"]),
        "minimo": min(datos, key=lambda p: p["valor"]),
        "fuente": resultado["fuente"],
    }


@mcp.tool(annotations=SOLO_LECTURA)
def comparar_series(codigo_a: str, codigo_b: str, desde: str, hasta: str) -> dict:
    """Compara dos series por periodos coincidentes y calcula su correlación, sin inferir causalidad."""
    serie_a = serie(codigo_a, desde, hasta)
    serie_b = serie(codigo_b, desde, hasta)
    if serie_a["frecuencia"].lower() != serie_b["frecuencia"].lower():
        raise ToolError("Para comparar series, ambas deben tener la misma frecuencia.")

    valores_b = {p["periodo"]: p["valor"] for p in serie_b["datos"]}
    pares = [
        {"periodo": p["periodo"], "valor_a": p["valor"], "valor_b": valores_b[p["periodo"]]}
        for p in serie_a["datos"]
        if p["periodo"] in valores_b
    ]
    if len(pares) < 2:
        raise ToolError("Se necesitan al menos dos periodos coincidentes para comparar las series.")

    correlacion = pd.Series([p["valor_a"] for p in pares]).corr(
        pd.Series([p["valor_b"] for p in pares])
    )
    return {
        "codigo_a": codigo_a,
        "codigo_b": codigo_b,
        "periodos_coincidentes": len(pares),
        "correlacion": float(correlacion) if pd.notna(correlacion) else None,
        "datos": pares,
        "fuentes": [serie_a["fuente"], serie_b["fuente"]],
        "nota": "La correlación describe asociación; no demuestra causalidad.",
    }


@mcp.resource("bcrp://serie/{codigo}")
def recurso_ficha_serie(codigo: str) -> dict:
    """Devuelve la ficha oficial de una serie por su código."""
    return _ficha(codigo)


@mcp.prompt
def informe(tema: str) -> str:
    """Guía un informe breve con cifras oficiales del BCRP, sus códigos y periodos."""
    return (
        f"Escribe un informe breve sobre {tema}. Busca las series pertinentes y verifica las cifras con serie o "
        "resumen. Cita el código, el periodo, la unidad y el enlace oficial de cada cifra. No infieras causalidad "
        "a partir de correlaciones."
    )


if __name__ == "__main__":
    mcp.run()
