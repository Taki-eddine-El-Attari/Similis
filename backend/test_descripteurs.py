"""Vérification des descripteurs. Lancer : .venv\\Scripts\\python.exe backend\\test_descripteurs.py

Utilise un dossier temporaire : la vraie base et les vrais fichiers ne sont pas touchés.
"""

import io
import sqlite3
import tempfile
from pathlib import Path

import cv2
import numpy as np

import descripteurs
from app import creer_app

# Image de test : un dégradé, un bloc de couleur et du bruit, pour que tous les descripteurs aient du contenu.
PHOTO = np.zeros((90, 120, 3), np.uint8)
PHOTO[:, :, 0] = np.linspace(0, 255, 120, dtype=np.uint8)
PHOTO[20:60, 30:90] = (40, 200, 230)
PHOTO[60:, :, 1] = np.random.default_rng(1).integers(0, 255, (30, 120), dtype=np.uint8)


def verifier_calcul():
    v = descripteurs.calculer(PHOTO)
    d = descripteurs.detailler(v)

    # Le vecteur fait 141 valeurs, toutes définies
    assert v.shape == (141,) and v.dtype == np.float32 and np.isfinite(v).all()
    # Deux calculs sur la même image sont identiques (k-means a une graine fixe)
    assert np.array_equal(v, descripteurs.calculer(PHOTO.copy()))

    # Histogrammes, LBP et proportions des couleurs dominantes sont des fréquences : leur somme vaut 1
    for canal in "rgb":
        assert len(d["histogrammes"][canal]) == 32 and abs(sum(d["histogrammes"][canal]) - 1) < 1e-5
    assert len(d["lbp"]) == 10 and abs(sum(d["lbp"]) - 1) < 1e-5
    proportions = [c["proportion"] for c in d["dominantes"]]
    assert len(proportions) == 5 and abs(sum(proportions) - 1) < 1e-5
    assert proportions == sorted(proportions, reverse=True)  # de la plus présente à la moins présente
    assert all(0 <= c[k] <= 1 for c in d["dominantes"] for k in "rgb")
    assert list(d["glcm"]) == ["contraste", "correlation", "energie", "homogeneite", "dissimilarite", "asm"]
    assert all(len(d["moments"][c]) == 3 for c in "hsv")

    # Histogrammes et LBP ne dépendent pas de la taille : la même image répétée 2 × 2 donne les mêmes histogrammes
    double = descripteurs.calculer(np.tile(PHOTO, (2, 2, 1)))
    assert np.allclose(double[:96], v[:96], atol=1e-6)

    # Valeurs connues : moitié noire, moitié blanche
    moitie = np.zeros((10, 20, 3), np.uint8)
    moitie[:, 10:] = 255
    m = descripteurs.detailler(descripteurs.calculer(moitie))
    assert m["histogrammes"]["r"][0] == 0.5 and m["histogrammes"]["r"][31] == 0.5
    assert m["moments"]["v"][:2] == [0.5, 0.5]  # moyenne 0,5 et écart-type 0,5 ; asymétrie nulle
    assert abs(m["moments"]["v"][2]) < 1e-6
    # Deux couleurs seulement pour 5 groupes : k-means répartit chaque couleur sur plusieurs groupes,
    # mais le total par couleur reste la moitié de l'image.
    assert all(c["r"] in (0, 1) for c in m["dominantes"])
    assert abs(sum(c["proportion"] for c in m["dominantes"] if c["r"] == 1) - 0.5) < 1e-5

    # Cas limites : image d'un seul pixel, image d'une seule couleur
    for petite in (np.full((1, 1, 3), 7, np.uint8), np.full((3, 50, 3), 200, np.uint8)):
        assert np.isfinite(descripteurs.calculer(petite)).all()


def verifier_api():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        app = creer_app(dossier)
        amine, sara = app.test_client(), app.test_client()
        amine.post("/api/auth/inscription", json={"nom": "Amine", "mot_de_passe": "motdepasse1"})
        sara.post("/api/auth/inscription", json={"nom": "Sara", "mot_de_passe": "motdepasse2"})
        png = cv2.imencode(".png", PHOTO)[1].tobytes()
        photo = amine.post("/api/images", content_type="multipart/form-data",
                           data={"fichiers": [(io.BytesIO(png), "photo.png")]}).json["creees"][0]["id"]

        def demander(images, client=amine):
            return client.post("/api/descripteurs", json={"images": images})

        def en_base(id):
            with sqlite3.connect(Path(dossier) / "similis.db") as db:
                return db.execute("SELECT descripteurs FROM images WHERE id = ?", (id,)).fetchone()[0]

        # Au chargement, les 141 valeurs sont rangées en base (float32 : 4 octets chacune)
        attendu = descripteurs.calculer(PHOTO)
        assert np.array_equal(np.frombuffer(en_base(photo), np.float32), attendu)

        # Le service renvoie les mêmes valeurs, découpées par descripteur
        reponse = demander([{"source": "galerie", "id": photo}])
        assert reponse.status_code == 200 and len(reponse.json) == 1
        d = reponse.json[0]
        assert (d["source"], d["id"]) == ("galerie", photo)
        assert d == {"source": "galerie", "id": photo, **descripteurs.detailler(attendu)}

        # Une image créée par transformation reçoit ses propres descripteurs
        grise = amine.post(f"/api/images/{photo}/transformations", json={"type": "gris"}).json["id"]
        assert not np.array_equal(np.frombuffer(en_base(grise), np.float32), attendu)
        # Plusieurs images à la fois, dans l'ordre demandé
        plusieurs = demander([{"source": "galerie", "id": grise}, {"source": "galerie", "id": photo}])
        assert [x["id"] for x in plusieurs.json] == [grise, photo]
        assert plusieurs.json[0]["moments"]["s"][0] == 0  # image grise : saturation nulle

        # Image chargée avant l'étape 5 (colonne vide) : calculée à la demande, puis rangée
        with sqlite3.connect(Path(dossier) / "similis.db") as db:
            db.execute("UPDATE images SET descripteurs = NULL WHERE id = ?", (photo,))
        assert demander([{"source": "galerie", "id": photo}]).json[0] == d
        assert np.array_equal(np.frombuffer(en_base(photo), np.float32), attendu)

        # Demandes invalides
        for corps in ({}, {"images": []}, {"images": "1"}, {"images": [photo]},
                      {"images": [{"source": "galerie"}]}, {"images": [{"source": "ailleurs", "id": photo}]},
                      {"images": [{"source": "galerie", "id": photo}] * 101}):
            assert amine.post("/api/descripteurs", json=corps).status_code == 400, corps
        # Image inconnue ou d'un autre utilisateur : 404 ; sans session : 401
        assert demander([{"source": "galerie", "id": 999}]).status_code == 404
        assert demander([{"source": "galerie", "id": photo}], client=sara).status_code == 404
        assert app.test_client().post("/api/descripteurs", json={"images": []}).status_code == 401


if __name__ == "__main__":
    verifier_calcul()
    verifier_api()
    print("Descripteurs : toutes les vérifications passent.")
