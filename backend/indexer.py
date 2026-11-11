"""Indexe GHIM-10K : calcule les 141 descripteurs de chaque image et les range dans un seul fichier.

À lancer une fois, avant la première recherche :
    .venv\\Scripts\\python.exe backend\\indexer.py

Le fichier produit, storage/index/ghim.npz, contient :
    vecteurs    10 000 × 141, float32   descripteurs bruts
    chemins     10 000                  chemin de chaque image dans data/GHIM-10K (« aircraft/10_5001.jpg »)
    categories  10 000                  nom du dossier : c'est la vérité terrain de l'évaluation
    moyenne, ecart_type   141           statistiques de normalisation, utilisées par la recherche

Une image est désignée partout par sa position dans ce fichier (0 à 9 999).
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np

import descripteurs

RACINE = Path(__file__).parent.parent
GHIM = RACINE / "data" / "GHIM-10K"
INDEX = RACINE / "storage" / "index" / "ghim.npz"


def indexer(dossier=GHIM, sortie=INDEX, limite=None):
    """Calcule l'index des images de « dossier » et l'écrit dans « sortie ».

    « limite » ne garde que les premières images : sert à essayer le script sans attendre.
    """
    # Les chemins sont triés : l'ordre des images, donc leur numéro, est toujours le même.
    chemins = sorted(image.relative_to(dossier).as_posix() for image in dossier.glob("*/*.jpg"))[:limite]
    if not chemins:
        sys.exit(f"Aucune image trouvée dans {dossier}")

    debut = time.perf_counter()
    vecteurs = np.zeros((len(chemins), descripteurs.TAILLE), np.float32)
    for i, chemin in enumerate(chemins):
        # np.fromfile puis imdecode : cv2.imread échoue sous Windows si le chemin contient un accent.
        pixels = cv2.imdecode(np.fromfile(dossier / chemin, np.uint8), cv2.IMREAD_COLOR)
        if pixels is None:
            sys.exit(f"Image illisible : {chemin}")
        vecteurs[i] = descripteurs.calculer(pixels)
        if (i + 1) % 500 == 0:
            print(f"{i + 1} / {len(chemins)} images, {time.perf_counter() - debut:.0f} s")

    sortie.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        sortie,
        vecteurs=vecteurs,
        chemins=np.array(chemins),
        categories=np.array([chemin.split("/")[0] for chemin in chemins]),
        # Moyenne et écart-type de chaque composante, calculés sur toute la base.
        moyenne=vecteurs.mean(axis=0, dtype=np.float64).astype(np.float32),
        ecart_type=vecteurs.std(axis=0, dtype=np.float64).astype(np.float32),
    )
    return time.perf_counter() - debut


def verifier(fichier=INDEX):
    """Relit l'index et contrôle son contenu. Renvoie le nombre d'images."""
    index = np.load(fichier)
    nombre = len(index["chemins"])
    assert index["vecteurs"].shape == (nombre, descripteurs.TAILLE) and index["vecteurs"].dtype == np.float32
    assert np.isfinite(index["vecteurs"]).all(), "valeur manquante dans l'index"
    assert len(index["categories"]) == nombre
    assert index["moyenne"].shape == index["ecart_type"].shape == (descripteurs.TAILLE,)
    assert list(index["chemins"]) == sorted(index["chemins"]), "les chemins ne sont pas triés"
    return nombre


if __name__ == "__main__":
    # Argument facultatif : nombre d'images à indexer, pour un essai rapide (python indexer.py 100).
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else None
    duree = indexer(limite=limite)
    nombre = verifier()
    categories = np.unique(np.load(INDEX)["categories"])
    print(f"Index écrit : {INDEX}")
    print(f"{nombre} images, {len(categories)} catégories, {duree:.0f} s ({1000 * duree / nombre:.0f} ms par image)")
