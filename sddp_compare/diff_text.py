"""Comparaison des fichiers texte (format .dat à colonnes fixes de SDDP, etc.).

Principe :
1. alignement des lignes (difflib) en ignorant les différences d'espaces ;
2. appariement des lignes modifiées par leur clé (premier champ : code, nom…) ;
3. comparaison champ par champ, avec écart numérique ;
4. libellé de chaque champ déduit de la ligne d'en-tête la plus proche au-dessus
   (les .dat SDDP ont des en-têtes alignés sur les colonnes de données).
"""

from __future__ import annotations

import difflib
import re

from .models import LineChange, TextDiff, TokenChange

TOKEN_RE = re.compile(r"\S+")
NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eEdD][+-]?\d+)?$")

MAX_DETAIL_LINES = 3000
FAST_MODE_LINES = 200_000


def parse_number(tok: str) -> float | None:
    t = tok.strip().rstrip(",;")
    if not NUM_RE.match(t):
        return None
    try:
        return float(t.replace("d", "e").replace("D", "e"))
    except ValueError:
        return None


def _norm(line: str) -> str:
    return " ".join(line.split())


def _is_header_like(line: str) -> bool:
    toks = line.split()
    if not toks:
        return False
    if line.lstrip()[:1] in ("!", "$", "#", "*", "/"):
        return True
    n_num = sum(parse_number(t) is not None for t in toks)
    has_alpha = any(c.isalpha() for c in line)
    return has_alpha and n_num / len(toks) < 0.3 and len(toks) >= 2


def _header_index(lines: list[str]) -> list[int | None]:
    """Pour chaque ligne, index de la ligne d'en-tête la plus proche au-dessus."""
    out: list[int | None] = []
    last: int | None = None
    for i, line in enumerate(lines):
        out.append(last)
        if _is_header_like(line):
            last = i
    return out


def _column_label(header: str | None, start: int, end: int, idx: int) -> str:
    """Libellé du champ situé en [start, end) d'après la ligne d'en-tête."""
    if header:
        best, best_dist = None, None
        for m in TOKEN_RE.finditer(header):
            hs, he = m.span()
            overlap = min(end, he) - max(start, hs)
            if overlap > 0:
                return m.group().strip("!$#*.") or f"champ {idx + 1}"
            dist = min(abs(hs - end), abs(start - he))
            if best_dist is None or dist < best_dist:
                best, best_dist = m.group(), dist
        if best is not None and best_dist is not None and best_dist <= 2:
            return best.strip("!$#*.") or f"champ {idx + 1}"
    return f"champ {idx + 1}"


DOTS_RE = re.compile(r"^[.:=_-]{2,}$")


def _line_key(line: str) -> str:
    """Identifiant probable de l'enregistrement porté par la ligne.

    - « 12 ITAIPU  ... » → « 12 ITAIPU » (code + nom) ;
    - « Numero de series ....... 50 » → « Numero de series » (paramètre) ;
    - sinon le premier champ.
    """
    toks = line.split()
    if not toks:
        return ""
    if parse_number(toks[0]) is not None:
        if len(toks) > 1 and parse_number(toks[1]) is None:
            return f"{toks[0]} {toks[1]}"[:60]
        return toks[0][:60]
    words = []
    for t in toks:
        if parse_number(t) is not None or DOTS_RE.match(t):
            break
        words.append(t.rstrip(".:="))
        if len(words) == 6:
            break
    return " ".join(w for w in words if w)[:60] or toks[0][:60]


