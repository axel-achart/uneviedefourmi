"""Affichage de la fourmilière et de ses habitantes (networkx + matplotlib).

Deux usages :

* ``dessiner(...)`` : une image du graphe, les fourmis étant posées sur les
  salles où elles se trouvent ;
* ``animer(...)`` : une fenêtre qui montre le déroulement étape par étape.

Les salles sont disposées en colonnes : l'abscisse est la distance au
vestibule, donc ``Sv`` est à gauche et ``Sd`` à droite. Les couleurs indiquent
l'occupation : bleu = vide, jaune clair = occupée, jaune = pleine.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from ants import DORTOIR, VESTIBULE, construire_graphe, distances, indice, occupation

COULEUR_VESTIBULE = "#8fd694"
COULEUR_DORTOIR = "#f2a1a1"
COULEUR_VIDE = "#dbe8f8"
COULEUR_OCCUPEE = "#f7e3b5"
COULEUR_PLEINE = "#f3c56b"
COULEUR_FOURMIS = "#a03030"

# Nombre de fourmis affichées par salle (au-delà, on écrit « +k »).
MAX_FOURMIS_AFFICHEES = 5


def cle_naturelle(salle: str) -> tuple[str, int]:
    """Clé de tri « humaine » : S2 avant S10, Sv et Sd à leur place."""

    chiffres = "".join(caractere for caractere in salle if caractere.isdigit())
    return (salle.rstrip("0123456789"), int(chiffres) if chiffres else 0)


def positions_par_niveaux(fourmiliere: dict) -> dict[str, tuple[float, float]]:
    """Place chaque salle en colonne selon sa distance au vestibule."""

    noms = fourmiliere["salles"]
    distance = distances(fourmiliere, indice(fourmiliere, VESTIBULE))

    par_niveau: dict[int, list[int]] = {}
    for salle, niveau in sorted(
        ((salle, distance[salle]) for salle in range(len(noms))),
        key=lambda paire: (paire[1], cle_naturelle(noms[paire[0]])),
    ):
        par_niveau.setdefault(niveau, []).append(salle)

    positions: dict[str, tuple[float, float]] = {}
    for niveau, salles in par_niveau.items():
        dernier = len(salles) - 1
        for rang, salle in enumerate(salles):
            positions[noms[salle]] = (niveau, dernier / 2 - rang)

    # Salles isolées (hors de la composante du vestibule) : parquées à droite.
    colonne = (max(par_niveau) + 1) if par_niveau else 0
    for rang, salle in enumerate(range(len(noms))):
        if noms[salle] not in positions:
            positions[noms[salle]] = (colonne, -rang)
    return positions


def etiquette_salle(fourmiliere: dict, salle: int) -> str:
    """Texte écrit dans une salle : son nom et sa capacité."""

    nom = fourmiliere["salles"][salle]
    if nom == VESTIBULE:
        return f"{nom}\n(départ)"
    if nom == DORTOIR:
        return f"{nom}\n(arrivée)"
    return f"{nom}\ncapacité {fourmiliere['capacites'][salle]}"


def couleur_salle(fourmiliere: dict, salle: int, contenu: dict[str, list[int]]) -> str:
    """Couleur d'une salle selon le nombre de fourmis présentes."""

    nom = fourmiliere["salles"][salle]
    if nom == VESTIBULE:
        return COULEUR_VESTIBULE
    if nom == DORTOIR:
        return COULEUR_DORTOIR
    presentes = len(contenu.get(nom, ()))
    if presentes == 0:
        return COULEUR_VIDE
    if presentes >= fourmiliere["capacites"][salle]:
        return COULEUR_PLEINE
    return COULEUR_OCCUPEE


def texte_fourmis(fourmis: list[int]) -> str:
    """Liste courte des fourmis d'une salle (« f1 f2 » ou « f1 f2 +3 »)."""

    if len(fourmis) <= MAX_FOURMIS_AFFICHEES:
        return " ".join(f"f{numero}" for numero in fourmis)
    montrees = " ".join(f"f{numero}" for numero in fourmis[:MAX_FOURMIS_AFFICHEES])
    return f"{montrees} +{len(fourmis) - MAX_FOURMIS_AFFICHEES}"


