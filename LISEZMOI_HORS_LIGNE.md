# Installation sur une machine sans Internet

L'archive `sddp-compare-hors-ligne-py314-linux-x86_64.tar.gz` contient le code et tous
les paquets Python nécessaires (dossier `wheels/`), pour **Linux x86_64 et Python 3.14**.

```bash
tar xzf sddp-compare-hors-ligne-py314-linux-x86_64.tar.gz
cd sddp-compare
./scripts/installer_hors_ligne.sh      # une seule fois
./scripts/lancer.sh                    # lance l'interface web sur le port 8501
```

Si `python3` n'est pas Python 3.14, indiquez le bon :
`PYTHON=python3.14 ./scripts/installer_hors_ligne.sh`

Ligne de commande, sans interface web :

```bash
.venv/bin/python -m sddp_compare /chemin/cas_A /chemin/cas_B -o rapport.html -x rapport.xlsx
```

## Mettre à jour plus tard

Sur une machine avec Internet, dans le dossier du projet :

```bash
pip download -r requirements.txt -d wheels --only-binary=:all: \
  --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 \
  --platform manylinux_2_28_x86_64 --python-version 314
```

puis recopiez le dossier sur la machine et relancez `./scripts/installer_hors_ligne.sh`.
