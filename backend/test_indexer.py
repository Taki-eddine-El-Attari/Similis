"""Vérification du script d'indexation. Lancer : .venv\\Scripts\\python.exe backend\\test_indexer.py

Fabrique une mini-base de 6 images dans un dossier temporaire : GHIM-10K et le vrai index ne sont pas touchés.
"""

import tempfile
from pathlib import Path

import cv2
import numpy as np

import descripteurs
import indexer


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        base, sortie = Path(dossier) / "base", Path(dossier) / "index" / "mini.npz"
        hasard = np.random.default_rng(0)
        # Deux catégories de 3 images ; un nom de dossier avec un espace, comme « sea shores » dans GHIM-10K
        for categorie in ("sea shores", "arbres"):
            (base / categorie).mkdir(parents=True)
            for n in (3, 1, 2):  # créées dans le désordre : l'index doit quand même être trié
                pixels = hasard.integers(0, 255, (30, 40, 3), dtype=np.uint8)
                cv2.imencode(".jpg", pixels)[1].tofile(base / categorie / f"{n}.jpg")

        indexer.indexer(base, sortie)
        assert indexer.verifier(sortie) == 6
        index = np.load(sortie)

        # Chemins triés, catégorie = nom du dossier
        assert list(index["chemins"]) == ["arbres/1.jpg", "arbres/2.jpg", "arbres/3.jpg",
                                          "sea shores/1.jpg", "sea shores/2.jpg", "sea shores/3.jpg"]
        assert list(index["categories"]) == ["arbres"] * 3 + ["sea shores"] * 3

        # Chaque ligne est bien le vecteur de l'image du même rang
        pixels = cv2.imdecode(np.fromfile(base / "sea shores" / "2.jpg", np.uint8), cv2.IMREAD_COLOR)
        assert np.array_equal(index["vecteurs"][4], descripteurs.calculer(pixels))

        # Statistiques de normalisation
        assert np.allclose(index["moyenne"], index["vecteurs"].mean(axis=0), atol=1e-6)
        assert np.allclose(index["ecart_type"], index["vecteurs"].std(axis=0), atol=1e-6)

        # Une seconde indexation donne exactement le même contenu
        autre = Path(dossier) / "index" / "autre.npz"
        indexer.indexer(base, autre)
        assert all(np.array_equal(index[cle], np.load(autre)[cle]) for cle in index.files)

        # « limite » ne garde que les premières images
        indexer.indexer(base, autre, limite=2)
        assert indexer.verifier(autre) == 2

    print("Indexation : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
