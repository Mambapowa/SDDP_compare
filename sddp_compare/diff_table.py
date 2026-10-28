"""Comparaison des fichiers CSV (entrées et sorties SDDP) comme des tableaux.

Les CSV PSR ont souvent quelques lignes de méta-données avant l'en-tête
(unité, « varie par bloc ? »…). On détecte la ligne d'en-tête, on identifie les
colonnes « clés » (étape, série, bloc, code, nom…) et on compare cellule à cellule.
"""

from __future__ import annotations

import csv
import io
from collections import Counter

import pandas as pd

from .diff_text import diff_text, parse_number
from .models import CellChange, ColumnStat, TableDiff

KEY_NAMES = {
    "stag", "stg", "stage", "estg", "blk", "blq", "pat", "sist", "sys", "bus", "barra", "etapa", "estagio", "étape", "etape", "seq", "seq.", "serie", "série", "series",
    "scenario", "scénario", "cenario", "blck", "block", "bloc", "bloque", "patamar", "date", "data", "fecha",
    "year", "ano", "año", "annee", "année", "month", "mes", "mois", "week", "semana", "day", "dia", "hour",
    "hora", "heure", "code", "codigo", "código", "cod", "id", "num", "number", "name", "nome", "nombre",
    "nom", "system", "sistema", "système", "agent", "agente", "plant", "usina", "planta", "!code", "!name",
}
MAX_KEY_COLS = 6
MAX_TOP_CELLS = 50
MAX_ROW_LIST = 200


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:50])
    counts = {d: sample.count(d) for d in (",", ";", "\t")}
    return max(counts, key=counts.get) if any(counts.values()) else ","


def _parse(text: str):
    delim = _sniff_delimiter(text)
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim)]
    rows = [[c.strip() for c in r] for r in rows]
    non_empty = [r for r in rows if any(r)]
    if len(non_empty) < 2:
        return None
    modal = Counter(len(r) for r in non_empty).most_common(1)[0][0]
    if modal < 2:
        return None
    # La première ligne ayant le nombre de colonnes « normal » est l'en-tête si elle
    # est surtout textuelle ; les lignes avant elle sont des méta-données (préambule).
    first = next(i for i, r in enumerate(rows) if len(r) == modal and any(r))
    cells = [c for c in rows[first] if c]
    is_header = sum(parse_number(c) is None for c in cells) / max(len(cells), 1) >= 0.5
    header_idx = first if is_header else None
    if header_idx is None:
        header = [f"col{k + 1}" for k in range(modal)]
        data, preamble = rows[first:], rows[:first]
    else:
        header = rows[header_idx]
        data, preamble = rows[header_idx + 1:], rows[:header_idx]
    # noms de colonnes uniques
    seen: Counter = Counter()
    cols = []
    for k, h in enumerate(header):
        name = h or f"col{k + 1}"
        seen[name] += 1
        cols.append(name if seen[name] == 1 else f"{name}#{seen[name]}")
    width = len(cols)
    data = [(r + [""] * width)[:width] for r in data if any(r)]
    df = pd.DataFrame(data, columns=cols, dtype=str)
    pre_text = "\n".join(delim.join(r) for r in preamble)
    return df, pre_text


def _key_columns(df: pd.DataFrame) -> list[str]:
    keys = []
    for col in list(df.columns)[:MAX_KEY_COLS]:
        name = col.strip().lower()
        numeric = pd.to_numeric(df[col], errors="coerce").notna().mean() if len(df) else 0
        if name in KEY_NAMES or numeric < 0.5:
            keys.append(col)
        else:
            break
    if len(keys) == len(df.columns):  # tout est « clé » : on garde au moins une colonne de valeurs
        keys = keys[:1]
    if not keys and len(df) > 1:
        # Repli : premières colonnes entières (étape, bloc…) dont la combinaison est unique
        cand = []
        for col in list(df.columns)[:3]:
            v = pd.to_numeric(df[col], errors="coerce")
            if v.isna().any() or not (v == v.round()).all():
                break
            cand.append(col)
            if len(cand) < len(df.columns) and not df[cand].duplicated().any():
                return cand
    return keys


