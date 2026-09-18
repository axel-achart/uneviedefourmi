"""Modélisation d'une fourmilière.

Ce module contient tout ce qui permet de lire une fourmilière décrite dans un
fichier texte, de la transformer en graphe (NetworkX) et de la dessiner
(matplotlib).

Format des fichiers de fourmilière :
    f=5             -> nombre de fourmis de la colonie
    S1              -> une salle de capacité 1
    S2 { 4 }        -> une salle pouvant accueillir 4 fourmis
    Sv - S1         -> un tunnel entre le vestibule et la salle 1
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

VESTIBULE = "Sv"
DORTOIR = "Sd"

# Écartement des salles sur le dessin (une colonne = une étape depuis le vestibule).
ECART_COLONNE = 1.6
ECART_RANG = 1.2

# f=5 / F=100
_RE_FOURMIS = re.compile(r"^[fF]\s*=\s*(\d+)$")
# S2 { 4 }  ou  S2
_RE_SALLE = re.compile(r"^(S\w+)\s*(?:\{\s*(\d+)\s*\})?$")
# Sv - S1
_RE_TUNNEL = re.compile(r"^(S\w+)\s*-\s*(S\w+)$")


@dataclass
class Salle:
    """Une salle de la fourmilière.

    La capacité vaut 1 par défaut ; le vestibule et le dortoir sont les deux
    seules salles à pouvoir accueillir toute la colonie en même temps.
    """

    nom: str
    capacite: float = 1

    @property
    def est_illimitee(self) -> bool:
        return self.capacite == math.inf

    def __str__(self) -> str:
        if self.est_illimitee:
            return self.nom
        return f"{self.nom}{{{int(self.capacite)}}}"


@dataclass
class Fourmiliere:
    """Une fourmilière : des salles, des tunnels et une colonie de fourmis."""

    nom: str = "fourmiliere"
    nb_fourmis: int = 0
    salles: dict[str, Salle] = field(default_factory=dict)
    tunnels: list[tuple[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        # Le vestibule et le dortoir existent toujours, sans limite de place.
        for nom in (VESTIBULE, DORTOIR):
            self.salles.setdefault(nom, Salle(nom, math.inf))

    @classmethod
    def depuis_fichier(cls, chemin: str | Path) -> "Fourmiliere":
        """Construit une fourmilière à partir d'un fichier texte."""
        chemin = Path(chemin)
        fourmiliere = cls(nom=chemin.stem)

        lignes = chemin.read_text(encoding="utf-8").splitlines()
        for numero, ligne in enumerate(lignes, 1):
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            fourmiliere._lire_ligne(ligne, numero)

        return fourmiliere

    def _lire_ligne(self, ligne: str, numero: int) -> None:
        """Interprète une ligne du fichier et l'ajoute à la fourmilière."""
        correspondance = _RE_FOURMIS.match(ligne)
        if correspondance is not None:
            self.nb_fourmis = int(correspondance.group(1))
            return

        correspondance = _RE_TUNNEL.match(ligne)
        if correspondance is not None:
            self.ajouter_tunnel(correspondance.group(1), correspondance.group(2))
            return

        correspondance = _RE_SALLE.match(ligne)
        if correspondance is not None:
            capacite = int(correspondance.group(2)) if correspondance.group(2) else 1
            self.ajouter_salle(correspondance.group(1), capacite)
            return

        raise ValueError(f"{self.nom} : ligne {numero} incomprise -> {ligne!r}")

    def ajouter_salle(self, nom: str, capacite: float = 1) -> Salle:
        """Ajoute une salle (vestibule et dortoir gardent leur capacité infinie)."""
        if nom in (VESTIBULE, DORTOIR):
            capacite = math.inf
        salle = self.salles.get(nom)
        if salle is None:
            salle = Salle(nom, capacite)
            self.salles[nom] = salle
        else:
            salle.capacite = capacite
        return salle

    def ajouter_tunnel(self, depart: str, arrivee: str) -> None:
        """Ajoute un tunnel, en créant au besoin les salles qu'il relie."""
        for nom in (depart, arrivee):
            if nom not in self.salles:
                self.ajouter_salle(nom)
        if (depart, arrivee) in self.tunnels or (arrivee, depart) in self.tunnels:
            return
        self.tunnels.append((depart, arrivee))

    # ------------------------------------------------------------------ #
    # Graphe
    # ------------------------------------------------------------------ #
    def graphe(self) -> nx.Graph:
        """Représente la fourmilière sous forme de graphe non orienté.

        Chaque salle est un noeud (portant sa capacité), chaque tunnel une
        arête : les tunnels se franchissent dans les deux sens.
        """
        G = nx.Graph(nom=self.nom, fourmis=self.nb_fourmis)
        for salle in self.salles.values():
            G.add_node(salle.nom, capacite=salle.capacite)
        G.add_edges_from(self.tunnels)
        return G

    def salles_ordonnees(self) -> list[str]:
        """Noms des salles triés : Sv, S1, S2, ... puis Sd."""
        return sorted(self.salles, key=_cle_tri)

    def matrice_adjacence(self):
        """Matrice d'adjacence de la fourmilière (salles triées)."""
        return nx.to_numpy_array(self.graphe(), nodelist=self.salles_ordonnees())

    def voisines(self, nom: str) -> list[str]:
        """Salles directement accessibles depuis `nom`."""
        return sorted(self.graphe().neighbors(nom), key=_cle_tri)

    def chemin_le_plus_court(self) -> list[str] | None:
        """Le plus court chemin du vestibule au dortoir, s'il en existe un."""
        try:
            return nx.shortest_path(self.graphe(), VESTIBULE, DORTOIR)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #
    def positions(self) -> dict[str, tuple[float, float]]:
        """Place les salles en colonnes, du vestibule (gauche) au dortoir (droite).

        La colonne d'une salle correspond à sa distance au vestibule : on lit
        ainsi le trajet des fourmis de gauche à droite.
        """
        G = self.graphe()
        distances = nx.single_source_shortest_path_length(G, VESTIBULE)
        profondeur = max(distances.values(), default=0)
        # Les salles jamais atteignables sont rejetées tout à droite.
        colonne_isolee = profondeur + 1

        colonnes: dict[int, list[str]] = {}
        for salle in self.salles_ordonnees():
            x = distances.get(salle, colonne_isolee)
            colonnes.setdefault(x, []).append(salle)

        # Le dortoir occupe toujours la dernière colonne : c'est l'arrivée.
        x_dortoir = distances.get(DORTOIR, colonne_isolee)
        derniere = max(colonnes)
        if x_dortoir != derniere or len(colonnes[derniere]) > 1:
            colonnes[x_dortoir].remove(DORTOIR)
            colonnes.setdefault(derniere + 1, []).append(DORTOIR)
            if not colonnes[x_dortoir]:
                del colonnes[x_dortoir]

        positions: dict[str, tuple[float, float]] = {}
        for x, salles in colonnes.items():
            for rang, salle in enumerate(salles):
                y = (rang - (len(salles) - 1) / 2) * ECART_RANG
                positions[salle] = (float(x) * ECART_COLONNE, y)
        return positions

    def dessiner(self, chemin_image: str | Path | None = None, afficher: bool = False):
        """Dessine le graphe de la fourmilière et l'enregistre si demandé."""
        G = self.graphe()
        pos = self.positions()

        couleurs = [_couleur(nom, G.nodes[nom]["capacite"]) for nom in G.nodes]
        tailles = [_taille(nom, G.nodes[nom]["capacite"]) for nom in G.nodes]
        etiquettes = {nom: _etiquette(nom, G.nodes[nom]["capacite"]) for nom in G.nodes}

        xs = [x for x, _ in pos.values()]
        ys = [y for _, y in pos.values()]
        largeur = max(8.0, 1.3 * (max(xs) - min(xs) + 2))
        hauteur = max(3.5, 1.0 * (max(ys) - min(ys) + 2))
        figure, ax = plt.subplots(figsize=(largeur, hauteur))

        _tracer_tunnels(G, pos, ax, list(G.edges), tailles, "#b08968", 1.6)
        # Le plus court chemin donne le trajet le plus direct vers le dortoir.
        chemin = self.chemin_le_plus_court()
        if chemin:
            aretes = list(zip(chemin, chemin[1:]))
            _tracer_tunnels(G, pos, ax, aretes, tailles, "#c1440e", 3.0)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=couleurs, node_size=tailles,
                               edgecolors="#4a3728", linewidths=1.5)
        nx.draw_networkx_labels(G, pos, ax=ax, labels=etiquettes, font_size=9,
                                font_weight="bold")

        titre = (f"{self.nom} — {self.nb_fourmis} fourmis, "
                 f"{G.number_of_nodes()} salles, {G.number_of_edges()} tunnels")
        if chemin:
            titre += f"\nplus court chemin : {' → '.join(chemin)} ({len(chemin) - 1} tunnels)"
        else:
            titre += "\naucun chemin ne mène du vestibule au dortoir"
        ax.set_title(titre, fontsize=11)
        ax.margins(0.12)
        ax.axis("off")
        figure.tight_layout()

        if chemin_image is not None:
            chemin_image = Path(chemin_image)
            chemin_image.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(chemin_image, dpi=150)
        if afficher:
            plt.show()
        else:
            plt.close(figure)
        return figure

    # ------------------------------------------------------------------ #
    def resume(self) -> str:
        """Description textuelle de la fourmilière."""
        salles = ", ".join(str(self.salles[nom]) for nom in self.salles_ordonnees())
        lignes = [
            f"Fourmilière « {self.nom} »",
            f"  fourmis : {self.nb_fourmis}",
            f"  salles  : {len(self.salles)} -> {salles}",
            f"  tunnels : {len(self.tunnels)}",
        ]
        chemin = self.chemin_le_plus_court()
        if chemin:
            lignes.append(f"  chemin le plus court : {' → '.join(chemin)} "
                          f"({len(chemin) - 1} tunnels)")
        else:
            lignes.append("  chemin le plus court : aucun (dortoir inaccessible)")
        return "\n".join(lignes)

    def __str__(self) -> str:
        return self.resume()


