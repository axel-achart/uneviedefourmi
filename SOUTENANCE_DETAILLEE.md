---
marp: true
theme: default
paginate: true
---

<!--
SOUTENANCE "Une vie de fourmi" — 10 minutes maximum.
Ce fichier s'ouvre en slides avec l'extension VS Code "Marp for VS Code"
(commande : « Marp: Toggle Preview », export possible en PDF / PPTX).
Les blocs <!-- ... --> sont des notes d'orateur : non visibles en présentation.

Répartition conseillée pour un groupe de 3 personnes :
  A = slides 1, 2, 3, 4        (le problème + la modélisation)
  B = slides 5, 6, 7, 8, 9     (glouton, ses limites, la méthode exacte)
  C = slides 10, 11, 12        (résultats, démo, bilan)
Pour 4 personnes : découper les slides 7-8-9 en deux (réseau dilaté / flot + planning).
Pour 2 personnes : A garde 1-6, B garde 7-12.
-->

# Une vie de fourmi

## Ramener toute la colonie au dortoir, le plus vite possible

**Groupe :** *[Prénom Nom 1] · [Prénom Nom 2] · [Prénom Nom 3]*

*B3 — Projet Python — [date]*

<!-- 20 s — A. Slide affichée pendant qu'on se présente, pas de commentaire inutile. -->

---

# Le problème : ramener les fourmis au dortoir

Une fourmilière = des **salles** reliées par des **tunnels**. Toutes les fourmis
partent du **vestibule Sv** et doivent être **ramenées au dortoir Sd**.

**Les règles du jeu**

* 1 fourmi par salle — sauf `Si { k }` → `k` fourmis ; Sv et Sd illimités
* 1 seul tunnel franchi par fourmi **et par étape** (traversée instantanée)
* On n'entre dans une salle que si elle est vide, a une place libre, ou si
  l'occupant est en train de partir
* **Toutes les fourmis bougent en même temps**

**Ce qu'on doit rendre :** le **nombre minimal d'étapes** + le détail de
chaque déplacement (`+++ E1 +++` / `f1 - Sv - S1`).

<!-- 60 s — A. Insister sur le "en même temps" : c'est ce qui rend le problème
difficile (les fourmis se gênent). Exemple du sujet : 3 fourmis, 3 étapes. -->

---

# Modélisation : un graphe à capacités

* Salles = **sommets**, tunnels = **arêtes** → **matrice d'adjacence**
* Chaque salle porte une **capacité**

```
salles    = ["Sv", "S1", "S2", "Sd"]
capacités = [ 5,   1,   1,   5  ]        Sv - S1 - S2 - Sd
                                   matrice[i][j] = 1  ⇔  tunnel i - j
```

* **BFS** → distance Sv → Sd = **borne inférieure** (une fourmi seule)
* Pour `fourmiliere_un` : 3 tunnels + 5 fourmis, en file indienne →
  `distance + F - 1 = 3 + 5 - 1 = 7` étapes

<!-- 45 s — A. Montrer que la borne inférieure se lit directement dans le graphe ;
le vrai problème est le DÉBIT (combien de fourmis par étape), pas la distance. -->

---

# L'architecture du programme

```
main.py            → enchaîne les 5 étapes, compare les deux méthodes
 └─ ants.py        → le cerveau : lecture, BFS, glouton, flot, vérification
 └─ graphes.py     → les yeux : dessin du graphe, animation, PNG

fourmilieres/ (entrées)      → 9 fichiers
solutions/   (plannings)     → 1 planning optimal par fourmilière
```

**Toute l'algorithmique est écrite à la main** (BFS, glouton, Edmonds-Karp).
`networkx`/`matplotlib` servent uniquement à l'affichage.

<!-- 30 s — A. Slide "coupe-circuit n°1" : si on est en retard, passer directement
à la slide suivante, cette slide est la moins indispensable. -->

---

# Méthode 1 : le glouton

À chaque étape, pour chaque fourmi (en commençant par les plus proches de Sd) :

1. chercher une salle voisine **plus proche du dortoir** ;
2. avancer s'il reste une place libre **à la fin de l'étape** ;
3. sinon, attendre — puis appliquer tous les mouvements **simultanément**.

✔ Simple, rapide, et **optimal sur 7 fourmilières sur 9** (toutes celles
sans goulet).

<!-- 60 s — B. Montrer 2-3 étapes d'une petite fourmilière au tableau ou de tête
(fourmiliere_un : f1, f2, f3... en file indienne). -->

---

# Pourquoi le glouton échoue : le goulet

Il compare les **distances**, jamais les **débits**.

