"""Structures de données décrivant le résultat d'une comparaison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

IDENTICAL = "identique"
MODIFIED = "modifié"
ADDED = "ajouté"      # présent seulement dans le cas B
REMOVED = "supprimé"  # présent seulement dans le cas A


@dataclass
class TokenChange:
    """Une valeur qui change à l'intérieur d'une ligne de texte."""
    column: str           # libellé de colonne déduit de l'en-tête, ou "champ N"
    old: str
    new: str
    delta: float | None = None       # new - old si les deux sont numériques
    rel_delta: float | None = None   # (new - old) / |old|


@dataclass
class LineChange:
    kind: str                      # "ajoutée", "supprimée", "modifiée"
    line_a: int | None             # numéro de ligne (1-based) dans A
    line_b: int | None
    text_a: str | None
    text_b: str | None
    key: str = ""                  # identifiant probable de l'enregistrement (code, nom…)
    tokens: list[TokenChange] = field(default_factory=list)


@dataclass
class TextDiff:
    lines: list[LineChange] = field(default_factory=list)
    n_added: int = 0
    n_removed: int = 0
    n_modified: int = 0
    n_values: int = 0          # nombre de valeurs (tokens) modifiées
    truncated: bool = False    # détails tronqués (fichier très gros)


@dataclass
class ColumnStat:
    column: str
    n_changed: int
    sum_a: float | None = None
    sum_b: float | None = None
    max_abs_delta: float | None = None
    max_rel_delta: float | None = None


@dataclass
class CellChange:
    key: str
    column: str
    old: Any
    new: Any
    delta: float | None = None


@dataclass
class TableDiff:
    key_columns: list[str] = field(default_factory=list)
    n_rows_a: int = 0
    n_rows_b: int = 0
    n_rows_added: int = 0
    n_rows_removed: int = 0
    rows_added: list[str] = field(default_factory=list)
    rows_removed: list[str] = field(default_factory=list)
    cols_added: list[str] = field(default_factory=list)
    cols_removed: list[str] = field(default_factory=list)
    column_stats: list[ColumnStat] = field(default_factory=list)
    top_cells: list[CellChange] = field(default_factory=list)
    n_cells_changed: int = 0
    n_rows_changed: int = 0
    preamble: TextDiff | None = None   # lignes d'en-tête avant le tableau


@dataclass
class JsonChange:
    path: str
    kind: str      # "ajouté", "supprimé", "modifié"
    old: Any = None
    new: Any = None


@dataclass
class JsonDiff:
    changes: list[JsonChange] = field(default_factory=list)
    truncated: bool = False


@dataclass
class FileDiff:
    path: str
    category: str
    description: str
    status: str
    kind: str = "binaire"          # texte | csv | json | binaire
    size_a: int | None = None
    size_b: int | None = None
    summary: str = ""
    n_changes: int = 0
    text: TextDiff | None = None
    table: TableDiff | None = None
    json: JsonDiff | None = None
    error: str | None = None


@dataclass
class CaseComparison:
    case_a: str
    case_b: str
    label_a: str
    label_b: str
    files: list[FileDiff] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)

    def by_status(self, status: str) -> list[FileDiff]:
        return [f for f in self.files if f.status == status]

    @property
    def changed(self) -> list[FileDiff]:
        return [f for f in self.files if f.status != IDENTICAL]
