"""Résolution des fourmilières.

Étape en place : lecture des fourmilières du dossier `fourmilieres/` et
représentation de chacune sous forme de graphe.

    python main.py                          # toutes les fourmilières -> graphes/*.png
    python main.py fourmilieres/fourmiliere_un.txt --afficher
"""

import argparse
import sys
from pathlib import Path

from ants import Fourmiliere, charger_fourmilieres

# La console Windows n'est pas en UTF-8 par défaut : les flèches des chemins
# feraient planter l'affichage.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOSSIER_FOURMILIERES = Path("fourmilieres")
DOSSIER_GRAPHES = Path("graphes")


def analyser_arguments() -> argparse.Namespace:
    parseur = argparse.ArgumentParser(description="Représente les fourmilières en graphes.")
    parseur.add_argument("fichiers", nargs="*", type=Path,
                         help="fichiers de fourmilière (par défaut : tout le dossier fourmilieres/)")
    parseur.add_argument("--afficher", action="store_true",
                         help="ouvre chaque graphe dans une fenêtre matplotlib")
    parseur.add_argument("--sortie", type=Path, default=DOSSIER_GRAPHES,
                         help="dossier où enregistrer les images (défaut : graphes/)")
    return parseur.parse_args()


def main() -> None:
    arguments = analyser_arguments()

    if arguments.fichiers:
        fourmilieres = [Fourmiliere.depuis_fichier(f) for f in arguments.fichiers]
    else:
        fourmilieres = charger_fourmilieres(DOSSIER_FOURMILIERES)

    if not fourmilieres:
        print(f"Aucune fourmilière trouvée dans {DOSSIER_FOURMILIERES}/")
        return

    for fourmiliere in fourmilieres:
        print(fourmiliere.resume())
        image = arguments.sortie / f"{fourmiliere.nom}.png"
        fourmiliere.dessiner(chemin_image=image, afficher=arguments.afficher)
        print(f"  graphe  : {image}\n")

    print(f"{len(fourmilieres)} fourmilière(s) représentée(s) dans {arguments.sortie}/")


if __name__ == "__main__":
    main()
