"""Vérification du script d'évaluation. Lancer : .venv\\Scripts\\python.exe backend\\test_evaluer.py

Fabrique une mini-base de 24 images dans un dossier temporaire : GHIM-10K et le vrai index ne sont pas touchés.
"""

import csv
import tempfile
from pathlib import Path

import cv2
import numpy as np

import evaluer
import indexer
import recherche


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        dossier = Path(dossier)
        hasard = np.random.default_rng(0)
        # 4 catégories de 6 images, chacune d'une couleur nette : la recherche doit les retrouver facilement
        teintes = {"bleu": (210, 80, 20), "vert": (30, 180, 30), "rouge": (20, 30, 200), "gris": (128, 128, 128)}
        for nom, teinte in teintes.items():
            (dossier / "base" / nom).mkdir(parents=True)
            for n in range(6):
                pixels = np.clip(np.array(teinte) + hasard.integers(0, 30, (30, 40, 3)), 0, 255).astype(np.uint8)
                cv2.imencode(".png", pixels)[1].tofile(dossier / "base" / nom / f"{n}.jpg")
        fichier = dossier / "index.npz"
        indexer.indexer(dossier / "base", fichier)
        idx = recherche.charger(str(fichier), fichier.stat().st_mtime)

        requetes, precisions = evaluer.evaluer(idx, par_categorie=2, portee=5, iterations=3)

        # 2 requêtes par catégorie, toutes différentes, chacune bien dans sa catégorie
        assert len(requetes) == len(set(requetes)) == 8
        assert [idx["categories"][r] for r in requetes] == ["bleu"] * 2 + ["gris"] * 2 + ["rouge"] * 2 + ["vert"] * 2
        assert precisions.shape == (8, 3) and ((0 <= precisions) & (precisions <= 1)).all()
        # Couleurs nettes : les 5 autres images de la catégorie sont toutes retrouvées, à chaque itération.
        # Cela prouve aussi que l'image requête n'est pas comptée (sinon il n'y aurait que 4 bonnes sur 5).
        assert (precisions == 1).all()

        # Même graine : mêmes requêtes et mêmes résultats ; autre graine : autres requêtes
        memes, memes_precisions = evaluer.evaluer(idx, par_categorie=2, portee=5, iterations=3)
        assert memes == requetes and np.array_equal(memes_precisions, precisions)
        assert evaluer.evaluer(idx, par_categorie=2, portee=5, iterations=1, graine=1)[0] != requetes

        # Portée plus grande que la catégorie : la précision est plafonnée à 5 bonnes images sur 10
        assert (evaluer.evaluer(idx, par_categorie=1, portee=10, iterations=2)[1] == 0.5).all()

        # Tableau écrit : une ligne par itération, une colonne par catégorie
        sortie = dossier / "resultats" / "evaluation.csv"
        evaluer.ecrire(idx, requetes, precisions, sortie)
        lignes = list(csv.reader(open(sortie, encoding="utf-8")))
        assert lignes[0] == ["iteration", "precision", "bleu", "gris", "rouge", "vert"]
        assert lignes[1:] == [[str(i), "1.0000", "1.0000", "1.0000", "1.0000", "1.0000"] for i in (1, 2, 3)]

    print("Évaluation : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
