"""Comparateur de cas SDDP (PSR) : détecte et résume les différences entre deux cas."""

from .core import compare_cases
from .report import to_dataframes, to_excel, to_html, to_markdown
from .summary import build_summary

__all__ = ["compare_cases", "build_summary", "to_html", "to_excel", "to_markdown", "to_dataframes"]
__version__ = "1.0.0"
