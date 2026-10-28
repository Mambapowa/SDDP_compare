"""Export des résultats : HTML autonome, Excel et Markdown."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .models import ADDED, IDENTICAL, MODIFIED, REMOVED, CaseComparison, FileDiff  # noqa: F401
from .summary import Summary, _fmt, build_summary

MAX_HTML_ROWS = 400


def _e(v) -> str:
    if isinstance(v, float):
        v = _fmt(v)
    return html.escape("" if v is None else str(v))


def _short(v, n: int = 120) -> str:
    s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    return s if len(s) <= n else s[:n] + "…"


# ---------------------------------------------------------------- HTML

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e3e2dc;--accent:#1f5fbf;
--mod:#b26b00;--mod-bg:#fff4e0;--add:#1d7a3a;--add-bg:#e6f5ea;--rem:#b3261e;--rem-bg:#fdeceb;--code:#f0efea}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#1f1f1e;--fg:#ecebe6;
--muted:#a3a29b;--line:#363633;--accent:#7aa7ff;--mod:#f0b45a;--mod-bg:#3a2c14;--add:#6fd08c;--add-bg:#173022;
--rem:#ff8a80;--rem-bg:#3a1a18;--code:#2a2a28}}
:root[data-theme="dark"]{--bg:#161615;--card:#1f1f1e;--fg:#ecebe6;--muted:#a3a29b;--line:#363633;--accent:#7aa7ff;
--mod:#f0b45a;--mod-bg:#3a2c14;--add:#6fd08c;--add-bg:#173022;--rem:#ff8a80;--rem-bg:#3a1a18;--code:#2a2a28}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1200px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 12px}
.sub{color:var(--muted);font-size:13px}.headline{font-size:17px;margin:16px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.kpi b{display:block;font-size:26px;font-variant-numeric:tabular-nums}.kpi span{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 0;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;white-space:nowrap}tr:last-child td{border-bottom:0}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
.mono{white-space:pre;background:var(--code);padding:1px 4px;border-radius:4px}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600}
.b-modifié{color:var(--mod);background:var(--mod-bg)}.b-ajouté,.b-ajoutée{color:var(--add);background:var(--add-bg)}
.b-supprimé,.b-supprimée{color:var(--rem);background:var(--rem-bg)}.b-modifiée{color:var(--mod);background:var(--mod-bg)}
.b-identique{color:var(--muted);background:var(--code)}
ul.hl{padding-left:20px}ul.hl li{margin:4px 0}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:8px 0}
summary{cursor:pointer;padding:10px 14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
summary .path{font-weight:600}summary .desc{color:var(--muted);font-size:13px}
.fbody{padding:0 14px 14px;overflow-x:auto}.fbody h4{margin:12px 0 6px;font-size:14px}
.old{color:var(--rem)}.new{color:var(--add)}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.toolbar input{flex:1;min-width:200px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;
background:var(--card);color:var(--fg)}
.toolbar label{display:flex;gap:4px;align-items:center;font-size:13px;color:var(--muted)}
.note{color:var(--muted);font-size:13px;margin:6px 0}
"""

JS = """
const q=document.getElementById('q'),showId=document.getElementById('showid');
function apply(){const t=q.value.toLowerCase();document.querySelectorAll('details.file').forEach(d=>{
const okT=!t||d.dataset.search.includes(t);const okS=showId.checked||d.dataset.status!=='identique';
d.style.display=okT&&okS?'':'none';});}
q.addEventListener('input',apply);showId.addEventListener('change',apply);apply();
"""


