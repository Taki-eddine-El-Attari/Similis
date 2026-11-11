"""Vérification du retour de pertinence FRE. Lancer : .venv\\Scripts\\python.exe backend\\test_affiner.py

Fabrique une mini-base GHIM de 18 images dans un dossier temporaire : rien de réel n'est touché.
"""

import io
import tempfile
from pathlib import Path

import cv2
import numpy as np

import indexer
import recherche
from app import creer_app

HASARD = np.random.default_rng(0)


def image(teinte, lisse):
    """Image d'une couleur (B, G, R) : unie avec un léger bruit si « lisse », sinon très bruitée."""
    bruit = HASARD.integers(0, 15 if lisse else 120, (30, 40, 3))
    return np.clip(np.array(teinte) + bruit, 0, 255).astype(np.uint8)


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        dossier = Path(dossier)
        base = dossier / "GHIM"
        # 3 couleurs × 2 textures (lisse ou bruitée), 3 images chacune : 6 catégories, 18 images
        teintes = {"bleu": (200, 90, 30), "vert": (40, 170, 40), "rouge": (30, 40, 190)}
        for couleur, teinte in teintes.items():
            for texture in ("lisse", "bruit"):
                (base / f"{couleur} {texture}").mkdir(parents=True)
                for n in range(3):
                    pixels = image(teinte, texture == "lisse")
                    cv2.imencode(".png", pixels)[1].tofile(base / f"{couleur} {texture}" / f"{n}.jpg")

        app = creer_app(dossier / "storage", ghim=base)
        amine, sara = app.test_client(), app.test_client()
        amine.post("/api/auth/inscription", json={"nom": "Amine", "mot_de_passe": "motdepasse1"})
        sara.post("/api/auth/inscription", json={"nom": "Sara", "mot_de_passe": "motdepasse2"})

        def affiner(requete, pertinentes, k=17, client=amine):
            return client.post("/api/recherche/affiner", json={
                "requete": {"source": "ghim", "id": requete},
                "pertinentes": [{"source": "ghim", "id": i} for i in pertinentes], "k": k})

        assert affiner(0, []).status_code == 503  # index absent
        indexer.indexer(base, dossier / "storage" / "index" / "ghim.npz")
        index = np.load(dossier / "storage" / "index" / "ghim.npz")
        categories = index["categories"].tolist()
        requete = categories.index("vert lisse")
        ordre = lambda reponse: [(r["source"], r["id"]) for r in reponse.json["resultats"]]

        # --- Sans image cochée, « Affiner » redonne la recherche simple ---
        simple = amine.post("/api/recherche", json={"requete": {"source": "ghim", "id": requete}, "k": 17})
        sans_coche = affiner(requete, [])
        assert sans_coche.status_code == 200 and ordre(sans_coche) == ordre(simple)
        assert np.allclose([r["distance"] for r in sans_coche.json["resultats"]],
                           [r["distance"] for r in simple.json["resultats"]], atol=1e-4)
        # Poids tous égaux : chaque descripteur pèse sa part de composantes (96, 9, 20, 6 et 10 sur 141)
        parts = sans_coche.json["poids_par_descripteur"]
        assert list(parts) == ["histogrammes", "moments", "dominantes", "glcm", "lbp"]
        assert np.allclose(list(parts.values()), np.array([96, 9, 20, 6, 10]) / 141, atol=1e-5)
        # Cocher la requête elle-même ne change rien : elle fait déjà partie de R
        assert ordre(affiner(requete, [requete])) == ordre(simple)

        # --- Avec des images cochées, les poids et l'ordre changent ---
        # On coche les images vertes bruitées : couleur commune, texture différente de la requête.
        verts_bruit = [i for i, c in enumerate(categories) if c == "vert bruit"]
        avec = affiner(requete, verts_bruit)
        assert avec.status_code == 200
        assert avec.json["poids_par_descripteur"] != parts and ordre(avec) != ordre(simple)
        assert abs(sum(avec.json["poids_par_descripteur"].values()) - 1) < 1e-5
        assert avec.json["requete"]["id"] == requete
        distances = [r["distance"] for r in avec.json["resultats"]]
        assert distances == sorted(distances)
        # Les 6 images vertes passent devant toutes les autres : la couleur compte, la texture moins
        assert {categories[r["id"]].split()[0] for r in avec.json["resultats"][:6]} == {"vert"}
        assert {categories[r["id"]].split()[0] for r in simple.json["resultats"][:6]} != {"vert"}

        # --- Le calcul suit les formules 3 et 4 du papier ---
        normalises = recherche.normaliser(index["vecteurs"], index["moyenne"], index["ecart_type"])
        pertinents = normalises[[requete] + verts_bruit]
        poids = 1 / (0.0001 + pertinents.std(axis=0))
        attendu = ((normalises - pertinents.mean(axis=0)) ** 2 * poids).sum(axis=1) / poids.sum()
        for resultat in avec.json["resultats"]:
            assert abs(resultat["distance"] - attendu[resultat["id"]]) < 1e-4
        assert [r["id"] for r in avec.json["resultats"]] == np.argsort(attendu, kind="stable")[:18].tolist()

        # Le serveur ne garde aucun état : le même appel redonne la même réponse, les doublons sont ignorés
        assert affiner(requete, verts_bruit).json == avec.json
        assert affiner(requete, verts_bruit + verts_bruit).json == avec.json

        # --- Une image de la galerie peut être cochée ; celle d'un autre compte non ---
        verte = cv2.imencode(".png", image(teintes["vert"], True))[1].tobytes()
        mienne = amine.post("/api/images", content_type="multipart/form-data",
                            data={"fichiers": [(io.BytesIO(verte), "pre.png")]}).json["creees"][0]["id"]
        corps = {"requete": {"source": "ghim", "id": requete}, "pertinentes": [{"source": "galerie", "id": mienne}], "k": 5}
        mixte = amine.post("/api/recherche/affiner", json=corps)
        assert mixte.status_code == 200 and len(mixte.json["resultats"]) == 6
        assert sara.post("/api/recherche/affiner", json=corps).status_code == 404

        # --- Demandes invalides ---
        bon = {"source": "ghim", "id": requete}
        for corps in ({"requete": bon}, {"requete": bon, "pertinentes": "3"}, {"requete": bon, "pertinentes": [3]},
                      {"requete": bon, "pertinentes": [bon] * 501}, {"pertinentes": []},
                      {"requete": bon, "pertinentes": [], "k": 2}):
            assert amine.post("/api/recherche/affiner", json=corps).status_code == 400, corps
        assert affiner(requete, [999]).status_code == 404
        assert app.test_client().post("/api/recherche/affiner", json={}).status_code == 401

    print("Retour de pertinence : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
