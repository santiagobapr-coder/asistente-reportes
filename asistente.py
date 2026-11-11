"""Asistente de reportes: sube un Excel o CSV y recibe un informe en lenguaje claro.

Dos formas de usarlo:
    python asistente.py ejemplo_ventas.xlsx          # genera informe.html
    python asistente.py --servir                     # abre una página local para subir archivos

El análisis es local (reglas + estadística). Opcionalmente, si defines la variable de entorno
ANTHROPIC_API_KEY, el resumen se redacta con un modelo de IA. Solo se envían cifras agregadas,
nunca las filas del archivo.
"""
from __future__ import annotations

import argparse
import calendar
import html
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
import warnings
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dashboard_kit import PALETTE, render_dashboard, table_html, tag

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
PALABRAS_MEDIDA = ["total", "venta", "ingreso", "monto", "valor", "importe", "precio", "costo", "gasto"]


# ----------------------------------------------------------------------------- lectura
def leer(origen, nombre: str) -> pd.DataFrame:
    ext = Path(nombre).suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(origen)
    if ext in (".csv", ".txt"):
        data = origen.read() if hasattr(origen, "read") else Path(origen).read_bytes()
        texto = data.decode("utf-8", errors="replace")
        sep = ";" if texto.count(";") > texto.count(",") else ","
        return pd.read_csv(io.StringIO(texto), sep=sep)
    raise ValueError("Formato no soportado: usa .xlsx o .csv")


def es_texto(s: pd.Series) -> bool:
    return s.dtype == object or pd.api.types.is_string_dtype(s)


def plural(n: int, uno: str, varios: str) -> str:
    return f"{n:,} {uno if n == 1 else varios}"


def col_id(df: pd.DataFrame):
    """Columna que parece un número de pedido, factura o código único."""
    for c in df.columns:
        if re.search(r"(^id\b|pedido|factura|orden|c[oó]digo|n[uú]mero)", str(c).lower()) and df[c].nunique() >= 0.5 * len(df):
            return c
    return None


def moneda(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.0f}"


# ----------------------------------------------------------------------------- detección de columnas
def detectar(df: pd.DataFrame) -> dict:
    fecha = None
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            fecha = col
            break
    if fecha is None:
        for col in df.columns:
            if es_texto(df[col]) or "fecha" in str(col).lower() or "date" in str(col).lower():
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    conv = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
                if conv.notna().mean() > 0.8:
                    fecha = col
                    break
    numericas = [c for c in df.select_dtypes("number").columns if df[c].nunique() < len(df) or len(df) < 5]
    medida = None
    for kw in PALABRAS_MEDIDA:
        medida = next((c for c in numericas if kw in str(c).lower()), None)
        if medida:
            break
    if medida is None and numericas:
        medida = max(numericas, key=lambda c: df[c].sum())
    categorias = [
        c for c in df.columns
        if c not in (fecha, medida) and es_texto(df[c]) and 2 <= df[c].nunique() <= 30
    ]
    return {"fecha": fecha, "medida": medida, "categorias": categorias}