def _index(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if keys:
        if len(keys) == 1:
            key = df[keys[0]].astype(str)
        else:
            key = df[keys].astype(str).apply(lambda r: " · ".join(f"{c}={v}" for c, v in r.items()), axis=1)
    else:
        key = pd.Series([f"ligne {i + 1}" for i in range(len(df))], index=df.index)
    # clés en double : on numérote les occurrences
    occ = key.groupby(key).cumcount()
    key = key.where(occ == 0, key + " #" + (occ + 1).astype(str))
    out = df.copy()
    out.index = key
    return out


def diff_table(text_a: str, text_b: str, tol: float = 1e-9) -> TableDiff | None:
    """Retourne None si le fichier ne ressemble pas à un tableau exploitable."""
    pa, pb = _parse(text_a), _parse(text_b)
    if pa is None or pb is None:
        return None
    df_a, pre_a = pa
    df_b, pre_b = pb
    common_cols = [c for c in df_a.columns if c in set(df_b.columns)]
    if not common_cols:
        return None

    keys = [k for k in _key_columns(df_a) if k in df_b.columns]
    a = _index(df_a, keys)
    b = _index(df_b, keys)

    res = TableDiff(key_columns=keys, n_rows_a=len(a), n_rows_b=len(b))
    set_a, set_b = set(a.index), set(b.index)
    added = [k for k in b.index if k not in set_a]
    removed = [k for k in a.index if k not in set_b]
    res.rows_added = added[:MAX_ROW_LIST]
    res.rows_removed = removed[:MAX_ROW_LIST]
    res.n_rows_added = len(added)
    res.n_rows_removed = len(removed)
    res.cols_added = [c for c in df_b.columns if c not in set(df_a.columns)]
    res.cols_removed = [c for c in df_a.columns if c not in set(df_b.columns)]

    common_rows = [k for k in a.index if k in set_b]
    value_cols = [c for c in common_cols if c not in keys]
    ca = a.loc[common_rows, value_cols]
    cb = b.loc[common_rows, value_cols]

    any_row_changed = pd.Series(False, index=pd.Index(common_rows))
    cells: list[CellChange] = []
    for col in value_cols:
        sa, sb = ca[col], cb[col]
        na = pd.to_numeric(sa, errors="coerce")
        nb = pd.to_numeric(sb, errors="coerce")
        both_num = na.notna() & nb.notna()
        delta = (nb - na)
        changed_num = both_num & (delta.abs() > tol)
        changed_txt = ~both_num & (sa.fillna("") != sb.fillna(""))
        changed = changed_num | changed_txt
        n = int(changed.sum())
        full_a = pd.to_numeric(a[col], errors="coerce")
        full_b = pd.to_numeric(b[col], errors="coerce")
        is_numeric = full_a.notna().mean() > 0.5 if len(full_a) else False
        stat = ColumnStat(column=col, n_changed=n)
        if is_numeric:
            stat.sum_a = float(full_a.sum())
            stat.sum_b = float(full_b.sum())
        if n:
            any_row_changed |= changed.values
            d = delta[changed_num]
            if len(d):
                stat.max_abs_delta = float(d.abs().max())
                rel = (d / na[changed_num].abs()).replace([float("inf"), -float("inf")], float("nan"))
                if rel.notna().any():
                    stat.max_rel_delta = float(rel.abs().max())
            for k in changed[changed].index[:500]:
                dv = float(delta[k]) if bool(both_num[k]) else None
                cells.append(CellChange(str(k), col, sa[k], sb[k], dv))
        if n or stat.sum_a != stat.sum_b:
            res.column_stats.append(stat)
        res.n_cells_changed += n

    res.n_rows_changed = int(any_row_changed.sum())
    cells.sort(key=lambda c: (c.delta is None, -abs(c.delta or 0)))
    res.top_cells = cells[:MAX_TOP_CELLS]
    if pre_a.strip() != pre_b.strip():
        res.preamble = diff_text(pre_a, pre_b, tol)
    return res