# ---------------------------------------------------------------------- #
# Utilitaires
# ---------------------------------------------------------------------- #
def _cle_tri(nom: str) -> tuple[int, int, str]:
    """Trie les salles : Sv d'abord, puis S1, S2, ... S10, et Sd en dernier."""
    if nom == VESTIBULE:
        return (0, 0, nom)
    if nom == DORTOIR:
        return (2, 0, nom)
    numero = re.search(r"\d+", nom)
    return (1, int(numero.group()) if numero else 0, nom)


def _tracer_tunnels(G: nx.Graph, pos: dict, ax, aretes: list, tailles: list,
                    couleur: str, epaisseur: float) -> None:
    """Trace des tunnels : droits entre salles voisines, courbés sinon.

    Un tunnel qui saute par-dessus d'autres salles passerait pile derrière
    elles s'il était droit : on le courbe pour qu'il reste visible.
    """
    droits, courbes = [], []
    for depart, arrivee in aretes:
        colonnes = abs(pos[depart][0] - pos[arrivee][0]) / ECART_COLONNE
        rangs = abs(pos[depart][1] - pos[arrivee][1]) / ECART_RANG
        voisines = colonnes < 1.01 and (colonnes > 0.99 or rangs < 1.01)
        (droits if voisines else courbes).append((depart, arrivee))

    if droits:
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=droits,
                               edge_color=couleur, width=epaisseur)
    if courbes:
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=courbes, node_size=tailles,
                               edge_color=couleur, width=epaisseur,
                               arrows=True, arrowstyle="-",
                               connectionstyle="arc3,rad=0.22")


def _couleur(nom: str, capacite: float) -> str:
    if nom == VESTIBULE:
        return "#8ecae6"   # l'entrée, près de la surface
    if nom == DORTOIR:
        return "#ffb703"   # l'objectif des fourmis
    if capacite > 1:
        return "#a7c957"   # salle spacieuse
    return "#e9edc9"       # salle simple : une fourmi à la fois


def _taille(nom: str, capacite: float) -> int:
    if nom in (VESTIBULE, DORTOIR):
        return 2200
    return 800 + 200 * min(int(capacite), 6)


def _etiquette(nom: str, capacite: float) -> str:
    if capacite == math.inf or capacite <= 1:
        return nom
    return f"{nom}\n({int(capacite)})"


def charger_fourmilieres(dossier: str | Path = "fourmilieres") -> list[Fourmiliere]:
    """Charge toutes les fourmilières d'un dossier, triées par nom de fichier."""
    return [Fourmiliere.depuis_fichier(f) for f in sorted(Path(dossier).glob("*.txt"))]
