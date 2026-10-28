"""Comparaison structurelle de fichiers JSON (ex. base PSRClasses des versions récentes)."""

from __future__ import annotations

from typing import Any

from .models import JsonChange, JsonDiff

ID_FIELDS = ("reference_id", "ReferenceId", "id", "Id", "code", "Code", "name", "Name", "AVId")
MAX_CHANGES = 3000


def _id_field(items: list) -> str | None:
    if not items or not all(isinstance(x, dict) for x in items):
        return None
    for f in ID_FIELDS:
        vals = [x.get(f) for x in items]
        if all(v is not None for v in vals) and len(set(map(str, vals))) == len(vals):
            return f
    return None


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def diff_json(a: Any, b: Any, tol: float = 1e-9) -> JsonDiff:
    res = JsonDiff()

    def push(c: JsonChange) -> None:
        if len(res.changes) < MAX_CHANGES:
            res.changes.append(c)
        else:
            res.truncated = True

    def walk(x: Any, y: Any, path: str) -> None:
        if isinstance(x, dict) and isinstance(y, dict):
            for k in x:
                p = f"{path}.{k}" if path else str(k)
                if k not in y:
                    push(JsonChange(p, "supprimé", old=x[k]))
                else:
                    walk(x[k], y[k], p)
            for k in y:
                if k not in x:
                    push(JsonChange(f"{path}.{k}" if path else str(k), "ajouté", new=y[k]))
        elif isinstance(x, list) and isinstance(y, list):
            fid = _id_field(x) if _id_field(x) == _id_field(y) else None
            if fid:
                mx = {str(i[fid]): i for i in x}
                my = {str(i[fid]): i for i in y}
                for k, v in mx.items():
                    p = f"{path}[{fid}={k}]"
                    if k not in my:
                        push(JsonChange(p, "supprimé", old=v))
                    else:
                        walk(v, my[k], p)
                for k, v in my.items():
                    if k not in mx:
                        push(JsonChange(f"{path}[{fid}={k}]", "ajouté", new=v))
            else:
                for i in range(max(len(x), len(y))):
                    p = f"{path}[{i}]"
                    if i >= len(x):
                        push(JsonChange(p, "ajouté", new=y[i]))
                    elif i >= len(y):
                        push(JsonChange(p, "supprimé", old=x[i]))
                    else:
                        walk(x[i], y[i], p)
        else:
            if _num(x) and _num(y):
                if abs(y - x) > tol:
                    push(JsonChange(path, "modifié", x, y))
            elif x != y:
                push(JsonChange(path, "modifié", x, y))

    walk(a, b, "")
    return res
