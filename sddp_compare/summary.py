"""Synthèse lisible d'une comparaison : chiffres clés, catégories, principales variations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .diff_text import parse_number
from .models import ADDED, IDENTICAL, MODIFIED, REMOVED, CaseComparison

CATEGORY_ORDER = [
    "Paramètres", "Base du cas", "Demande", "Hydraulique", "Thermique", "Combustibles", "Renouvelables",
    "Stockage", "Réseau", "Réserves", "Contraintes", "Coût futur", "Séries binaires", "Sorties", "Autres",
]


@dataclass
class Summary:
    headline: str
    counts: dict[str, int]
    categories: list[dict] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    top_changes: list[dict] = field(default_factory=list)


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return f"{int(v):,}".replace(",", " ")
        return f"{v:,.4g}".replace(",", " ")
    return str(v)


def _pct(old, new) -> float | None:
    a, b = parse_number(str(old)), parse_number(str(new))
    if a is None or b is None or a == 0:
        return None
    return (b - a) / abs(a)


def iter_value_changes(cmp: CaseComparison):
    """Toutes les valeurs modifiées, quel que soit le format du fichier."""
    for f in cmp.files:
        if f.status != MODIFIED:
            continue
        if f.text:
            for lc in f.text.lines:
                for t in lc.tokens:
                    yield {"fichier": f.path, "catégorie": f.category, "élément": lc.key or f"ligne {lc.line_b}",
                           "champ": t.column, "ancien": t.old, "nouveau": t.new, "écart": t.delta,
                           "écart_rel": t.rel_delta, "ligne": lc.line_b}
        if f.table:
            for c in f.table.top_cells:
                yield {"fichier": f.path, "catégorie": f.category, "élément": c.key, "champ": c.column,
                       "ancien": c.old, "nouveau": c.new, "écart": c.delta, "écart_rel": _pct(c.old, c.new),
                       "ligne": None}
        if f.json:
            for c in f.json.changes:
                if c.kind == "modifié" and not isinstance(c.old, (dict, list)):
                    yield {"fichier": f.path, "catégorie": f.category, "élément": c.path, "champ": "",
                           "ancien": c.old, "nouveau": c.new,
                           "écart": (c.new - c.old) if isinstance(c.old, (int, float)) and isinstance(c.new, (int, float))
                           and not isinstance(c.old, bool) else None,
                           "écart_rel": _pct(c.old, c.new), "ligne": None}


def build_summary(cmp: CaseComparison, top_n: int = 25, max_per_file: int = 5) -> Summary:
    counts = {s: len(cmp.by_status(s)) for s in (MODIFIED, ADDED, REMOVED, IDENTICAL)}
    total = len(cmp.files)
    n_diff = counts[MODIFIED] + counts[ADDED] + counts[REMOVED]
    if n_diff == 0:
        headline = f"Les deux cas sont identiques ({total} fichiers comparés)."
    else:
        bits = []
        if counts[MODIFIED]:
            bits.append(f"{counts[MODIFIED]} modifié{'s' if counts[MODIFIED] > 1 else ''}")
        if counts[ADDED]:
            bits.append(f"{counts[ADDED]} ajouté{'s' if counts[ADDED] > 1 else ''} dans {cmp.label_b}")
        if counts[REMOVED]:
            bits.append(f"{counts[REMOVED]} absent{'s' if counts[REMOVED] > 1 else ''} de {cmp.label_b}")
        headline = (f"{n_diff} fichier{'s' if n_diff > 1 else ''} sur {total} diffère{'nt' if n_diff > 1 else ''} "
                    f"entre {cmp.label_a} et {cmp.label_b} : " + ", ".join(bits) + ".")

    # Par catégorie
    by_cat: dict[str, dict] = defaultdict(lambda: {MODIFIED: [], ADDED: [], REMOVED: [], IDENTICAL: []})
    for f in cmp.files:
        by_cat[f.category][f.status].append(f.path)
    cats = []
    for c in sorted(by_cat, key=lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99):
        d = by_cat[c]
        cats.append({"catégorie": c, "modifiés": len(d[MODIFIED]), "ajoutés": len(d[ADDED]),
                     "supprimés": len(d[REMOVED]), "identiques": len(d[IDENTICAL]),
                     "fichiers concernés": ", ".join(d[MODIFIED] + d[ADDED] + d[REMOVED])})

    # Points marquants, rédigés catégorie par catégorie
    highlights = []
    for f in sorted(cmp.changed, key=lambda f: (CATEGORY_ORDER.index(f.category)
                                                 if f.category in CATEGORY_ORDER else 99, f.path)):
        prefix = f"[{f.category}] {f.path} – {f.description}"
        if f.status == ADDED:
            highlights.append(f"{prefix} : nouveau fichier dans {cmp.label_b}.")
        elif f.status == REMOVED:
            highlights.append(f"{prefix} : présent seulement dans {cmp.label_a}.")
        else:
            line = f"{prefix} : {f.summary}."
            # Pour les fichiers de paramètres, on détaille chaque valeur (peu nombreuses et décisives)
            if f.category == "Paramètres" and f.text:
                details = [f"« {lc.key} » {t.column} : {t.old} → {t.new}"
                           for lc in f.text.lines for t in lc.tokens][:10]
                if details:
                    line += " Détail : " + " ; ".join(details) + "."
            highlights.append(line)
        if f.error:
            highlights.append(f"⚠ {f.path} : analyse détaillée impossible ({f.error}).")

    # Plus fortes variations relatives
    changes = list(iter_value_changes(cmp))
    numeric = [c for c in changes if c["écart_rel"] is not None]
    numeric.sort(key=lambda c: -abs(c["écart_rel"]))
    top, per_file = [], defaultdict(int)
    for c in numeric:
        if len(top) >= top_n:
            break
        per_file[c["fichier"]] += 1
        if per_file[c["fichier"]] > max_per_file:
            continue
        top.append({"fichier": c["fichier"], "élément": c["élément"], "champ": c["champ"],
                    "ancien": c["ancien"], "nouveau": c["nouveau"],
                    "écart": _fmt(c["écart"]), "écart %": f"{c['écart_rel']:+.1%}"})
    return Summary(headline, counts, cats, highlights, top)
