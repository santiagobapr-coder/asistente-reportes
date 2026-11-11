"""Pequeño kit para armar tableros HTML autónomos con matplotlib.

Genera un único archivo .html (gráficos incrustados en base64) que se abre
en cualquier navegador sin instalar nada.
"""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PALETTE = {
    "ink": "#1b2a41",
    "primary": "#2a6f97",
    "accent": "#e07a5f",
    "good": "#3a9d6e",
    "warn": "#e9a23b",
    "bad": "#c8553d",
    "muted": "#8d99ae",
    "grid": "#e6e9ef",
}
SERIES = ["#2a6f97", "#e07a5f", "#3a9d6e", "#e9a23b", "#8d99ae", "#6d597a"]


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": PALETTE["grid"],
            "axes.labelcolor": PALETTE["ink"],
            "axes.titleweight": "bold",
            "axes.titlesize": 12,
            "axes.titlecolor": PALETTE["ink"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": PALETTE["grid"],
            "grid.linewidth": 0.8,
            "xtick.color": PALETTE["muted"],
            "ytick.color": PALETTE["muted"],
            "font.size": 10,
            "axes.prop_cycle": matplotlib.cycler(color=SERIES),
        }
    )


apply_style()


def fig_to_b64(fig, dpi: int = 130) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def money(x: float, symbol: str = "$") -> str:
    signo = "-" if x < 0 else ""
    return f"{signo}{symbol}{abs(x):,.0f}"


CSS = """
:root{--ink:#1b2a41;--muted:#6b778c;--line:#e6e9ef;--bg:#f5f7fa;--card:#fff;--primary:#2a6f97;--good:#3a9d6e;--bad:#c8553d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,'Segoe UI',system-ui,sans-serif;line-height:1.5}
header{background:var(--ink);color:#fff;padding:28px 32px}
header h1{margin:0;font-size:24px}
header p{margin:6px 0 0;color:#c5cddb;font-size:14px}
main{max-width:1180px;margin:0 auto;padding:24px 20px 48px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:24px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.kpi .l{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.kpi .v{font-size:26px;font-weight:700;margin-top:4px}
.kpi .d{font-size:12px;margin-top:2px;color:var(--muted)}
.kpi .d.up{color:var(--good)}.kpi .d.down{color:var(--bad)}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:20px}
section h2{margin:0 0 4px;font-size:17px}
section .note{margin:0 0 14px;color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}
.grid img,section>img{width:100%;height:auto;border-radius:8px}
section>img{max-width:780px;display:block;margin:0 auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em;padding:8px 10px;border-bottom:2px solid var(--line)}
td{padding:8px 10px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600}
.tag.bad{background:#fbe9e5;color:var(--bad)}.tag.warn{background:#fdf1dc;color:#a8700f}.tag.good{background:#e2f4ea;color:var(--good)}
footer{text-align:center;color:var(--muted);font-size:12px;padding:20px}
@media (max-width:520px){.grid{grid-template-columns:1fr}header{padding:20px}}
"""


def table_html(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def tag(text: str, kind: str) -> str:
    return f'<span class="tag {kind}">{html.escape(text)}</span>'


def render_dashboard(
    out_path: str | Path,
    title: str,
    subtitle: str,
    kpis: list[tuple],
    sections: list[dict],
    footer: str = "Datos de ejemplo generados para demostración.",
) -> Path:
    """kpis: (label, value, delta_text|None, 'up'|'down'|'')
    sections: {title, note, figs:[fig,...] , html: str opcional}
    """
    kp = ""
    for k in kpis:
        label, value = k[0], k[1]
        delta = k[2] if len(k) > 2 else None
        kind = k[3] if len(k) > 3 else ""
        d = f'<div class="d {kind}">{html.escape(delta)}</div>' if delta else ""
        kp += (
            f'<div class="kpi"><div class="l">{html.escape(label)}</div>'
            f'<div class="v">{html.escape(str(value))}</div>{d}</div>'
        )
    sec = ""
    for s in sections:
        figs = "".join(
            f'<img alt="{html.escape(s["title"])}" src="data:image/png;base64,{fig_to_b64(f)}">'
            for f in s.get("figs", [])
        )
        grid = f'<div class="grid">{figs}</div>' if len(s.get("figs", [])) > 1 else figs
        sec += (
            f'<section><h2>{html.escape(s["title"])}</h2>'
            f'<p class="note">{html.escape(s.get("note", ""))}</p>{grid}{s.get("html", "")}</section>'
        )
    doc = (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
        f"<header><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></header>"
        f"<main><div class='kpis'>{kp}</div>{sec}</main>"
        f"<footer>{html.escape(footer)}</footer></body></html>"
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return out
