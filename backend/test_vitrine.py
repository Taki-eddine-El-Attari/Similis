"""Vérification de la vitrine publique. Lancer : .venv\\Scripts\\python.exe backend\\test_vitrine.py

La vitrine est la seule partie de la recherche ouverte sans session : il faut donc vérifier
ce qu'elle montre, et surtout ce qu'elle ne montre pas.
Fabrique une mini-base GHIM dans un dossier temporaire : rien de réel n'est touché.
"""

import tempfile
from pathlib import Path

import cv2
import numpy as np

import descripteurs
import evaluer
import indexer
import recherche
from app import creer_app


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        dossier = Path(dossier)
        base = dossier / "GHIM"
        hasard = np.random.default_rng(0)
        # 5 catégories de 8 images : la vitrine doit en garder 4 catégories de 6
        for c, categorie in enumerate(["avions", "barques", "cerfs", "dunes", "etangs"]):
            (base / categorie).mkdir(parents=True)
            for n in range(8):
                pixels = np.clip(40 * c + hasard.integers(0, 60, (30, 40, 3)), 0, 255).astype(np.uint8)
                cv2.imencode(".png", pixels)[1].tofile(base / categorie / f"{n}.jpg")

        app = creer_app(dossier / "storage", ghim=base)
        visiteur = app.test_client()  # aucun compte, aucune session

        # Sans index : 503, et la page d'accueil saura s'en passer
        assert visiteur.get("/api/vitrine").status_code == 503
        assert visiteur.get("/api/vitrine/0/fichier").status_code == 503

        indexer.indexer(base, dossier / "storage" / "index" / "ghim.npz")
        index = np.load(dossier / "storage" / "index" / "ghim.npz")
        idx = recherche.charger(str(dossier / "storage" / "index" / "ghim.npz"),
                                (dossier / "storage" / "index" / "ghim.npz").stat().st_mtime)

        # --- La vitrine répond sans session ---
        reponse = visiteur.get("/api/vitrine")
        assert reponse.status_code == 200
        vitrine = reponse.json
        images = vitrine["images"]
        # 4 catégories de 6 images, numérotées de 0 à 23, mélangées
        assert len(images) == 24 and [image["n"] for image in images] == list(range(24))
        categories = [image["categorie"] for image in images]
        assert sorted(set(categories)) == ["avions", "barques", "cerfs", "dunes"]
        assert all(categories.count(nom) == 6 for nom in set(categories))
        assert categories != sorted(categories)
        assert vitrine["total"] == 40 and 0 <= vitrine["exemple"] < 24
        assert vitrine["groupes"] == {"histogrammes": [0, 96], "moments": [96, 105], "dominantes": [105, 125],
                                      "glcm": [125, 131], "lbp": [131, 141]}

        # Chaque image porte son vecteur normalisé (141 valeurs) et ses 5 couleurs dominantes
        positions = recherche.vitrine(idx)
        for image, position in zip(images, positions):
            assert len(image["vecteur"]) == 141
            assert np.allclose(image["vecteur"], idx["normalises"][position], atol=5e-5)
            assert image["dominantes"] == descripteurs.detailler(index["vecteurs"][position])["dominantes"]
            assert image["categorie"] == index["categories"][position]

        # Toujours les mêmes images, dans le même ordre
        assert visiteur.get("/api/vitrine").json == vitrine

        # --- Précision mesurée par evaluer.py : absente tant qu'il n'a pas été lancé ---
        assert vitrine["evaluation"] == []
        tableau = dossier / "storage" / "evaluation.csv"
        requetes, precisions = evaluer.evaluer(idx, par_categorie=2, portee=5, iterations=3)
        evaluer.ecrire(idx, requetes, precisions, tableau)
        # Une valeur par itération : la moyenne sur toutes les requêtes, à 4 décimales
        attendu = [float(f"{valeur:.4f}") for valeur in precisions.mean(axis=0)]
        assert len(attendu) == 3 and visiteur.get("/api/vitrine").json["evaluation"] == attendu
        # Un tableau illisible ne casse pas la page d'accueil
        tableau.write_text("iteration,autre\n1,0.5\n", encoding="utf-8")
        assert visiteur.get("/api/vitrine").json["evaluation"] == []

        # --- Ses fichiers aussi, et seulement eux ---
        for n in (0, 23):
            fichier = visiteur.get(f"/api/vitrine/{n}/fichier")
            assert fichier.status_code == 200
            assert fichier.data == (base / index["chemins"][positions[n]]).read_bytes()
            fichier.close()
        assert visiteur.get("/api/vitrine/24/fichier").status_code == 404
        assert visiteur.get("/api/vitrine/-1/fichier").status_code == 404
        assert visiteur.get("/api/vitrine/0").status_code == 404

        # --- Tout le reste exige toujours une session ---
        for chemin in ("/api/ghim", "/api/ghim/0/fichier", "/api/images", "/api/categories", "/api/auth/moi",
                       "/api/vitrinee", "/api/vitrine2/0/fichier"):
            assert visiteur.get(chemin).status_code == 401, chemin
        for chemin in ("/api/recherche", "/api/recherche/affiner", "/api/descripteurs"):
            assert visiteur.post(chemin, json={}).status_code == 401, chemin
        # La vitrine ne se modifie pas
        assert visiteur.post("/api/vitrine", json={}).status_code == 405
        assert visiteur.delete("/api/vitrine/0/fichier").status_code == 405

    print("Vitrine : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
