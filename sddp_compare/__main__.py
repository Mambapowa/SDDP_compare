"""Ligne de commande : python -m sddp_compare CAS_A CAS_B [-o rapport.html] [-x rapport.xlsx]"""

from __future__ import annotations

import argparse
import sys

from . import build_summary, compare_cases, to_excel, to_html, to_markdown


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sddp-compare", description="Compare deux cas SDDP et résume les différences.")
    p.add_argument("case_a", help="Cas de référence (dossier ou .zip)")
    p.add_argument("case_b", help="Cas à comparer (dossier ou .zip)")
    p.add_argument("-o", "--html", help="Fichier HTML du rapport")
    p.add_argument("-x", "--excel", help="Fichier Excel du détail")
    p.add_argument("-i", "--ignore", action="append", default=[],
                   help="Motif de fichiers à ignorer (répétable), ex. -i '*.csv' -i 'resultats/*'")
    p.add_argument("-t", "--tol", type=float, default=1e-9, help="Tolérance numérique absolue (défaut 1e-9)")
    p.add_argument("--label-a", help="Nom affiché pour le cas A")
    p.add_argument("--label-b", help="Nom affiché pour le cas B")
    args = p.parse_args(argv)

    cmp = compare_cases(args.case_a, args.case_b, ignore=args.ignore, tol=args.tol,
                        label_a=args.label_a, label_b=args.label_b)
    summary = build_summary(cmp)
    sys.stdout.write(to_markdown(cmp, summary))
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(to_html(cmp, summary))
        print(f"\nRapport HTML : {args.html}")
    if args.excel:
        to_excel(cmp, args.excel, summary)
        print(f"Détail Excel : {args.excel}")
    return 0 if not cmp.changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
