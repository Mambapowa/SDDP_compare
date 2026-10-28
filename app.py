"""Interface web du comparateur de cas SDDP.

Lancement :  streamlit run app.py
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from sddp_compare import build_summary, compare_cases, to_dataframes, to_html
from sddp_compare.models import ADDED, IDENTICAL, MODIFIED, REMOVED

st.set_page_config(page_title="Comparateur SDDP", page_icon="⚖️", layout="wide")
st.title("Comparateur de cas SDDP")
st.caption("Choisissez deux cas (dossiers ou archives .zip) pour obtenir un résumé de leurs différences.")

# ------------------------------------------------------------------ Choix des cas
with st.sidebar:
    st.header("Options")
    tol = st.number_input("Tolérance numérique (écart absolu ignoré)", min_value=0.0, value=1e-6,
                          format="%.1e", help="Deux valeurs dont l'écart est inférieur sont considérées égales.")
    ignore_txt = st.text_area("Fichiers à ignorer (un motif par ligne)", value="*.log\n*.out",
                              help="Ex. : *.csv pour ignorer les résultats, resultats/* pour un sous-dossier.")
    ignore = [l.strip() for l in ignore_txt.splitlines() if l.strip()]
    label_a = st.text_input("Nom du cas A", "")
    label_b = st.text_input("Nom du cas B", "")

mode = st.radio("Source des cas", ["Archives .zip (envoi)", "Dossiers sur ce poste"], horizontal=True)
col_a, col_b = st.columns(2)
path_a = path_b = None
if mode.startswith("Archives"):
    up_a = col_a.file_uploader("Cas A (référence) – .zip", type="zip", key="ua")
    up_b = col_b.file_uploader("Cas B (à comparer) – .zip", type="zip", key="ub")
    if up_a and up_b:
        tmp = Path(st.session_state.setdefault("tmpdir", tempfile.mkdtemp(prefix="sddp_up_")))
        path_a, path_b = tmp / up_a.name, tmp / ("B_" + up_b.name if up_b.name == up_a.name else up_b.name)
        path_a.write_bytes(up_a.getvalue())
        path_b.write_bytes(up_b.getvalue())
        label_a = label_a or Path(up_a.name).stem
        label_b = label_b or Path(up_b.name).stem
else:
    pa = col_a.text_input("Dossier du cas A (référence)", placeholder=r"C:\SDDP\cas_2025")
    pb = col_b.text_input("Dossier du cas B (à comparer)", placeholder=r"C:\SDDP\cas_2026")
    if pa and pb:
        path_a, path_b = Path(pa.strip().strip('"')), Path(pb.strip().strip('"'))

if st.button("Comparer", type="primary", disabled=not (path_a and path_b)):
    bar = st.progress(0.0, text="Analyse…")
    try:
        cmp = compare_cases(path_a, path_b, ignore=ignore, tol=tol, label_a=label_a or None,
                            label_b=label_b or None,
                            progress=lambda i, n, name: bar.progress(i / n, text=f"Analyse de {name} ({i}/{n})"))
    except FileNotFoundError as exc:
        bar.empty()
        st.error(str(exc))
        st.stop()
    bar.empty()
    st.session_state["cmp"] = cmp

cmp = st.session_state.get("cmp")
if not cmp:
    st.stop()

# ------------------------------------------------------------------ Résumé
summary = build_summary(cmp)
st.divider()
st.subheader(f"{cmp.label_a} → {cmp.label_b}")
st.markdown(f"**{summary.headline}**")
m = st.columns(4)
for c, (k, lbl) in zip(m, [(MODIFIED, "Modifiés"), (ADDED, "Ajoutés"), (REMOVED, "Supprimés"),
                           (IDENTICAL, "Identiques")]):
    c.metric(lbl, summary.counts[k])

frames = to_dataframes(cmp, summary)
d1, d2, _ = st.columns([1, 1, 3])
d1.download_button("Télécharger le rapport HTML", to_html(cmp, summary).encode("utf-8"),
                   file_name=f"comparaison_{cmp.label_a}_vs_{cmp.label_b}.html", mime="text/html")
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    for name, df in frames.items():
        df.to_excel(xw, sheet_name=name[:31], index=False)
d2.download_button("Télécharger le détail Excel", buf.getvalue(),
                   file_name=f"comparaison_{cmp.label_a}_vs_{cmp.label_b}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

tab_res, tab_var, tab_files = st.tabs(["Résumé", "Plus fortes variations", "Détail par fichier"])
with tab_res:
    if summary.highlights:
        st.markdown("\n".join(f"- {h}" for h in summary.highlights))
    else:
        st.success("Aucune différence.")
    st.markdown("#### Par catégorie")
    st.dataframe(pd.DataFrame(summary.categories), hide_index=True, width="stretch")

with tab_var:
    if summary.top_changes:
        st.caption("Valeurs numériques dont l'écart relatif est le plus grand, tous fichiers confondus.")
        st.dataframe(pd.DataFrame(summary.top_changes), hide_index=True, width="stretch")
    else:
        st.info("Aucune variation numérique détectée.")

with tab_files:
    f1, f2 = st.columns([2, 3])
    q = f1.text_input("Filtrer par nom ou catégorie")
    statuses = f2.multiselect("Statuts", [MODIFIED, ADDED, REMOVED, IDENTICAL], default=[MODIFIED, ADDED, REMOVED])
    for f in cmp.files:
        if f.status not in statuses:
            continue
        if q and q.lower() not in f"{f.path} {f.category} {f.description}".lower():
            continue
        icon = {MODIFIED: "🟠", ADDED: "🟢", REMOVED: "🔴", IDENTICAL: "⚪"}[f.status]
        with st.expander(f"{icon} {f.path} — {f.category} · {f.summary or f.status}"):
            st.caption(f.description)
            if f.error:
                st.warning(f.error)
            if f.text:
                rows = []
                for lc in f.text.lines:
                    if lc.tokens:
                        rows += [{"Ligne A": lc.line_a, "Ligne B": lc.line_b, "Type": lc.kind, "Élément": lc.key,
                                  "Champ": t.column, "Ancien": t.old, "Nouveau": t.new, "Écart": t.delta,
                                  "Écart %": None if t.rel_delta is None else round(100 * t.rel_delta, 2)}
                                 for t in lc.tokens]
                    else:
                        rows.append({"Ligne A": lc.line_a, "Ligne B": lc.line_b, "Type": lc.kind, "Élément": lc.key,
                                     "Champ": "", "Ancien": lc.text_a or "", "Nouveau": lc.text_b or ""})
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            if f.table:
                t = f.table
                st.caption(f"Colonnes clés : {', '.join(t.key_columns) or 'position'} · "
                           f"{t.n_rows_a} lignes (A) / {t.n_rows_b} lignes (B)")
                if t.column_stats:
                    st.dataframe(pd.DataFrame([vars(s) for s in t.column_stats]).rename(columns={
                        "column": "Colonne", "n_changed": "Valeurs modifiées", "sum_a": "Total A", "sum_b": "Total B",
                        "max_abs_delta": "Écart max", "max_rel_delta": "Écart relatif max"}),
                        hide_index=True, width="stretch")
                if t.top_cells:
                    st.markdown("Principales valeurs modifiées")
                    st.dataframe(pd.DataFrame([vars(c) for c in t.top_cells]).rename(columns={
                        "key": "Ligne (clé)", "column": "Colonne", "old": "Ancien", "new": "Nouveau", "delta": "Écart"}),
                        hide_index=True, width="stretch")
                if t.n_rows_added:
                    st.markdown(f"**Lignes ajoutées ({t.n_rows_added})** : " + " · ".join(t.rows_added[:50]))
                if t.n_rows_removed:
                    st.markdown(f"**Lignes supprimées ({t.n_rows_removed})** : " + " · ".join(t.rows_removed[:50]))
                if t.cols_added or t.cols_removed:
                    st.markdown(f"Colonnes ajoutées : {', '.join(t.cols_added) or '—'} · "
                                f"supprimées : {', '.join(t.cols_removed) or '—'}")
            if f.json:
                st.dataframe(pd.DataFrame([{"Type": c.kind, "Chemin": c.path, "Ancien": str(c.old)[:200],
                                            "Nouveau": str(c.new)[:200]} for c in f.json.changes]),
                             hide_index=True, width="stretch")