Dans `salle_d_at-ant` (100 fourmis) :

* chemin court : `Sv-S1-S2-S3-S4-S5-Sd`… mais `S4`/`S5` = **1 place** → 1 fourmi/étape ;
* détour long mais large : carrefour `S21` → chaîne de salles à **5 places** ;
* `S21` est *plus loin* de Sd → le glouton refuse d'y aller (il « recule »).

**Résultat : 98 étapes au lieu du minimum de 15.**

<!-- 60 s — B. Idée à faire passer : un chemin court mais étroit attire tout le
monde et bloque tout ; un détour plus long mais large est bien meilleur.
Autres cas : fourmiliere_cinq 17 vs 11, fourmiliere_3D 28 vs 14. -->

---

# Méthode 2 : le réseau dilaté dans le temps

On **recopie la fourmilière à chaque pas de temps** `t = 0, 1, 2, …` :

| Arc | Signification | Capacité |
|---|---|---|
| entrée(s,t) → sortie(s,t) | occuper une place dans la salle s | capacité de s |
| sortie(s,t) → entrée(s,t+1) | **attendre** | capacité de s |
| sortie(u,t) → entrée(v,t+1) | **traverser** le tunnel u-v | capacité de v |

* `SOURCE → Sv(0)` (les F fourmis), `Sd(t) → PUITS`

> **Un plan en T étapes existe ⇔ le flot maximum de Sv(0) à Sd(T) vaut F.**

Un plan = F chemins dans le réseau = un **flot entier** de valeur F.

<!-- 90 s — B. Slide clé de la soutenance : y passer du temps. Reformuler deux
fois l'équivalence, c'est LA justification de l'optimalité. -->

---

# Edmonds-Karp à la main + dichotomie

**Flot maximum** (aucune fonction de flot de `networkx`) :

1. chemin **augmentant** SOURCE → PUITS trouvé par **BFS** ;
2. faire passer le **goulot d'étranglement** ;
3. mettre à jour les capacités restantes + **arcs inverses** (pour annuler un mauvais choix) ;
4. recommencer → arrêt dès que F fourmis sont passées.

**Plus petit T** — `plan_possible(T)` est monotone :

* borne basse : la distance Sv → Sd ;
* borne haute : `distance + F` ;
* **dichotomie** → ~7 calculs de flot pour F = 100.

<!-- 60 s — B. Si on demande les maths : c'est le théorème flot entier / chemins
disjoints appliqué au réseau dilaté. -->

---

# Du flot au planning — et la vérification

* **`derouler`** : chaque arc de traversée transportant `k` unités =
  « `k` fourmis prennent ce tunnel à ce pas » ; on répartit entre les fourmis
  présentes (elles sont interchangeables).
* **`verifier_planning`** rejoue le plan et contrôle **chaque règle** :
  un déplacement par fourmi et par étape, tunnel existant, capacités
  respectées à chaque étape, toute la colonie au dortoir à la fin.

```bash
python main.py --verifier   # rejoue les 9 plannings de solutions/ → valides + optimaux
python main.py --test       # cas simple de l'énoncé (3 fourmis → 3 étapes)
```

<!-- 45 s — B. Message : on ne "croît" pas notre programme, on le vérifie.
C'est aussi ce qui rassure un jury sur la justesse des plannings livrés. -->

---

# Résultats sur les 9 fourmilières

| fourmilière | fourmis | glouton | **minimum** |
|---|---|---|---|
| fourmiliere_zero | 2 | 2 | **2** |
| fourmiliere_deux | 5 | 1 | **1** |
| fourmiliere_un / trois | 5 | 7 | **7** |
| fourmiliere_quatre | 10 | 9 | **9** |
| fourmiliere_cinq | 50 | 17 | **11** ↓ |
| fourmiliere_3D | 50 | 28 | **14** ↓ |
| La_hormiguera_de_la_muerte | 30 | 9 | **9** |
| salle_d_at-ant | 100 | **98** | **15** ↓ |

* Glouton optimal sur **7/9** · la méthode exacte toujours au minimum
* Les 9 fourmilières résolues en **~1 seconde** au total

<!-- 60 s — C. Commenter uniquement les 3 écarts (cinq, 3D, at-ant) :
c'est le cœur du message "on a mesuré, puis on a fait mieux". -->

---

# Démonstration

```bash
python main.py fourmiliere_cinq -d      # planning détaillé (11 étapes)
python main.py --verifier               # validation des 9 plannings
```

* Animation `-g` : graphe + fourmis étape par étape (vidéo de secours prête)
* `images/<fourmilière>/` : un PNG par étape (utilisé en secours si besoin)