# ----------------------------------------------------------------------------- análisis
def normaliza(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")


def calidad(df: pd.DataFrame, cols: dict) -> list[dict]:
    hallazgos = []
    idc = col_id(df)
    if idc:
        dup = int(df.duplicated(subset=[idc]).sum())
        if dup:
            hallazgos.append({"nivel": "warn", "texto": f"El «{idc}» se repite en {plural(dup, 'fila', 'filas')} ({dup / len(df) * 100:.1f}% del archivo): son duplicados y inflan los totales."})
    else:
        dup = int(df.duplicated().sum())
        if dup:
            hallazgos.append({"nivel": "warn", "texto": f"Hay {plural(dup, 'fila idéntica', 'filas idénticas')} a otra. Sin una columna de número de pedido no puedo saber si son duplicados o ventas iguales; conviene revisarlo."})
    for c in df.columns:
        n = int(df[c].isna().sum())
        if n and n / len(df) >= 0.01:
            hallazgos.append({"nivel": "warn", "texto": f"La columna «{c}» tiene {n:,} celdas vacías ({n / len(df) * 100:.1f}%)."})
    for c in cols["categorias"]:
        vistos = df[c].dropna().astype(str)
        if vistos.nunique() > normaliza(vistos).nunique():
            grupos = vistos.groupby(normaliza(vistos)).agg(lambda x: sorted(set(x)))
            ejemplos = [g for g in grupos if len(g) > 1][:2]
            ej = "; ".join(" / ".join(f"«{v}»" for v in g) for g in ejemplos)
            hallazgos.append({"nivel": "warn", "texto": f"En «{c}» el mismo valor está escrito de varias formas: {ej}. Conviene unificarlos."})
    m = cols["medida"]
    if m:
        neg = int((df[m] < 0).sum())
        if neg:
            hallazgos.append({"nivel": "warn", "texto": f"Hay {neg:,} valores negativos en «{m}» (¿devoluciones o errores?)."})
    if not hallazgos:
        hallazgos.append({"nivel": "good", "texto": "No se detectaron duplicados, vacíos importantes ni escrituras inconsistentes."})
    return hallazgos


def analizar(df: pd.DataFrame) -> dict:
    df = df.copy()
    cols = detectar(df)
    f, m = cols["fecha"], cols["medida"]
    res = {"filas": len(df), "columnas": len(df.columns), "cols": cols, "hallazgos": [], "calidad": calidad(df, cols), "acciones": []}
    if m is None:
        res["hallazgos"].append("No encontré una columna numérica de ventas, ingresos o montos para analizar.")
        return res

    # trabajamos sobre datos sin duplicados exactos para no inflar totales
    idc = col_id(df)
    base = df.drop_duplicates(subset=[idc]) if idc else df
    res["duplicados_quitados"] = len(df) - len(base)
    total = float(base[m].sum())
    res["total"] = total
    h = res["hallazgos"]

    if f:
        base[f] = pd.to_datetime(base[f], errors="coerce", dayfirst=True)
        base = base.dropna(subset=[f])
        ini, fin = base[f].min(), base[f].max()
        h.append(f"El archivo cubre del {ini:%d/%m/%Y} al {fin:%d/%m/%Y}: {len(base):,} registros y un total de «{m}» de {moneda(total)} (sin contar pedidos repetidos).")
        mens = base.set_index(f)[m].resample("MS").sum()
        incompleto = fin.day < calendar.monthrange(fin.year, fin.month)[1]
        completos = mens.iloc[:-1] if incompleto and len(mens) > 1 else mens
        res["mensual"] = mens
        res["mes_incompleto"] = incompleto
        if len(completos) >= 2:
            ult, ant = completos.iloc[-1], completos.iloc[-2]
            var = (ult / ant - 1) * 100 if ant else np.nan
            mu, ma = completos.index[-1], completos.index[-2]
            tendencia = "subió" if var >= 0 else "bajó"
            h.append(f"En {MESES[mu.month - 1]} el total {tendencia} {abs(var):.1f}% frente a {MESES[ma.month - 1]} ({moneda(ult)} contra {moneda(ant)}).")
            res["var_ultimo_mes"] = var
        mejor, peor = completos.idxmax(), completos.idxmin()
        h.append(f"El mejor mes fue {MESES[mejor.month - 1]} ({moneda(completos[mejor])}) y el más bajo {MESES[peor.month - 1]} ({moneda(completos[peor])}).")
        if incompleto:
            h.append(f"El último mes ({MESES[fin.month - 1]}) está incompleto y no se usó en las comparaciones.")
        dias = base.groupby(base[f].dt.weekday)[m].sum()
        nombres = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        res["dias"] = dias
        h.append(f"El día de la semana que más vende es el {nombres[int(dias.idxmax())]} ({dias.max() / dias.sum() * 100:.0f}% del total).")
    else:
        h.append(f"El archivo tiene {len(base):,} registros y un total de «{m}» de {moneda(total)}. No encontré una columna de fechas, así que no analicé tendencias.")

    for c in cols["categorias"][:2]:
        g = base.assign(_k=normaliza(base[c])).groupby("_k")[m].sum().sort_values(ascending=False)
        nombre = base.assign(_k=normaliza(base[c])).groupby("_k")[c].agg(lambda x: x.mode().iat[0] if not x.mode().empty else x.iat[0])
        g.index = [str(nombre[i]).strip().title() for i in g.index]
        res.setdefault("cat", {})[c] = g
        top = g.iloc[0]
        h.append(f"En «{c}», {g.index[0]} concentra el {top / g.sum() * 100:.0f}% del total; los 3 primeros suman {g.head(3).sum() / g.sum() * 100:.0f}%.")

    q1, q3 = base[m].quantile([0.25, 0.75])
    limite = max(q3 + 3 * (q3 - q1), 2 * base[m].quantile(0.995))  # evita marcar ventas altas pero normales
    atip = base[base[m] > limite]
    res["limite_atipico"] = limite
    res["atipicos"] = atip
    if len(atip):
        h.append(f"Hay {plural(len(atip), "registro", "registros")} con valores muy por encima de lo normal (más de {moneda(limite)}); el mayor es {moneda(atip[m].max())}. Vale la pena confirmar que no sean errores de digitación.")

    # acciones sugeridas
    a = res["acciones"]
    if any(("duplicados" in x["texto"] or "idénticas" in x["texto"] or "idéntica" in x["texto"]) for x in res["calidad"]):
        a.append("Revisar y eliminar los pedidos duplicados antes de calcular totales.")
    if any("varias formas" in x["texto"] for x in res["calidad"]):
        a.append("Estandarizar los nombres (mayúsculas, tildes, espacios) en las columnas de categorías.")
    if any("celdas vacías" in x["texto"] for x in res["calidad"]):
        a.append("Completar o justificar las celdas vacías; pueden esconder ventas sin clasificar.")
    if len(atip):
        a.append("Revisar los registros atípicos contra el documento original.")
    if res.get("var_ultimo_mes", 0) < -5:
        a.append("Investigar la caída del último mes completo: producto, canal o ciudad que explica la diferencia.")
    if not a:
        a.append("Los datos están ordenados. El siguiente paso es automatizar este informe para recibirlo cada semana.")
    res["base"] = base
    return res


# ----------------------------------------------------------------------------- redacción opcional con IA
def resumen_con_ia(res: dict) -> str | None:
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        return None
    contexto = {
        "filas": res["filas"],
        "total": res.get("total"),
        "hallazgos": res["hallazgos"],
        "calidad": [c["texto"] for c in res["calidad"]],
    }
    cuerpo = {
        "model": os.environ.get("ASISTENTE_MODELO", "claude-sonnet-5-5"),
        "max_tokens": 400,
        "messages": [{
            "role": "user",
            "content": "Redacta en español, en un párrafo corto y sin tecnicismos, un resumen para el dueño de un negocio "
                       "con estas cifras (no inventes datos):\n" + json.dumps(contexto, ensure_ascii=False),
        }],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(cuerpo).encode(),
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["content"][0]["text"]
    except Exception as e:  # sin red o clave inválida: se usa el resumen local
        print(f"(No se pudo usar la IA: {e}. Se usa el resumen local.)", file=sys.stderr)
        return None


# ----------------------------------------------------------------------------- informe
def construir_informe(res: dict, nombre: str, salida: str) -> str:
    cols, m = res["cols"], res["cols"]["medida"]
    figs_a, figs_b = [], []
    if "mensual" in res:
        mens = res["mensual"]
        fig, ax = plt.subplots(figsize=(7.6, 3.8))
        colores = [PALETTE["primary"]] * len(mens)
        if res.get("mes_incompleto"):
            colores[-1] = PALETTE["muted"]
        ax.bar([f"{MESES[d.month - 1][:3].title()} {str(d.year)[2:]}" for d in mens.index], mens.values / 1e6, color=colores)
        ax.set_ylabel("Millones")
        ax.set_title("Total por mes" + (" (el último, incompleto)" if res.get("mes_incompleto") else ""))
        ax.grid(axis="x", visible=False)
        figs_a.append(fig)
    for c, g in list(res.get("cat", {}).items())[:2]:
        g = g.head(8).sort_values()
        fig, ax = plt.subplots(figsize=(7.6, 3.8))
        ax.barh(g.index, g.values / 1e6, color=PALETTE["accent"])
        ax.set_xlabel("Millones")
        ax.set_title(f"Total por {c}")
        ax.grid(axis="y", visible=False)
        figs_a.append(fig)
    ia = resumen_con_ia(res)
    lista = "".join(f"<li>{html.escape(x)}</li>" for x in res["hallazgos"])
    resumen_html = f'<ul style="line-height:1.7">{lista}</ul>'
    if ia:
        resumen_html = f'<p style="font-size:16px;line-height:1.6">{html.escape(ia)}</p><details><summary>Ver hallazgos detallados</summary>{resumen_html}</details>'
    cal = table_html(["Estado", "Qué encontré"], [[tag("Revisar" if c["nivel"] == "warn" else "Bien", c["nivel"]), html.escape(c["texto"])] for c in res["calidad"]])
    acc = "<ol style='line-height:1.7'>" + "".join(f"<li>{html.escape(x)}</li>" for x in res["acciones"]) + "</ol>"
    sections = [
        {"title": "Resumen para el dueño del negocio", "note": "Lo más importante, en lenguaje claro.", "html": resumen_html},
        {"title": "Gráficos clave", "note": "", "figs": figs_a},
        {"title": "Calidad de los datos", "note": "Lo que conviene corregir antes de confiar en los totales.", "html": cal},
        {"title": "Próximos pasos recomendados", "note": "", "html": acc},
    ]
    kpis = [("Registros", f"{res['filas']:,}"), ("Columnas", str(res["columnas"]))]
    if "total" in res:
        kpis.append((f"Total de «{m}»", f"${res['total'] / 1e6:,.1f} M", "sin pedidos repetidos"))
    if "var_ultimo_mes" in res:
        v = res["var_ultimo_mes"]
        kpis.append(("Último mes completo", f"{v:+.1f}%", "frente al mes anterior", "up" if v >= 0 else "down"))
    kpis.append(("Problemas de calidad", str(sum(1 for c in res["calidad"] if c["nivel"] == "warn"))))
    render_dashboard(salida, "Informe automático de datos", f"Archivo: {nombre}", kpis, sections, footer="Informe generado automáticamente. Revisa las cifras importantes contra tu fuente original.")
    return Path(salida).read_text(encoding="utf-8")


def procesar(origen, nombre: str, salida: str) -> str:
    df = leer(origen, nombre)
    return construir_informe(analizar(df), nombre, salida)


# ----------------------------------------------------------------------------- servidor local
PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asistente de reportes</title>
<style>body{font-family:Inter,'Segoe UI',sans-serif;background:#f5f7fa;color:#1b2a41;margin:0;display:grid;place-items:center;min-height:100vh}
main{background:#fff;border:1px solid #e6e9ef;border-radius:14px;padding:32px;max-width:520px;width:92%}
h1{margin:0 0 6px;font-size:24px}p{color:#6b778c}input[type=file]{margin:16px 0;width:100%}
button{background:#2a6f97;color:#fff;border:0;border-radius:8px;padding:12px 20px;font-size:15px;cursor:pointer}
small{display:block;margin-top:14px;color:#8d99ae}</style>
<main><h1>Asistente de reportes</h1><p>Sube un Excel o CSV de ventas y recibe un informe en lenguaje claro: tendencia, categorías que más pesan, datos atípicos y problemas de calidad.</p>
<form method="post" enctype="multipart/form-data"><input type="file" name="archivo" accept=".xlsx,.xls,.csv" required>
<button>Generar informe</button></form><small>El archivo se procesa en tu computador y no se guarda.</small></main></html>"""


class Manejador(BaseHTTPRequestHandler):
    def _enviar(self, codigo: int, cuerpo: str):
        data = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._enviar(200, PAGINA)

    def do_POST(self):
        try:
            largo = int(self.headers.get("Content-Length", 0))
            msg = BytesParser(policy=HTTP).parsebytes(
                b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + self.rfile.read(largo)
            )
            parte = next(p for p in msg.iter_parts() if p.get_filename())
            nombre, datos = parte.get_filename(), parte.get_payload(decode=True)
            with tempfile.TemporaryDirectory() as tmp:
                informe = procesar(io.BytesIO(datos), nombre, str(Path(tmp) / "informe.html"))
            self._enviar(200, informe)
        except Exception as e:
            self._enviar(400, f"<p style='font-family:sans-serif'>No pude procesar el archivo: {html.escape(str(e))}. <a href='/'>Volver</a></p>")

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo", nargs="?", help="Excel o CSV a analizar")
    ap.add_argument("--salida", default="informe.html")
    ap.add_argument("--servir", action="store_true", help="Levanta una página local para subir archivos")
    ap.add_argument("--puerto", type=int, default=8000)
    a = ap.parse_args()
    if a.servir:
        print(f"Abre http://localhost:{a.puerto} en tu navegador (Ctrl+C para salir)")
        HTTPServer(("127.0.0.1", a.puerto), Manejador).serve_forever()
    elif a.archivo:
        procesar(a.archivo, a.archivo, a.salida)
        print(f"Informe guardado en {a.salida}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
