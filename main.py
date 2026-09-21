"""Point d'entrée du projet « Une vie de fourmi ».

Le programme suit toujours les mêmes étapes, affichées à l'écran :

    1. lecture de la fourmilière (matrice d'adjacence + capacités) ;
    2. plus court chemin Sv → Sd, par parcours en largeur ;
    3. déplacement glouton des fourmis, étape par étape ;
    4. méthode exacte : flot maximum dans le réseau dilaté dans le temps ;
    5. vérification du planning optimal puis enregistrement dans solutions/.

Le glouton sert de comparaison : il est simple mais peut passer à côté du
minimum (il ne sait pas détourner les fourmis vers une voie plus longue mais
plus large). Le flot, lui, donne le minimum d'étapes.

Usage :
    python main.py                           toutes les fourmilières
    python main.py fourmiliere_un            une seule fourmilière
    python main.py fourmiliere_un --details  avec le détail des étapes
    python main.py --graphes                 affiche le graphe et l'animation
    python main.py --images                  enregistre les images dans images/
    python main.py --verifier                rejoue les plannings de solutions/
    python main.py --test                    vérifie le cas simple de l'énoncé
"""

from __future__ import annotations

import sys
from pathlib import Path

from ants import (
    DORTOIR,
    VESTIBULE,
    ErreurFourmiliere,
    exemple_du_sujet,
    format_planning,
    indice,
    lire_fourmiliere,
    lire_planning,
    plus_court_chemin,
    resoudre_glouton,
    resoudre_optimal,
    verifier_planning,
)

RACINE = Path(__file__).resolve().parent
DOSSIER_FOURMILIERES = RACINE / "fourmilieres"
DOSSIER_SOLUTIONS = RACINE / "solutions"
DOSSIER_IMAGES = RACINE / "images"


def importer_module_affichage(sans_fenetre: bool):
    """Importe le module d'affichage en choisissant un rendu adapté."""

    try:
        import matplotlib

        if sans_fenetre:
            matplotlib.use("Agg")  # pas de fenêtre : on écrit des images
        import graphes
    except ImportError as erreur:  # pragma: no cover - dépend de l'installation
        raise SystemExit(
            "matplotlib est nécessaire pour --graphes / --images : "
            "pip install -r requirements.txt"
        ) from erreur
    return graphes


def analyser_fourmiliere(chemin: Path, details: bool = False, fenetre: bool = False, images: bool = False):
    """Résout une fourmilière en suivant les cinq étapes du programme."""

    print(f"=== {chemin.name} ===")

    # --- Étape 1 : lecture -------------------------------------------------
    fourmiliere = lire_fourmiliere(chemin)
    tunnels = sum(sum(ligne) for ligne in fourmiliere["matrice"]) // 2
    print(
        f"Étape 1 - lecture : {fourmiliere['fourmis']} fourmis, "
        f"{len(fourmiliere['salles'])} salles, {tunnels} tunnels"
    )

    # --- Étape 2 : plus court chemin ---------------------------------------
    noms = fourmiliere["salles"]
    chemin_court = plus_court_chemin(
        fourmiliere, indice(fourmiliere, VESTIBULE), indice(fourmiliere, DORTOIR)
    )
    trajet = len(chemin_court) - 1
    print(
        f"Étape 2 - graphe : plus court chemin "
        f"{' -> '.join(noms[salle] for salle in chemin_court)} ({trajet} tunnels)"
    )

    # --- Étape 3 : glouton --------------------------------------------------
    glouton = resoudre_glouton(fourmiliere)
    verifier_planning(fourmiliere, glouton["etapes"])
    print(f"Étape 3 - glouton : dortoir atteint en {glouton['duree']} étapes (planning valide)")

    # --- Étape 4 : méthode exacte ------------------------------------------
    optimal = resoudre_optimal(fourmiliere)
    verifier_planning(fourmiliere, optimal["etapes"])
    commentaire = (
        "le glouton est optimal ici"
        if glouton["duree"] == optimal["duree"]
        else f"le glouton perd {glouton['duree'] - optimal['duree']} étapes"
    )
    print(f"Étape 4 - flot maximum : minimum de {optimal['duree']} étapes ({commentaire})")
    if details:
        print(format_planning(fourmiliere, optimal["etapes"]))

    # --- Étape 5 : enregistrement ------------------------------------------
    DOSSIER_SOLUTIONS.mkdir(exist_ok=True)
    entete = (
        f"{chemin.name} : {fourmiliere['fourmis']} fourmis, dortoir atteint en "
        f"{optimal['duree']} étapes (plus court trajet : {trajet} tunnels)\n\n"
    )
    (DOSSIER_SOLUTIONS / f"{chemin.stem}.txt").write_text(
        entete + format_planning(fourmiliere, optimal["etapes"]) + "\n", encoding="utf-8"
    )
    print(f"Étape 5 - planning optimal écrit dans solutions/{chemin.stem}.txt")

    # --- Bonus : graphes ---------------------------------------------------
    if fenetre or images:
        affichage = importer_module_affichage(sans_fenetre=images and not fenetre)
        if fenetre:
            affichage.animer(fourmiliere, optimal)
        if images:
            fichiers = affichage.enregistrer_images(
                fourmiliere, optimal, DOSSIER_IMAGES / chemin.stem
            )
            print(f"          {len(fichiers)} images écrites dans images/{chemin.stem}/")
    print()
    return fourmiliere, optimal, glouton


