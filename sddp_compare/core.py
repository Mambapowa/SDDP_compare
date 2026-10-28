"""Point d'entrée : comparaison de deux cas SDDP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .catalog import classify
from .diff_json import diff_json
from .diff_table import diff_table
from .diff_text import diff_text
from .io import CaseSource, file_hash, is_text_file, read_text
from .models import ADDED, IDENTICAL, MODIFIED, REMOVED, CaseComparison, FileDiff


def _fmt_size(n: int | None) -> str:
    if n is None:
        return "-"
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n > 1 else ''}"


def _compare_file(fd: FileDiff, pa: Path, pb: Path, tol: float) -> None:
    if file_hash(pa) == file_hash(pb):
        fd.status = IDENTICAL
        return
    fd.status = MODIFIED
    if not (is_text_file(pa) and is_text_file(pb)):
        fd.kind = "binaire"
        if fd.size_a == fd.size_b:
            fd.summary = f"Contenu binaire modifié (même taille : {_fmt_size(fd.size_a)})"
        else:
            fd.summary = f"Contenu binaire modifié (taille {_fmt_size(fd.size_a)} → {_fmt_size(fd.size_b)})"
        fd.n_changes = 1
        return

    ta, tb = read_text(pa), read_text(pb)
    suffix = pa.suffix.lower()

    if suffix == ".json":
        try:
            ja, jb = json.loads(ta), json.loads(tb)
        except json.JSONDecodeError:
            pass
        else:
            fd.kind = "json"
            fd.json = diff_json(ja, jb, tol)
            n = len(fd.json.changes)
            fd.n_changes = n
            if n == 0:
                fd.status = IDENTICAL
                fd.summary = "Différences de mise en forme uniquement"
            else:
                kinds = {k: sum(c.kind == k for c in fd.json.changes) for k in ("modifié", "ajouté", "supprimé")}
                parts = [f"{v} {k}{'s' if v > 1 else ''}" for k, v in kinds.items() if v]
                fd.summary = f"{_plural(n, 'élément')} différent{'s' if n > 1 else ''} : " + ", ".join(parts)
            return

    if suffix == ".csv":
        table = diff_table(ta, tb, tol)
        if table is not None:
            fd.kind = "csv"
            fd.table = table
            parts = []
            if table.n_rows_added:
                parts.append(f"{_plural(table.n_rows_added, 'ligne')} ajoutée{'s' if table.n_rows_added > 1 else ''}")
            if table.n_rows_removed:
                parts.append(f"{_plural(table.n_rows_removed, 'ligne')} supprimée{'s' if table.n_rows_removed > 1 else ''}")
            if table.cols_added:
                parts.append(f"colonnes ajoutées : {', '.join(table.cols_added[:5])}")
            if table.cols_removed:
                parts.append(f"colonnes supprimées : {', '.join(table.cols_removed[:5])}")
            if table.n_cells_changed:
                cols = sorted((s for s in table.column_stats if s.n_changed), key=lambda s: -s.n_changed)
                names = ", ".join(s.column for s in cols[:4]) + ("…" if len(cols) > 4 else "")
                parts.append(f"{_plural(table.n_cells_changed, 'valeur')} modifiée{'s' if table.n_cells_changed > 1 else ''} "
                             f"sur {_plural(table.n_rows_changed, 'ligne')} (colonnes : {names})")
            totals = []
            for st in sorted(table.column_stats, key=lambda st: -st.n_changed):
                if st.sum_a and st.sum_b is not None and abs(st.sum_b - st.sum_a) > tol:
                    totals.append(f"{st.column} {st.sum_a:,.6g} → {st.sum_b:,.6g} "
                                  f"({(st.sum_b - st.sum_a) / abs(st.sum_a):+.1%})".replace(",", " "))
            if totals:
                parts.append("totaux : " + ", ".join(totals[:3]))
            if table.preamble and (table.preamble.n_modified or table.preamble.n_added or table.preamble.n_removed):
                parts.append("en-tête modifié")
            fd.n_changes = (table.n_rows_added + table.n_rows_removed + table.n_cells_changed
                            + len(table.cols_added) + len(table.cols_removed) + (1 if table.preamble else 0))
            if fd.n_changes == 0:
                fd.status = IDENTICAL
                fd.summary = "Différences de mise en forme uniquement"
            else:
                fd.summary = " ; ".join(parts)
            return

    fd.kind = "texte"
    fd.text = diff_text(ta, tb, tol)
    t = fd.text
    fd.n_changes = t.n_added + t.n_removed + t.n_modified
    if fd.n_changes == 0:
        fd.status = IDENTICAL
        fd.summary = "Différences de mise en forme uniquement (espaces, écriture des nombres)"
        return
    parts = []
    if t.n_modified:
        parts.append(f"{_plural(t.n_modified, 'ligne')} modifiée{'s' if t.n_modified > 1 else ''} "
                     f"({_plural(t.n_values, 'valeur')})")
    if t.n_added:
        parts.append(f"{_plural(t.n_added, 'ligne')} ajoutée{'s' if t.n_added > 1 else ''}")
    if t.n_removed:
        parts.append(f"{_plural(t.n_removed, 'ligne')} supprimée{'s' if t.n_removed > 1 else ''}")
    fd.summary = ", ".join(parts)


def compare_cases(
    path_a: str | Path,
    path_b: str | Path,
    ignore: list[str] | None = None,
    tol: float = 1e-9,
    label_a: str | None = None,
    label_b: str | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> CaseComparison:
    """Compare deux cas SDDP (dossiers ou .zip) et retourne le détail des différences.

    ``tol`` : écart numérique absolu en dessous duquel deux valeurs sont jugées égales.
    ``ignore`` : motifs de fichiers à ignorer (ex. ``["*.csv", "results/*"]``).
    """
    with CaseSource(path_a) as ca, CaseSource(path_b) as cb:
        files_a = ca.list_files(ignore)
        files_b = cb.list_files(ignore)
        cmp = CaseComparison(
            case_a=str(path_a), case_b=str(path_b),
            label_a=label_a or ca.label, label_b=label_b or cb.label,
            options={"tolérance": tol, "ignorés": ignore or []},
        )
        all_keys = sorted(set(files_a) | set(files_b))
        for n, key in enumerate(all_keys, 1):
            pa, pb = files_a.get(key), files_b.get(key)
            display = (pb or pa).relative_to(cb.root if pb else ca.root).as_posix()
            if progress:
                progress(n, len(all_keys), display)
            category, description = classify(display)
            fd = FileDiff(path=display, category=category, description=description, status=IDENTICAL,
                          size_a=pa.stat().st_size if pa else None,
                          size_b=pb.stat().st_size if pb else None)
            if pa is None:
                fd.status, fd.summary, fd.n_changes = ADDED, f"Nouveau fichier ({_fmt_size(fd.size_b)})", 1
            elif pb is None:
                fd.status, fd.summary, fd.n_changes = REMOVED, f"Fichier absent du cas {cmp.label_b}", 1
            else:
                try:
                    _compare_file(fd, pa, pb, tol)
                except Exception as exc:  # un fichier illisible ne doit pas bloquer tout le rapport
                    fd.status = MODIFIED
                    fd.error = f"{type(exc).__name__}: {exc}"
                    fd.summary = "Fichier différent (erreur pendant l'analyse détaillée)"
            cmp.files.append(fd)
    return cmp
