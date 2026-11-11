"""Évalue la recherche et le retour de pertinence FRE sur GHIM-10K, sans intervention humaine.

Lancer, après l'indexation :
    .venv\\Scripts\\python.exe backend\\evaluer.py

Protocole, calqué sur le tableau 2 du papier :
    - vérité terrain : une image est pertinente si elle est dans le même dossier que la requête ;
    - requêtes : 5 images par catégorie, tirées avec une graine fixe, soit 100 requêtes ;
    - 25 résultats par recherche, sans compter l'image requête elle-même ;
    - 7 itérations ; la première est la recherche simple ;
    - retour simulé : après chaque itération, les résultats de la bonne catégorie sont ajoutés
      à l'ensemble pertinent R, comme le ferait un utilisateur qui les coche tous.

Sortie : la précision moyenne par itération, affichée et écrite dans storage/evaluation.csv
(une ligne par itération ; une colonne pour l'ensemble, puis une par catégorie).
"""

import csv
from pathlib import Path

import numpy as np

import indexer
import recherche

SORTIE = Path(__file__).parent.parent / "storage" / "evaluation.csv"


def evaluer(idx, par_categorie=5, portee=25, iterations=7, graine=0):
    """Renvoie (requêtes, précisions) : précisions[n, i] est la précision de la requête n à l'itération i."""
    base = idx["normalises"]
    categories = np.array(idx["categories"])
    # Graine fixe : les mêmes requêtes à chaque lancement, donc des résultats reproductibles.
    hasard = np.random.default_rng(graine)
    requetes = [
        int(image)
        for nom in sorted(set(idx["categories"]))
        for image in hasard.choice(np.flatnonzero(categories == nom), par_categorie, replace=False)
    ]

    precisions = np.zeros((len(requetes), iterations))
    for n, requete in enumerate(requetes):
        pertinents = [requete]  # l'ensemble R commence par la requête seule : c'est la recherche simple
        for i in range(iterations):
            # Même calcul que le service /api/recherche/affiner.
            nouvelle_requete, poids = recherche.retour_de_pertinence(base[pertinents])
            d = recherche.distances(base, nouvelle_requete, poids)
            d[requete] = np.inf  # l'image requête n'est pas comptée parmi les résultats
            resultats = np.argsort(d, kind="stable")[:portee]
            bons = resultats[categories[resultats] == categories[requete]]
            precisions[n, i] = len(bons) / portee
            # Retour simulé : les bons résultats rejoignent R (dict.fromkeys retire les doublons).
            pertinents = list(dict.fromkeys(pertinents + bons.tolist()))
    return requetes, precisions


def ecrire(idx, requetes, precisions, sortie=SORTIE):
    """Écrit le tableau des précisions moyennes : une ligne par itération."""
    categories = np.array(idx["categories"])[requetes]
    noms = sorted(set(categories.tolist()))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with open(sortie, "w", newline="", encoding="utf-8") as fichier:
        tableau = csv.writer(fichier)
        tableau.writerow(["iteration", "precision"] + noms)
        for i in range(precisions.shape[1]):
            par_categorie = [precisions[categories == nom, i].mean() for nom in noms]
            tableau.writerow([i + 1] + [f"{valeur:.4f}" for valeur in [precisions[:, i].mean()] + par_categorie])


if __name__ == "__main__":
    if not indexer.INDEX.exists():
        raise SystemExit("Index absent : lancer d'abord backend/indexer.py")
    idx = recherche.charger(str(indexer.INDEX), indexer.INDEX.stat().st_mtime)
    requetes, precisions = evaluer(idx)
    ecrire(idx, requetes, precisions)
    print(f"{len(requetes)} requêtes, 25 résultats, précision moyenne par itération :")
    for i, valeur in enumerate(precisions.mean(axis=0)):
        print(f"  itération {i + 1} : {valeur:.4f}" + ("  (recherche simple)" if i == 0 else ""))
    print(f"Tableau écrit : {SORTIE}")
