# Comparateur de cas SDDP

Compare deux cas SDDP (PSR) et produit un **résumé des différences** : fichiers ajoutés, supprimés
et modifiés, avec le détail des valeurs qui changent (ancien → nouveau, écart, écart en %).

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

### Interface web

```bash
streamlit run app.py
```

Choisissez deux cas (dossiers locaux ou archives `.zip`), cliquez sur **Comparer**.
Vous obtenez le résumé, les plus fortes variations, le détail par fichier, et pouvez
télécharger le rapport HTML et le détail Excel.

### Ligne de commande

```bash
python -m sddp_compare chemin/cas_A chemin/cas_B -o rapport.html -x rapport.xlsx
```

Options utiles :

| Option | Rôle |
|---|---|
| `-i '*.csv'` | ignorer des fichiers (répétable), ex. les résultats |
| `-t 1e-6` | tolérance : écart numérique en dessous duquel deux valeurs sont égales |
| `--label-a Base --label-b Variante` | noms affichés dans le rapport |

Le code de sortie vaut `0` si les cas sont identiques, `1` sinon (pratique en script).

### Depuis Python

```python
from sddp_compare import compare_cases, build_summary, to_html
cmp = compare_cases("cas_A", "cas_B", ignore=["*.log"])
print(build_summary(cmp).headline)
```

## Ce que l'outil compare

| Type de fichier | Méthode |
|---|---|
| `.dat` / texte (colonnes fixes) | alignement des lignes, appariement par code/nom, comparaison champ par champ. Le nom de la colonne est repris de la ligne d'en-tête (`!Num Nome PotIn…`). Les lignes `Paramètre ...... valeur` de `sddp.dat` sont reconnues. |
| `.csv` | lecture comme un tableau (les lignes de méta-données PSR avant l'en-tête sont gérées), colonnes clés détectées (étape, bloc, série, code, nom…), lignes/colonnes ajoutées ou supprimées, valeurs modifiées, totaux par colonne. |
| `.json` | comparaison de la structure ; les listes d'objets sont appariées par `name` / `code` / `id`. |
| binaires (`.bin`…) | différent ou non (et taille). |

- Les différences de **mise en forme** seules (espaces, `10.0` vs `10.00`) ne sont pas comptées.
- Les noms de fichiers sont comparés **sans tenir compte de la casse** (cas venant de Windows).
- Chaque fichier est classé par catégorie (Paramètres, Hydraulique, Thermique, Demande, Réseau…)
  d'après son nom ; la liste se complète dans `sddp_compare/catalog.py`.

## Exemple et tests

```bash
python tests/make_examples.py   # crée examples/cas_A et examples/cas_B
python -m sddp_compare examples/cas_A examples/cas_B -i '*.log'
python -m pytest -q tests
```
