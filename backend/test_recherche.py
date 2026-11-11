"""Vérification de la recherche simple. Lancer : .venv\\Scripts\\python.exe backend\\test_recherche.py

Fabrique une mini-base GHIM de 12 images dans un dossier temporaire : rien de réel n'est touché.
"""

import io
import tempfile
from pathlib import Path

import cv2
import numpy as np

import descripteurs
import indexer
import recherche
from app import creer_app

HASARD = np.random.default_rng(0)


def image_de_teinte(bleu, vert, rouge):
    """Image d'une couleur dominante, avec un peu de bruit pour que chaque image soit différente."""
    bruit = HASARD.integers(0, 40, (30, 40, 3))
    return np.clip(np.array([bleu, vert, rouge]) + bruit, 0, 255).astype(np.uint8)


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        dossier = Path(dossier)
        base = dossier / "GHIM"
        # Mini-base : 3 catégories de 4 images, chacune d'une couleur
        teintes = {"ciel": (200, 120, 30), "herbe": (40, 180, 40), "sunset rouge": (30, 40, 200)}
        for categorie, teinte in teintes.items():
            (base / categorie).mkdir(parents=True)
            for n in range(4):
                cv2.imencode(".png", image_de_teinte(*teinte))[1].tofile(base / categorie / f"{n}.jpg")

        app = creer_app(dossier / "storage", ghim=base)
        amine, sara = app.test_client(), app.test_client()
        amine.post("/api/auth/inscription", json={"nom": "Amine", "mot_de_passe": "motdepasse1"})
        sara.post("/api/auth/inscription", json={"nom": "Sara", "mot_de_passe": "motdepasse2"})

        def chercher(source, id, k=5, client=amine):
            return client.post("/api/recherche", json={"requete": {"source": source, "id": id}, "k": k})

        # Sans index : 503 avec un message clair ; sans session : 401
        assert amine.get("/api/ghim").status_code == 503
        assert chercher("ghim", 0).status_code == 503
        assert app.test_client().get("/api/ghim").status_code == 401

        indexer.indexer(base, dossier / "storage" / "index" / "ghim.npz")
        index = np.load(dossier / "storage" / "index" / "ghim.npz")

        # --- Parcourir GHIM ---
        assert amine.get("/api/ghim").json == [
            {"nom": "ciel", "nb_images": 4}, {"nom": "herbe", "nb_images": 4}, {"nom": "sunset rouge", "nb_images": 4}]
        page = amine.get("/api/ghim?categorie=herbe").json
        assert (page["page"], page["pages"], page["total"]) == (1, 1, 4)
        assert page["images"][0] == {"source": "ghim", "id": 4, "nom": "0.jpg", "categorie": "herbe"}
        assert amine.get("/api/ghim?categorie=sunset rouge&page=99").json["page"] == 1  # page ramenée à la dernière
        assert amine.get("/api/ghim?categorie=inconnue").status_code == 404
        fichier = amine.get("/api/ghim/4/fichier")
        assert fichier.status_code == 200 and fichier.data == (base / "herbe" / "0.jpg").read_bytes()
        fichier.close()
        assert amine.get("/api/ghim/12/fichier").status_code == 404

        # --- Recherche depuis une image GHIM ---
        reponse = chercher("ghim", 5)
        assert reponse.status_code == 200
        resultats = reponse.json["resultats"]
        # La requête sort en premier, avec une distance 0 ; les distances vont en croissant
        assert resultats[0] == {"source": "ghim", "id": 5, "nom": "1.jpg", "categorie": "herbe", "distance": 0}
        assert reponse.json["requete"] == resultats[0]
        assert [r["distance"] for r in resultats] == sorted(r["distance"] for r in resultats)
        assert len(resultats) == 6  # la requête, puis k = 5 images
        # Les 4 premières sont les 4 images vertes
        assert {r["categorie"] for r in resultats[:4]} == {"herbe"}

        # La distance suit la formule 1 : Σ (x − y)² / d sur les vecteurs centrés-réduits
        # (dans cette mini-base, certaines composantes ne varient pas : leur écart-type nul est remplacé par 1,
        # ce qui laisse leur différence à 0)
        ecart_type = np.where(index["ecart_type"] > 0, index["ecart_type"], 1)
        x = (index["vecteurs"][5] - index["moyenne"]) / ecart_type
        y = (index["vecteurs"][resultats[1]["id"]] - index["moyenne"]) / ecart_type
        assert abs(resultats[1]["distance"] - np.sum((x - y) ** 2) / 141) < 1e-4

        # --- La base de recherche réunit GHIM et la galerie de l'utilisateur ---
        verte = cv2.imencode(".png", image_de_teinte(*teintes["herbe"]))[1].tobytes()
        copie = (base / "ciel" / "2.jpg").read_bytes()  # copie exacte d'une image GHIM
        chargees = amine.post("/api/images", content_type="multipart/form-data", data={
            "fichiers": [(io.BytesIO(verte), "prairie.png"), (io.BytesIO(copie), "copie.png")]}).json["creees"]
        prairie, double = (c["id"] for c in chargees)
        rangement = amine.post("/api/categories", json={"nom": "Nature"}).json["id"]
        amine.put(f"/api/images/{prairie}", json={"categorie_id": rangement})

        resultats = chercher("ghim", 5).json["resultats"]
        assert {"source": "galerie", "id": prairie, "nom": "prairie.png", "categorie": "Nature"}.items() \
            <= next(r for r in resultats if r["source"] == "galerie").items()
        assert {r["source"] for r in resultats} == {"ghim", "galerie"}

        # --- Recherche depuis une image de la galerie ---
        resultats = chercher("galerie", prairie).json["resultats"]
        assert (resultats[0]["source"], resultats[0]["id"], resultats[0]["distance"]) == ("galerie", prairie, 0)
        assert {r["categorie"] for r in resultats[1:5]} == {"herbe"}
        # Copie exacte d'une image GHIM : deux distances nulles, la requête reste en premier
        resultats = chercher("galerie", double).json["resultats"]
        assert (resultats[0]["source"], resultats[0]["id"]) == ("galerie", double)
        assert (resultats[1]["source"], resultats[1]["id"], resultats[1]["distance"]) == ("ghim", 2, 0)

        # La galerie d'un autre utilisateur n'entre pas dans sa recherche, et ne peut pas servir de requête
        assert all(r["source"] == "ghim" for r in chercher("ghim", 5, k=14, client=sara).json["resultats"])
        assert chercher("galerie", prairie, client=sara).status_code == 404

        # --- Nombre de résultats ---
        assert len(chercher("ghim", 0, k=100).json["resultats"]) == 14  # toute la base : 12 GHIM + 2 galerie
        assert len(amine.post("/api/recherche", json={"requete": {"source": "ghim", "id": 0}}).json["resultats"]) == 14
        for k in (4, 101, "20", 7.5, True):
            assert chercher("ghim", 0, k=k).status_code == 400, k

        # --- Requêtes invalides ---
        for corps in ({}, {"requete": 5}, {"requete": {"source": "ghim"}}, {"requete": {"source": "web", "id": 1}}):
            assert amine.post("/api/recherche", json=corps).status_code == 400, corps
        assert chercher("ghim", 12).status_code == 404 and chercher("ghim", -1).status_code == 404
        assert chercher("galerie", 999).status_code == 404

        # --- Descripteurs d'une image GHIM : lus dans l'index ---
        reponse = amine.post("/api/descripteurs", json={"images": [
            {"source": "ghim", "id": 7}, {"source": "galerie", "id": prairie}]})
        assert reponse.status_code == 200 and [d["source"] for d in reponse.json] == ["ghim", "galerie"]
        assert reponse.json[0] == {"source": "ghim", "id": 7, **descripteurs.detailler(index["vecteurs"][7])}
        assert amine.post("/api/descripteurs", json={"images": [{"source": "ghim", "id": 12}]}).status_code == 404

    # Une composante d'écart-type nul est laissée à 0, sans division par zéro
    normalise = recherche.normaliser(np.array([[1, 5], [3, 5]], np.float32), np.array([2, 5]), np.array([1, 0]))
    assert normalise.tolist() == [[-1, 0], [1, 0]]
    # Avec des poids, la distance devient la formule 3 : Σ w (x − y)² / Σ w
    lignes = np.array([[0, 0], [2, 4]], np.float32)
    assert recherche.distances(lignes, lignes[0]).tolist() == [0, 10]
    assert recherche.distances(lignes, lignes[0], np.array([3, 1], np.float32)).tolist() == [0, 7]

    print("Recherche : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
