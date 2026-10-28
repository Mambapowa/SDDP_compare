"""Lecture des cas : dossiers ou archives .zip, détection d'encodage et de type."""

from __future__ import annotations

import fnmatch
import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

DEFAULT_IGNORE = ["*.tmp", "*.bak", "~$*", "*.pyc", "__pycache__/*", ".DS_Store", "Thumbs.db"]

TEXT_EXTENSIONS = {".dat", ".txt", ".csv", ".json", ".prn", ".out", ".log", ".cfg", ".ini", ".hdr", ".xml", ""}


class CaseSource:
    """Un cas SDDP ouvert depuis un dossier ou un .zip.

    Pour un .zip, le contenu est extrait dans un dossier temporaire ;
    utilisez ``with CaseSource(...) as case:`` pour le nettoyer ensuite.
    """

    def __init__(self, path: str | Path):
        self.original = Path(path)
        self._tmp: str | None = None
        if self.original.is_file() and zipfile.is_zipfile(self.original):
            self._tmp = tempfile.mkdtemp(prefix="sddp_case_")
            with zipfile.ZipFile(self.original) as zf:
                _safe_extract(zf, Path(self._tmp))
            self.root = _single_subfolder(Path(self._tmp))
        elif self.original.is_dir():
            self.root = self.original
        else:
            raise FileNotFoundError(f"Cas introuvable (dossier ou .zip attendu) : {path}")

    @property
    def label(self) -> str:
        return self.original.stem if self.original.is_file() else self.original.name

    def list_files(self, ignore: list[str] | None = None) -> dict[str, Path]:
        """Retourne {chemin relatif en minuscules: chemin absolu}.

        Les noms sont comparés sans tenir compte de la casse, car les cas
        SDDP viennent souvent de Windows.
        """
        patterns = DEFAULT_IGNORE + list(ignore or [])
        out: dict[str, Path] = {}
        for p in sorted(self.root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(self.root).as_posix()
            if any(fnmatch.fnmatch(rel.lower(), pat.lower()) or fnmatch.fnmatch(p.name.lower(), pat.lower())
                   for pat in patterns):
                continue
            out[rel.lower()] = p
        return out

    def close(self) -> None:
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

    def __enter__(self) -> "CaseSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(dest)):
            raise ValueError(f"Chemin dangereux dans l'archive : {member.filename}")
    zf.extractall(dest)


def _single_subfolder(root: Path) -> Path:
    """Si l'archive contient un seul dossier racine, on descend dedans."""
    entries = [e for e in root.iterdir() if e.name not in ("__MACOSX",)]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return root


def file_hash(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_text_file(path: Path) -> bool:
    """Heuristique : extension connue ou absence d'octets nuls dans le début du fichier."""
    if path.suffix.lower() == ".bin":
        return False
    with open(path, "rb") as f:
        head = f.read(8192)
    if b"\x00" in head:
        return False
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    # Proportion de caractères imprimables
    printable = sum(32 <= b < 127 or b in (9, 10, 13) or b >= 160 for b in head)
    return not head or printable / len(head) > 0.9


def read_text(path: Path) -> str:
    """Lit un fichier texte en UTF-8, avec repli en Latin-1 (fréquent chez PSR)."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")