def dessiner(
    fourmiliere: dict,
    position: list[int] | None = None,
    titre: str | None = None,
    fichier: str | Path | None = None,
    figure: plt.Figure | None = None,
) -> plt.Figure:
    """Dessine la fourmilière ; renvoie la figure matplotlib.

    ``position`` donne la salle de chaque fourmi (numéro de fourmi = indice + 1).
    ``fichier`` permet d'enregistrer l'image au lieu de l'afficher.
    """

    graphe = construire_graphe(fourmiliere)
    positions = positions_par_niveaux(fourmiliere)
    contenu = occupation(fourmiliere, position) if position is not None else {}

    if figure is None:
        largeur = 3.0 + 1.6 * len(fourmiliere["salles"])
        figure = plt.figure(figsize=(min(largeur, 16), 6))
    figure.clear()
    axe = figure.add_subplot(111)
    axe.set_axis_off()

    couleurs = [
        couleur_salle(fourmiliere, salle, contenu) for salle in range(len(fourmiliere["salles"]))
    ]
    noms = fourmiliere["salles"]
    nx.draw_networkx_edges(graphe, positions, ax=axe, width=1.6, edge_color="#909090")
    nx.draw_networkx_nodes(
        graphe,
        positions,
        ax=axe,
        node_color=couleurs,
        node_size=2400,
        edgecolors="#404040",
        linewidths=1.2,
    )
    nx.draw_networkx_labels(
        graphe,
        positions,
        labels={noms[salle]: etiquette_salle(fourmiliere, salle) for salle in range(len(noms))},
        ax=axe,
        font_size=8,
    )

    for salle in range(len(noms)):
        fourmis = contenu.get(noms[salle], [])
        if not fourmis:
            continue
        abscisse, ordonnee = positions[noms[salle]]
        # Décalage exprimé en points : les fourmis restent collées sous leur
        # salle quelle que soit l'échelle des axes (une seule rangée, etc.).
        axe.annotate(
            texte_fourmis(fourmis),
            xy=(abscisse, ordonnee),
            xytext=(0, -30),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=7,
            color=COULEUR_FOURMIS,
        )

    axe.set_title(titre if titre else fourmiliere["nom"], fontsize=12)

    # Cadre fixe autour des salles : sans lui, une fourmilière « plate »
    # (toutes les salles sur une même ligne) serait étirée verticalement.
    abscisses = [abscisse for abscisse, _ in positions.values()]
    ordonnees = [ordonnee for _, ordonnee in positions.values()]
    axe.set_xlim(min(abscisses) - 0.7, max(abscisses) + 0.7)
    axe.set_ylim(min(ordonnees) - 0.7, max(ordonnees) + 0.7)
    figure.canvas.draw_idle()

    if fichier is not None:
        figure.savefig(fichier, dpi=110, bbox_inches="tight")
    return figure


def animer(fourmiliere: dict, solution: dict, pause: float = 0.8) -> None:
    """Affiche le déroulement étape après étape (fenêtre interactive)."""

    figure = plt.figure(figsize=(12, 6))
    plt.ion()
    for numero, position in enumerate(solution["etats"]):
        titre = (
            f"{fourmiliere['nom']} - départ ({fourmiliere['fourmis']} fourmis dans {VESTIBULE})"
            if numero == 0
            else f"{fourmiliere['nom']} - étape {numero}/{solution['duree']}"
        )
        dessiner(fourmiliere, position, titre=titre, figure=figure)
        figure.canvas.draw()
        figure.canvas.flush_events()
        plt.pause(pause)
    plt.ioff()
    plt.show()


def enregistrer_images(fourmiliere: dict, solution: dict, dossier: str | Path) -> list[Path]:
    """Enregistre une image PNG par étape (départ compris) et renvoie les chemins."""

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    images = []

    for numero, position in enumerate(solution["etats"]):
        titre = (
            f"{fourmiliere['nom']} - départ"
            if numero == 0
            else f"{fourmiliere['nom']} - étape {numero}/{solution['duree']}"
        )
        chemin = dossier / f"{numero:02d}_etape_{numero}.png"
        dessiner(fourmiliere, position, titre=titre, fichier=chemin)
        plt.close("all")
        images.append(chemin)
    return images
