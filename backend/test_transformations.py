"""Vérification des transformations. Lancer : .venv\\Scripts\\python.exe backend\\test_transformations.py

Utilise un dossier temporaire : la vraie base et les vrais fichiers ne sont pas touchés.
"""

import io
import tempfile

import cv2
import numpy as np

from app import creer_app

# Image de départ : 40 × 30 pixels au hasard. En PNG (sans perte), on peut comparer pixel par pixel.
ORIGINE = np.random.default_rng(0).integers(0, 255, (30, 40, 3), dtype=np.uint8)


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        app = creer_app(dossier)
        amine, sara = app.test_client(), app.test_client()
        amine.post("/api/auth/inscription", json={"nom": "Amine", "mot_de_passe": "motdepasse1"})
        sara.post("/api/auth/inscription", json={"nom": "Sara", "mot_de_passe": "motdepasse2"})
        voyages = amine.post("/api/categories", json={"nom": "Voyages"}).json["id"]
        png = cv2.imencode(".png", ORIGINE)[1].tobytes()
        origine = amine.post("/api/images", content_type="multipart/form-data", data={
            "fichiers": [(io.BytesIO(png), "plage.png")], "categorie_id": str(voyages)}).json["creees"][0]["id"]

        def transformer(corps, client=amine, id=origine):
            return client.post(f"/api/images/{id}/transformations", json=corps)

        def pixels(image):
            """Relit le fichier d'une image par l'API et le décode."""
            reponse = amine.get(f"/api/images/{image['id']}/fichier")
            octets = np.frombuffer(reponse.data, np.uint8)
            reponse.close()
            return cv2.imdecode(octets, cv2.IMREAD_COLOR)

        # Les 5 transformations : chacune crée une nouvelle image correcte, dans la même catégorie
        attendus = {
            "recadrage": ({"x": 5, "y": 10, "largeur": 20, "hauteur": 15}, ORIGINE[10:25, 5:25]),
            "echelle": ({"facteur": 2}, cv2.resize(ORIGINE, (80, 60), interpolation=cv2.INTER_CUBIC)),
            "rotation": ({"angle": 90}, np.rot90(ORIGINE, k=-1)),  # k=-1 : sens des aiguilles d'une montre
            "miroir": ({"axe": "horizontal"}, ORIGINE[:, ::-1]),
            "gris": ({}, cv2.cvtColor(cv2.cvtColor(ORIGINE, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)),
        }
        for type, (parametres, attendu) in attendus.items():
            reponse = transformer({"type": type, **parametres})
            assert reponse.status_code == 201, (type, reponse.json)
            nouvelle = reponse.json
            assert nouvelle["nom"] == f"plage_{type}.png" and nouvelle["id"] != origine
            assert nouvelle["categorie_id"] == voyages
            assert (nouvelle["hauteur"], nouvelle["largeur"]) == attendu.shape[:2], type
            assert np.array_equal(pixels(nouvelle), attendu), type

        # Autres valeurs acceptées
        assert transformer({"type": "echelle", "facteur": 0.5}).json["largeur"] == 20
        assert np.array_equal(pixels(transformer({"type": "rotation", "angle": 180}).json), ORIGINE[::-1, ::-1])
        assert np.array_equal(pixels(transformer({"type": "rotation", "angle": 270}).json), np.rot90(ORIGINE))
        assert np.array_equal(pixels(transformer({"type": "miroir", "axe": "vertical"}).json), ORIGINE[::-1])

        # L'originale est conservée, intacte ; 9 nouvelles images à côté d'elle
        assert np.array_equal(pixels({"id": origine}), ORIGINE)
        assert len(amine.get(f"/api/images?categorie_id={voyages}").json) == 10
        assert amine.get(f"/api/images/{origine}").json["nom"] == "plage.png"

        # Paramètres invalides : 400, et aucune image créée
        for corps in (
            {}, {"type": "flou"}, {"type": ["gris"]},
            {"type": "recadrage", "x": 30, "y": 0, "largeur": 20, "hauteur": 10},   # dépasse à droite
            {"type": "recadrage", "x": -1, "y": 0, "largeur": 10, "hauteur": 10},
            {"type": "recadrage", "x": 0, "y": 0, "largeur": 0, "hauteur": 10},
            {"type": "recadrage", "x": 0.5, "y": 0, "largeur": 10, "hauteur": 10},
            {"type": "recadrage", "x": 0, "y": 0},
            {"type": "echelle", "facteur": 0.05}, {"type": "echelle", "facteur": 5},
            {"type": "echelle", "facteur": "2"}, {"type": "echelle", "facteur": True}, {"type": "echelle"},
            {"type": "rotation", "angle": 45}, {"type": "rotation", "angle": True}, {"type": "rotation"},
            {"type": "miroir", "axe": "diagonal"}, {"type": "miroir"},
        ):
            assert transformer(corps).status_code == 400, corps
        assert len(amine.get(f"/api/images?categorie_id={voyages}").json) == 10

        # Image d'un autre utilisateur, ou inexistante : 404
        assert transformer({"type": "gris"}, client=sara).status_code == 404
        assert transformer({"type": "gris"}, id=999).status_code == 404
        assert sara.get(f"/api/images/{origine}").status_code == 404

        # Une image JPG reste en JPG
        jpg = cv2.imencode(".jpg", ORIGINE)[1].tobytes()
        photo = amine.post("/api/images", content_type="multipart/form-data",
                           data={"fichiers": [(io.BytesIO(jpg), "photo.JPG")]}).json["creees"][0]["id"]
        grise = transformer({"type": "gris"}, id=photo).json
        assert grise["nom"] == "photo_gris.JPG" and grise["categorie_id"] is None
        reponse = amine.get(f"/api/images/{grise['id']}/fichier")
        assert reponse.mimetype == "image/jpeg" and reponse.data[:2] == b"\xff\xd8"
        reponse.close()

    print("Transformations : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