def verifier_cas_simple() -> None:
    """Vérifie le « cas simple » : 3 fourmis doivent arriver en 3 étapes."""

    print("=== cas simple de l'énoncé (3 fourmis, Sv-S1-Sd et Sv-S2-Sd) ===")
    fourmiliere = exemple_du_sujet()
    for methode, nom in ((resoudre_glouton, "glouton"), (resoudre_optimal, "flot maximum")):
        solution = methode(fourmiliere)
        verifier_planning(fourmiliere, solution["etapes"])
        print(f"--- {nom} : {solution['duree']} étapes ---")
        print(format_planning(fourmiliere, solution["etapes"]))
        if solution["duree"] != 3:
            raise SystemExit(f"échec : 3 étapes attendues, {solution['duree']} trouvées")
    print("Cas simple : 3 étapes avec les deux méthodes, plannings valides.\n")


def verifier_solutions() -> None:
    """Relit les plannings de ``solutions/`` et les rejoue règle par règle."""

    fichiers = sorted(DOSSIER_SOLUTIONS.glob("*.txt"))
    if not fichiers:
        raise SystemExit("aucun planning dans solutions/ : lancez d'abord « python main.py »")

    print("Vérification des plannings enregistrés dans solutions/")
    for chemin in fichiers:
        fourmiliere = lire_fourmiliere(chemin_demande(chemin.stem))
        etapes = lire_planning(fourmiliere, chemin.read_text(encoding="utf-8"))
        duree = verifier_planning(fourmiliere, etapes)
        minimum = resoudre_optimal(fourmiliere)["duree"]
        statut = "optimal" if duree == minimum else f"NON OPTIMAL ({minimum} étapes suffisent)"
        print(f"  {chemin.name:<34} {duree:>3} étapes, règles respectées, {statut}")
    print()


def chemin_demande(nom: str) -> Path:
    """Retrouve un fichier de fourmilière à partir d'un nom ou d'un chemin."""

    for candidat in (Path(nom), DOSSIER_FOURMILIERES / nom, DOSSIER_FOURMILIERES / f"{nom}.txt"):
        if candidat.is_file():
            return candidat
    raise SystemExit(f"Fourmilière introuvable : {nom}")


def main(arguments: list[str]) -> int:
    details = "--details" in arguments or "-d" in arguments
    fenetre = "--graphes" in arguments or "-g" in arguments
    images = "--images" in arguments or "-i" in arguments
    test = "--test" in arguments or "-t" in arguments
    verification = "--verifier" in arguments or "-v" in arguments

    if "-h" in arguments or "--help" in arguments:
        print(__doc__)
        return 0

    if verification:
        verifier_solutions()
        return 0

    if test:
        verifier_cas_simple()
        if len(arguments) == 1:
            return 0

    noms = [argument for argument in arguments if not argument.startswith("-")]
    if noms:
        fichiers = [chemin_demande(nom) for nom in noms]
    else:
        fichiers = sorted(DOSSIER_FOURMILIERES.glob("*.txt"))
    if not fichiers:
        raise SystemExit(f"aucune fourmilière trouvée dans {DOSSIER_FOURMILIERES}")

    resultats = []
    for chemin in fichiers:
        try:
            fourmiliere, optimal, glouton = analyser_fourmiliere(
                chemin, details=details, fenetre=fenetre, images=images
            )
        except ErreurFourmiliere as erreur:
            print(f"=== {chemin.name} ===\néchec : {erreur}\n")
            continue
        trajet = (
            len(
                plus_court_chemin(
                    fourmiliere, indice(fourmiliere, VESTIBULE), indice(fourmiliere, DORTOIR)
                )
            )
            - 1
        )
        resultats.append(
            (
                chemin.name,
                fourmiliere["fourmis"],
                trajet,
                glouton["duree"],
                optimal["duree"],
            )
        )

    if len(resultats) > 1:
        print("Récapitulatif")
        print(f"{'fourmilière':<34}{'fourmis':>8}{'trajet':>8}{'glouton':>9}{'minimum':>9}")
        for nom, nb_fourmis, trajet, duree_glouton, duree_min in resultats:
            print(f"{nom:<34}{nb_fourmis:>8}{trajet:>8}{duree_glouton:>9}{duree_min:>9}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
