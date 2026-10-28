"""Tests du comparateur sur les cas d'exemple (python -m pytest)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sddp_compare import build_summary, compare_cases, to_excel, to_html
from sddp_compare.diff_text import diff_text
from sddp_compare.models import ADDED, IDENTICAL, MODIFIED, REMOVED

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


@pytest.fixture(scope="module")
def cmp():
    subprocess.run([sys.executable, str(ROOT / "tests" / "make_examples.py")], check=True)
    return compare_cases(EX / "cas_A", EX / "cas_B", ignore=["*.log"])


def by_path(cmp, name):
    return next(f for f in cmp.files if f.path == name)


def test_statuses(cmp):
    assert by_path(cmp, "dbus.dat").status == IDENTICAL
    assert by_path(cmp, "cbatte.dat").status == ADDED
    assert by_path(cmp, "mntti.dat").status == REMOVED
    assert by_path(cmp, "gndgen.bin").status == MODIFIED
    assert not any(f.path == "sddp.log" for f in cmp.files)


def test_parameters_ignore_number_formatting(cmp):
    f = by_path(cmp, "sddp.dat")
    changes = {lc.key: (t.old, t.new) for lc in f.text.lines for t in lc.tokens}
    assert changes == {"Numero de etapas": ("12", "24"), "Numero de series forward": ("50", "100")}


def test_fixed_width_columns_are_labelled(cmp):
    f = by_path(cmp, "chidro.dat")
    found = {(lc.key, t.column, t.old, t.new) for lc in f.text.lines for t in lc.tokens}
    assert ("2 SALTO", "PotIn", "950.0", "1050.0") in found
    assert ("3 YACYRETA", "Vmin", "1000.0", "1200.0") in found
    assert f.text.n_added == 1
    t = by_path(cmp, "ctermi.dat").text
    assert t.n_removed == 1 and t.lines[0].kind in ("modifiée", "supprimée")


def test_csv(cmp):
    t = by_path(cmp, "demand.csv").table
    assert t.key_columns == ["Stg", "Blk"]
    assert t.n_rows_added == 36 and t.n_rows_removed == 0
    assert t.n_cells_changed == 9


def test_json(cmp):
    changes = by_path(cmp, "psrclasses.json").json.changes
    assert any(c.path == "fuels[name=GAS].price" and c.new == 7.2 for c in changes)
    assert any(c.kind == "ajouté" and "HYDROGENE" in c.path for c in changes)


def test_reports(cmp, tmp_path):
    s = build_summary(cmp)
    assert "8 fichiers sur 9" in s.headline
    assert "<html" in to_html(cmp, s)
    assert to_excel(cmp, tmp_path / "r.xlsx", s).stat().st_size > 0


def test_zip_input(tmp_path):
    a = shutil.make_archive(str(tmp_path / "A"), "zip", EX, "cas_A")
    b = shutil.make_archive(str(tmp_path / "B"), "zip", EX, "cas_B")
    c = compare_cases(a, b, ignore=["*.log"])
    assert len(c.changed) == 8


def test_identical_cases():
    c = compare_cases(EX / "cas_A", EX / "cas_A")
    assert not c.changed


def test_text_insert_does_not_shift_everything():
    a = "!Num Nome PotIn\n 1 A 10\n 2 B 20\n 3 C 30\n"
    b = "!Num Nome PotIn\n 1 A 10\n 9 Z 99\n 2 B 20\n 3 C 31\n"
    d = diff_text(a, b)
    assert d.n_added == 1 and d.n_modified == 1 and d.n_removed == 0