def _table(headers: list[str], rows: list[list], num_cols: set[int] = frozenset()) -> str:
    out = ["<table><thead><tr>", *[f"<th>{_e(h)}</th>" for h in headers], "</tr></thead><tbody>"]
    for r in rows:
        out.append("<tr>" + "".join(
            f"<td class='num'>{c}</td>" if i in num_cols else f"<td>{c}</td>" for i, c in enumerate(r)) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _file_html(f: FileDiff, cmp: CaseComparison) -> str:
    parts = []
    if f.error:
        parts.append(f"<p class='note'>⚠ {_e(f.error)}</p>")
    if f.text:
        t = f.text
        rows = []
        for lc in t.lines[:MAX_HTML_ROWS]:
            if lc.kind == "modifiée":
                for tk in lc.tokens:
                    rel = f"{tk.rel_delta:+.1%}" if tk.rel_delta is not None else ""
                    rows.append([_e(lc.line_a), _e(lc.line_b), f"<span class='badge b-modifiée'>modifiée</span>",
                                 _e(lc.key), _e(tk.column), f"<span class='old'>{_e(tk.old)}</span>",
                                 f"<span class='new'>{_e(tk.new)}</span>", _e(tk.delta), rel])
            else:
                txt = lc.text_b if lc.kind == "ajoutée" else lc.text_a
                rows.append([_e(lc.line_a), _e(lc.line_b), f"<span class='badge b-{lc.kind}'>{lc.kind}</span>",
                             _e(lc.key), "", f"<span class='mono'>{_e(txt)}</span>", "", "", ""])
        parts.append(_table([f"Ligne {cmp.label_a}", f"Ligne {cmp.label_b}", "Type", "Élément", "Champ",
                             "Ancien / contenu", "Nouveau", "Écart", "Écart %"], rows, {0, 1, 7, 8}))
        if len(t.lines) > MAX_HTML_ROWS or t.truncated:
            parts.append("<p class='note'>Liste tronquée : voir l'export Excel pour le détail complet.</p>")
    if f.table:
        tb = f.table
        parts.append(f"<p class='note'>Colonnes clés : {_e(', '.join(tb.key_columns) or 'position de la ligne')} · "
                     f"{tb.n_rows_a} lignes dans {_e(cmp.label_a)}, {tb.n_rows_b} dans {_e(cmp.label_b)}</p>")
        if tb.column_stats:
            rows = []
            for s in tb.column_stats:
                rel = f"{s.max_rel_delta:.1%}" if s.max_rel_delta is not None else ""
                total = ""
                if s.sum_a is not None and s.sum_b is not None:
                    total = f"{_e(s.sum_a)} → {_e(s.sum_b)}"
                rows.append([_e(s.column), s.n_changed, total, _e(s.max_abs_delta), rel])
            parts.append("<h4>Colonnes</h4>" + _table(
                ["Colonne", "Valeurs modifiées", f"Total {cmp.label_a} → {cmp.label_b}", "Écart max", "Écart rel. max"],
                rows, {1, 3, 4}))
        if tb.top_cells:
            rows = [[_e(c.key), _e(c.column), f"<span class='old'>{_e(c.old)}</span>",
                     f"<span class='new'>{_e(c.new)}</span>", _e(c.delta)] for c in tb.top_cells]
            parts.append("<h4>Principales valeurs modifiées</h4>" +
                         _table(["Ligne (clé)", "Colonne", "Ancien", "Nouveau", "Écart"], rows, {4}))
        for title, items, n in (("Lignes ajoutées", tb.rows_added, tb.n_rows_added),
                                ("Lignes supprimées", tb.rows_removed, tb.n_rows_removed)):
            if n:
                more = f" (et {n - len(items)} autres)" if n > len(items) else ""
                parts.append(f"<h4>{title} ({n})</h4><p class='mono' style='white-space:pre-wrap'>"
                             f"{_e(' · '.join(items[:60]))}{more}</p>")
        if tb.cols_added or tb.cols_removed:
            parts.append(f"<p>Colonnes ajoutées : {_e(', '.join(tb.cols_added) or '—')} · "
                         f"supprimées : {_e(', '.join(tb.cols_removed) or '—')}</p>")
        if tb.preamble and tb.preamble.lines:
            rows = [[_e(lc.kind), f"<span class='mono'>{_e(lc.text_a or '')}</span>",
                     f"<span class='mono'>{_e(lc.text_b or '')}</span>"] for lc in tb.preamble.lines[:50]]
            parts.append("<h4>En-tête du fichier</h4>" + _table(["Type", cmp.label_a, cmp.label_b], rows))
    if f.json:
        rows = [[f"<span class='badge b-{c.kind}'>{c.kind}</span>", f"<code>{_e(c.path)}</code>",
                 f"<span class='old'>{_e(_short(c.old)) if c.old is not None else ''}</span>",
                 f"<span class='new'>{_e(_short(c.new)) if c.new is not None else ''}</span>"]
                for c in f.json.changes[:MAX_HTML_ROWS]]
        parts.append(_table(["Type", "Chemin", "Ancien", "Nouveau"], rows))
        if len(f.json.changes) > MAX_HTML_ROWS or f.json.truncated:
            parts.append("<p class='note'>Liste tronquée : voir l'export Excel.</p>")
    return "".join(parts) or f"<p class='note'>{_e(f.summary)}</p>"


def to_html(cmp: CaseComparison, summary: Summary | None = None) -> str:
    s = summary or build_summary(cmp)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    kpi = "".join(f"<div class='kpi'><b>{s.counts[k]}</b><span>fichiers {k}s</span></div>"
                  for k in (MODIFIED, ADDED, REMOVED, IDENTICAL))
    cat_rows = [[_e(c["catégorie"]), c["modifiés"], c["ajoutés"], c["supprimés"], c["identiques"],
                 _e(c["fichiers concernés"])] for c in s.categories]
    top_rows = [[_e(t["fichier"]), _e(t["élément"]), _e(t["champ"]), f"<span class='old'>{_e(t['ancien'])}</span>",
                 f"<span class='new'>{_e(t['nouveau'])}</span>", _e(t["écart"]), _e(t["écart %"])]
                for t in s.top_changes]
    order = {MODIFIED: 0, ADDED: 1, REMOVED: 2, IDENTICAL: 3}
    files_html = []
    for f in sorted(cmp.files, key=lambda f: (order[f.status], f.category, f.path)):
        body = _file_html(f, cmp) if f.status == MODIFIED else f"<p class='note'>{_e(f.summary)}</p>"
        search = html.escape(f"{f.path} {f.category} {f.description} {f.summary}".lower(), quote=True)
        files_html.append(
            f"<details class='file' data-status='{f.status}' data-search='{search}'>"
            f"<summary><span class='badge b-{f.status}'>{f.status}</span><span class='path'>{_e(f.path)}</span>"
            f"<span class='desc'>{_e(f.category)} · {_e(f.description)} — {_e(f.summary) or 'aucune différence'}</span>"
            f"</summary><div class='fbody'>{body}</div></details>")

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Comparaison SDDP</title>
<style>{CSS}</style></head><body><main>
<h1>Comparaison de cas SDDP</h1>
<div class="sub">A : <b>{_e(cmp.label_a)}</b> ({_e(cmp.case_a)}) · B : <b>{_e(cmp.label_b)}</b> ({_e(cmp.case_b)}) · {now}
· tolérance numérique {_e(cmp.options.get('tolérance'))}</div>
<p class="headline">{_e(s.headline)}</p>
<div class="kpis">{kpi}</div>
<h2>Résumé des différences</h2>
{"<ul class='hl'>" + "".join(f"<li>{_e(h)}</li>" for h in s.highlights) + "</ul>" if s.highlights else "<p>Aucune différence.</p>"}
<h2>Par catégorie</h2><div class="card">{_table(["Catégorie", "Modifiés", "Ajoutés", "Supprimés", "Identiques", "Fichiers concernés"], cat_rows, {1, 2, 3, 4})}</div>
{"<h2>Plus fortes variations relatives</h2><div class='card'>" + _table(["Fichier", "Élément", "Champ", "Ancien", "Nouveau", "Écart", "Écart %"], top_rows, {5, 6}) + "</div>" if top_rows else ""}
<h2>Détail par fichier</h2>
<div class="toolbar"><input id="q" placeholder="Filtrer (nom de fichier, catégorie…)">
<label><input type="checkbox" id="showid"> afficher les fichiers identiques</label></div>
{''.join(files_html)}
</main><script>{JS}</script></body></html>"""


# ---------------------------------------------------------------- Excel / DataFrames

def to_dataframes(cmp: CaseComparison, summary: Summary | None = None) -> dict[str, pd.DataFrame]:
    s = summary or build_summary(cmp)
    resume = pd.DataFrame({"Résumé": [s.headline, ""] + s.highlights})
    fichiers = pd.DataFrame([{
        "Fichier": f.path, "Catégorie": f.category, "Description": f.description, "Statut": f.status,
        "Type": f.kind, f"Taille {cmp.label_a} (o)": f.size_a, f"Taille {cmp.label_b} (o)": f.size_b,
        "Nb différences": f.n_changes, "Résumé": f.summary, "Erreur": f.error or "",
    } for f in cmp.files])
    lignes = []
    for f in cmp.files:
        if f.text:
            for lc in f.text.lines:
                if lc.tokens:
                    for t in lc.tokens:
                        lignes.append({"Fichier": f.path, "Type": lc.kind, f"Ligne {cmp.label_a}": lc.line_a,
                                       f"Ligne {cmp.label_b}": lc.line_b, "Élément": lc.key, "Champ": t.column,
                                       "Ancien": t.old, "Nouveau": t.new, "Écart": t.delta, "Écart relatif": t.rel_delta})
                else:
                    lignes.append({"Fichier": f.path, "Type": lc.kind, f"Ligne {cmp.label_a}": lc.line_a,
                                   f"Ligne {cmp.label_b}": lc.line_b, "Élément": lc.key, "Champ": "",
                                   "Ancien": lc.text_a, "Nouveau": lc.text_b, "Écart": None, "Écart relatif": None})
    colonnes, cellules, json_rows = [], [], []
    for f in cmp.files:
        if f.table:
            for st in f.table.column_stats:
                colonnes.append({"Fichier": f.path, "Colonne": st.column, "Valeurs modifiées": st.n_changed,
                                 f"Total {cmp.label_a}": st.sum_a, f"Total {cmp.label_b}": st.sum_b,
                                 "Écart max": st.max_abs_delta, "Écart relatif max": st.max_rel_delta})
            for c in f.table.top_cells:
                cellules.append({"Fichier": f.path, "Ligne (clé)": c.key, "Colonne": c.column,
                                 "Ancien": c.old, "Nouveau": c.new, "Écart": c.delta})
            for k in f.table.rows_added:
                cellules.append({"Fichier": f.path, "Ligne (clé)": k, "Colonne": "(ligne ajoutée)"})
            for k in f.table.rows_removed:
                cellules.append({"Fichier": f.path, "Ligne (clé)": k, "Colonne": "(ligne supprimée)"})
        if f.json:
            for c in f.json.changes:
                json_rows.append({"Fichier": f.path, "Chemin": c.path, "Type": c.kind,
                                  "Ancien": _short(c.old, 500) if c.old is not None else "",
                                  "Nouveau": _short(c.new, 500) if c.new is not None else ""})
    out = {"Résumé": resume, "Fichiers": fichiers}
    if s.categories:
        out["Catégories"] = pd.DataFrame(s.categories)
    if s.top_changes:
        out["Variations"] = pd.DataFrame(s.top_changes)
    if lignes:
        out["Détail fichiers texte"] = pd.DataFrame(lignes)
    if colonnes:
        out["CSV - colonnes"] = pd.DataFrame(colonnes)
    if cellules:
        out["CSV - valeurs"] = pd.DataFrame(cellules)
    if json_rows:
        out["JSON"] = pd.DataFrame(json_rows)
    return out


def to_excel(cmp: CaseComparison, path: str | Path, summary: Summary | None = None) -> Path:
    path = Path(path)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in to_dataframes(cmp, summary).items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
            ws = xw.sheets[name[:31]]
            for col in ws.columns:
                width = max((len(str(c.value)) for c in col[:200] if c.value is not None), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 8), 80)
            ws.freeze_panes = "A2"
    return path


# ---------------------------------------------------------------- Markdown (console)

def to_markdown(cmp: CaseComparison, summary: Summary | None = None, max_items: int = 15) -> str:
    s = summary or build_summary(cmp)
    lines = [f"# Comparaison SDDP : {cmp.label_a} → {cmp.label_b}", "", s.headline, ""]
    if s.highlights:
        lines += ["## Résumé des différences", ""] + [f"- {h}" for h in s.highlights] + [""]
    if s.top_changes:
        lines += ["## Plus fortes variations relatives", "",
                  "| Fichier | Élément | Champ | Ancien | Nouveau | Écart % |", "|---|---|---|---|---|---|"]
        lines += [f"| {t['fichier']} | {t['élément']} | {t['champ']} | {t['ancien']} | {t['nouveau']} | {t['écart %']} |"
                  for t in s.top_changes[:max_items]]
    return "\n".join(lines) + "\n"