def _token_changes(a: str, b: str, header: str | None, tol: float) -> list[TokenChange]:
    ta = list(TOKEN_RE.finditer(a))
    tb = list(TOKEN_RE.finditer(b))
    changes: list[TokenChange] = []
    sm = difflib.SequenceMatcher(None, [m.group() for m in ta], [m.group() for m in tb], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        n = max(i2 - i1, j2 - j1)
        for k in range(n):
            ma = ta[i1 + k] if i1 + k < i2 else None
            mb = tb[j1 + k] if j1 + k < j2 else None
            old = ma.group() if ma else ""
            new = mb.group() if mb else ""
            va, vb = parse_number(old), parse_number(new)
            delta = rel = None
            if va is not None and vb is not None:
                delta = vb - va
                if abs(delta) <= tol:
                    continue  # même valeur, écriture différente (1.0 / 1.00)
                rel = delta / abs(va) if va != 0 else None
            ref = mb or ma
            idx = (j1 + k) if mb else (i1 + k)
            label = _column_label(header, ref.start(), ref.end(), idx)
            changes.append(TokenChange(label, old, new, delta, rel))
    return changes


def diff_text(text_a: str, text_b: str, tol: float = 1e-9) -> TextDiff:
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()
    norm_a = [_norm(l) for l in lines_a]
    norm_b = [_norm(l) for l in lines_b]
    hdr_a = _header_index(lines_a)
    hdr_b = _header_index(lines_b)
    res = TextDiff()

    def header_for(ia: int | None, ib: int | None) -> str | None:
        if ib is not None and hdr_b[ib] is not None:
            return lines_b[hdr_b[ib]]
        if ia is not None and hdr_a[ia] is not None:
            return lines_a[hdr_a[ia]]
        return None

    def add(change: LineChange) -> None:
        if change.kind == "ajoutée":
            res.n_added += 1
        elif change.kind == "supprimée":
            res.n_removed += 1
        else:
            res.n_modified += 1
            res.n_values += len(change.tokens)
        if len(res.lines) < MAX_DETAIL_LINES:
            res.lines.append(change)
        else:
            res.truncated = True

    def modified(ia: int, ib: int) -> None:
        # Ligne « libellé ....... valeur » : pas d'en-tête de colonnes à chercher
        kv_line = _is_header_like(lines_b[ib])
        toks = _token_changes(lines_a[ia], lines_b[ib], None if kv_line else header_for(ia, ib), tol)
        if kv_line:
            for t in toks:
                if t.column.startswith("champ"):
                    t.column = "valeur"
        if toks:
            add(LineChange("modifiée", ia + 1, ib + 1, lines_a[ia], lines_b[ib], _line_key(lines_b[ib]), toks))

    if len(lines_a) > FAST_MODE_LINES or len(lines_b) > FAST_MODE_LINES:
        # Très gros fichier : comparaison ligne à ligne, sans réalignement
        for i in range(max(len(lines_a), len(lines_b))):
            if i >= len(lines_a):
                add(LineChange("ajoutée", None, i + 1, None, lines_b[i], _line_key(lines_b[i])))
            elif i >= len(lines_b):
                add(LineChange("supprimée", i + 1, None, lines_a[i], None, _line_key(lines_a[i])))
            elif norm_a[i] != norm_b[i]:
                modified(i, i)
        return res

    sm = difflib.SequenceMatcher(None, norm_a, norm_b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        if op == "delete":
            for i in range(i1, i2):
                if norm_a[i]:
                    add(LineChange("supprimée", i + 1, None, lines_a[i], None, _line_key(lines_a[i])))
            continue
        if op == "insert":
            for j in range(j1, j2):
                if norm_b[j]:
                    add(LineChange("ajoutée", None, j + 1, None, lines_b[j], _line_key(lines_b[j])))
            continue
        # replace : on apparie d'abord par clé, puis par position si ressemblantes
        rest_a = list(range(i1, i2))
        rest_b = list(range(j1, j2))
        keys_b: dict[str, list[int]] = {}
        for j in rest_b:
            keys_b.setdefault(_line_key(lines_b[j]), []).append(j)
        pairs: list[tuple[int, int]] = []
        for i in list(rest_a):
            k = _line_key(lines_a[i])
            if k and keys_b.get(k):
                j = keys_b[k].pop(0)
                pairs.append((i, j))
                rest_a.remove(i)
                rest_b.remove(j)
        for i, j in list(zip(rest_a, rest_b)):
            ratio = difflib.SequenceMatcher(None, norm_a[i], norm_b[j]).quick_ratio()
            if ratio >= 0.5:
                pairs.append((i, j))
                rest_a.remove(i)
                rest_b.remove(j)
        events: list[tuple[int, int, LineChange | tuple[int, int]]] = []
        for i, j in pairs:
            events.append((j, 1, (i, j)))
        for i in rest_a:
            if norm_a[i]:
                events.append((j1, 0, LineChange("supprimée", i + 1, None, lines_a[i], None, _line_key(lines_a[i]))))
        for j in rest_b:
            if norm_b[j]:
                events.append((j, 2, LineChange("ajoutée", None, j + 1, None, lines_b[j], _line_key(lines_b[j]))))
        for _, _, ev in sorted(events, key=lambda e: (e[0], e[1])):
            if isinstance(ev, tuple):
                modified(*ev)
            else:
                add(ev)
    return res
