"""Catalogue des fichiers usuels d'un cas SDDP (PSR).

Associe un nom de fichier à une catégorie et une description lisible.
La correspondance se fait sur le préfixe du nom (insensible à la casse),
car SDDP suffixe souvent les fichiers par un code de système (ex. ``chidrobo.dat``).
Le catalogue est volontairement extensible : ajoutez vos propres préfixes.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

# (préfixe ou motif glob, catégorie, description)
# L'ordre compte : le premier motif qui correspond l'emporte.
CATALOG: list[tuple[str, str, str]] = [
    # Paramètres généraux
    ("sddp.dat", "Paramètres", "Paramètres d'exécution du cas"),
    ("sddp*.dat", "Paramètres", "Paramètres d'exécution"),
    ("psrclasses*.json", "Base du cas", "Base de données du cas (format PSRClasses)"),
    ("*.json", "Base du cas", "Données du cas au format JSON"),
    ("sistem", "Paramètres", "Définition des systèmes"),
    ("duraci", "Paramètres", "Durée des blocs (patamares)"),
    ("bloque", "Paramètres", "Définition des blocs horaires"),
    ("hrbl", "Paramètres", "Correspondance heures / blocs"),
    # Hydraulique
    ("chidro", "Hydraulique", "Configuration des centrales hydrauliques"),
    ("hinflw", "Hydraulique", "Apports hydrologiques historiques"),
    ("vazoes", "Hydraulique", "Apports hydrologiques"),
    ("inflow", "Hydraulique", "Apports hydrologiques"),
    ("mnthi", "Hydraulique", "Maintenance des centrales hydrauliques"),
    ("hmanut", "Hydraulique", "Maintenance des centrales hydrauliques"),
    ("cmhidr", "Hydraulique", "Modifications des centrales hydrauliques"),
    ("vmax", "Hydraulique", "Volumes maximaux / cibles"),
    ("vmin", "Hydraulique", "Volumes minimaux / cibles"),
    ("volfin", "Hydraulique", "Volumes finaux"),
    ("irriga", "Hydraulique", "Irrigation"),
    ("pumped", "Hydraulique", "Stations de pompage"),
    ("cpump", "Hydraulique", "Stations de pompage"),
    ("cvaz", "Hydraulique", "Stations hydrométriques"),
    # Thermique
    ("ctermi", "Thermique", "Configuration des centrales thermiques"),
    ("mntti", "Thermique", "Maintenance des centrales thermiques"),
    ("tmanut", "Thermique", "Maintenance des centrales thermiques"),
    ("cmterm", "Thermique", "Modifications des centrales thermiques"),
    ("genmin", "Thermique", "Production minimale"),
    # Combustibles
    ("ccombu", "Combustibles", "Configuration des combustibles"),
    ("cmcomb", "Combustibles", "Prix / modifications des combustibles"),
    ("cfuel", "Combustibles", "Combustibles"),
    ("fuel", "Combustibles", "Combustibles"),
    ("gas", "Combustibles", "Réseau de gaz"),
    # Renouvelables et stockage
    ("cgnd", "Renouvelables", "Sources renouvelables (non dispatchables)"),
    ("gndgen", "Renouvelables", "Profils de production renouvelable"),
    ("gnd", "Renouvelables", "Sources renouvelables"),
    ("renw", "Renouvelables", "Sources renouvelables"),
    ("cbatte", "Stockage", "Batteries"),
    ("batt", "Stockage", "Batteries"),
    # Demande
    ("demand", "Demande", "Demande par système"),
    ("dbf", "Demande", "Demande par barre"),
    ("dbus", "Réseau", "Configuration des barres"),
    ("load", "Demande", "Demande"),
    ("cdef", "Demande", "Coûts de défaillance"),
    ("defcit", "Demande", "Coûts de défaillance"),
    # Réseau
    ("dcirc", "Réseau", "Circuits (lignes, transformateurs)"),
    ("dclink", "Réseau", "Liaisons à courant continu"),
    ("dlink", "Réseau", "Liaisons à courant continu"),
    ("interc", "Réseau", "Interconnexions entre systèmes"),
    ("sumcir", "Réseau", "Contraintes de somme de flux"),
    ("dsum", "Réseau", "Contraintes de somme de flux"),
    ("area", "Réseau", "Zones électriques"),
    # Contraintes et réserves
    ("creser", "Réserves", "Réserves de production"),
    ("reserv", "Réserves", "Réserves de production"),
    ("rsv", "Réserves", "Réserves de production"),
    ("cgc", "Contraintes", "Contraintes génériques"),
    ("generic", "Contraintes", "Contraintes génériques"),
    ("constr", "Contraintes", "Contraintes"),
    # Coût futur, résultats
    ("fcf", "Coût futur", "Fonction de coût futur"),
    ("costme", "Coût futur", "Coût futur"),
    ("*.hdr", "Séries binaires", "En-tête de série binaire (graf)"),
    ("*.bin", "Séries binaires", "Série binaire (graf)"),
    ("*.out", "Sorties", "Fichier de sortie / log SDDP"),
    ("*.log", "Sorties", "Fichier de log"),
]


def classify(rel_path: str) -> tuple[str, str]:
    """Retourne (catégorie, description) pour un chemin relatif."""
    name = PurePosixPath(rel_path).name.lower()
    for pattern, category, description in CATALOG:
        if any(c in pattern for c in "*?["):
            if fnmatch.fnmatch(name, pattern):
                return category, description
        elif pattern.endswith((".dat", ".csv", ".json")):
            if name == pattern:
                return category, description
        elif name.startswith(pattern):
            return category, description
    return "Autres", "Fichier non répertorié"