<!-- 45 s — C. Slide "coupe-circuit n°2" : ne lancer la démo en direct que si
l'ordinateur et le vidéoprojecteur ont été testés. Sinon, montrer le GIF/PNG. -->

---

# Bilan

* Un problème de **graphe** qui cache un problème de **flot dans le temps**
* **Démarche incrémentale** : glouton simple → mesuré → méthode exacte prouvée
* Un résultat **vérifié automatiquement**, pas seulement affiché

**Perspectives :** plusieurs dortoirs ou plusieurs sorties ? contrainte de
temps sur les tunnels ? complexité sur de très grandes fourmilières ?

**Merci de votre attention — questions ?**

<!-- 30 s — C. Terminer net sur "Merci". Garder ~1 diapo de questions probables
sous la main (voir plus bas dans ce fichier). -->

---

<!--
====================================================================
NOTES HORS SLIDES — à ne PAS projeter
====================================================================

## Minutage cible (10 min max)

| # | Slide | Qui | Durée | Cumul |
|---|---|---|---|---|
| 1 | Titre | A | 0:20 | 0:20 |
| 2 | Le problème | A | 1:00 | 1:20 |
| 3 | Modélisation | A | 0:45 | 2:05 |
| 4 | Architecture (coupe n°1) | A | 0:30 | 2:35 |
| 5 | Glouton | B | 1:00 | 3:35 |
| 6 | Limites / goulet | B | 1:00 | 4:35 |
| 7 | Réseau dilaté | B | 1:30 | 6:05 |
| 8 | Edmonds-Karp + dichotomie | B | 1:00 | 7:05 |
| 9 | Flot → planning + vérif | B | 0:45 | 7:50 |
| 10 | Résultats | C | 1:00 | 8:50 |
| 11 | Démo (coupe n°2) | C | 0:45 | 9:35 |
| 12 | Bilan + questions | C | 0:30 | 10:05 |

Si vous êtes en retard : sauter la slide 4 puis la slide 11.
Si vous êtes en avance : détailler la slide 7 (équivalence plan ⇔ flot)
et montrer le tableau des résultats fourmilière par fourmilière.

## Questions probables du jury (réponses courtes)

* **Pourquoi une matrice d'adjacence ?** Le fichier ne donne que les tunnels ;
  `matrice[i][j] = 1` ⇔ tunnel i-j, les voisins sont la ligne i, le BFS tient
  en quelques lignes. (networkx uniquement pour dessiner.)
* **Pourquoi le glouton n'est pas optimal ?** Il ignore les débits : il
  s'engouffre dans le chemin le plus court même s'il est étroit.
* **Comment prouvez-vous l'optimalité ?** Si un plan en T étapes existait, le
  réseau dilaté aurait un flot de valeur F — or le test par dichotomie l'aurait
  détecté. Aucun algorithme ne peut faire mieux que le minimum de la dichotomie.
* **Deux fourmis peuvent-elles traverser le même tunnel à la même étape ?**
  Oui : un tunnel est une porte instantanée ; seule la capacité de la salle
  d'arrivée limite.
* **Peut-on attendre, et où ?** Oui, partout : c'est l'arc « attendre » du
  réseau, de capacité égale à celle de la salle.
* **Comment passez-vous du flot au planning ?** `derouler` relit les arcs :
  k unités transportées par un arc de traversée = k fourmis dans ce tunnel.
* **Complexité / durée ?** Réseau ≈ 2 × salles × (T+1) nœuds (≈ 1000 au max),
  Edmonds-Karp fait peu d'augmentations : ~1 s au total.
* **Que se passe-t-il si Sd est inaccessible ?** `ErreurFourmiliere` levée,
  `main.py` l'attrape et affiche un échec propre, sans planter.
* **Pourquoi avoir gardé le glouton ?** Il sert de référence mesurable et de
  méthode « simple » du cours ; la comparaison motive la méthode exacte.

## Check-list avant la soutenance

- [ ] Tester les commandes depuis le venv :
      `.venv/Scripts/python.exe main.py --verifier` (doit passer sans erreur)
- [ ] Démo animation `-g` : si la fenêtre Tk échoue depuis le venv, lancer
      d'abord `$env:TCL_LIBRARY='C:\Users\kylli\AppData\Local\Programs\Python\Python313\tcl\tcl8.6'`
- [ ] Préparer une **vidéo/GIF** de l'animation de `salle_d_at-ant` (15 étapes)
      et les PNG de `images/` comme secours
- [ ] Exporter les slides en **PDF** (Marp : « Export Slide Deck ») en secours
- [ ] Chronométrer une répétition complète : objectif **9 min 30**
-->
