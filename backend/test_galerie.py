"""Vérification des catégories et des images. Lancer : .venv\\Scripts\\python.exe backend\\test_galerie.py

Utilise un dossier temporaire : la vraie base et les vrais fichiers ne sont pas touchés.
"""

import io
import tempfile
import zipfile
from pathlib import Path

import cv2
import numpy as np

from app import creer_app


def image(extension=".jpg", largeur=40, hauteur=30):
    """Fabrique une petite image de test, encodée en mémoire."""
    pixels = np.random.default_rng(0).integers(0, 255, (hauteur, largeur, 3), dtype=np.uint8)
    return cv2.imencode(extension, pixels)[1].tobytes()


def envoyer(client, fichiers, categorie_id=None):
    """Envoie des fichiers [(nom, contenu)] comme le fait le formulaire du frontend."""
    donnees = {"fichiers": [(io.BytesIO(contenu), nom) for nom, contenu in fichiers]}
    if categorie_id is not None:
        donnees["categorie_id"] = str(categorie_id)
    return client.post("/api/images", data=donnees, content_type="multipart/form-data")


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        app = creer_app(dossier)
        amine, sara = app.test_client(), app.test_client()
        amine.post("/api/auth/inscription", json={"nom": "Amine", "mot_de_passe": "motdepasse1"})
        sara.post("/api/auth/inscription", json={"nom": "Sara", "mot_de_passe": "motdepasse2"})

        # Sans session : refusé
        assert app.test_client().get("/api/categories").status_code == 401
        assert app.test_client().get("/api/images").status_code == 401

        # --- Catégories ---
        voyages = amine.post("/api/categories", json={"nom": "Voyages"})
        assert voyages.status_code == 201 and voyages.json["parent_id"] is None
        voyages = voyages.json["id"]
        maroc = amine.post("/api/categories", json={"nom": "Maroc", "parent_id": voyages}).json["id"]
        # Nom vide, parent inconnu, parent d'un autre utilisateur
        assert amine.post("/api/categories", json={"nom": "  "}).status_code == 400
        assert amine.post("/api/categories", json={"nom": "X", "parent_id": 999}).status_code == 404
        assert sara.post("/api/categories", json={"nom": "X", "parent_id": voyages}).status_code == 404
        # Même nom sous le même parent : refusé, à la racine comme plus bas, sans tenir compte de la casse
        assert amine.post("/api/categories", json={"nom": "voyages"}).status_code == 409
        assert amine.post("/api/categories", json={"nom": "Maroc", "parent_id": voyages}).status_code == 409
        # Même nom sous un autre parent, ou chez un autre utilisateur : accepté
        assert amine.post("/api/categories", json={"nom": "Maroc"}).status_code == 201
        assert sara.post("/api/categories", json={"nom": "Voyages"}).status_code == 201
        # Renommer
        assert amine.put(f"/api/categories/{maroc}", json={"nom": "Maroc 2026"}).json["nom"] == "Maroc 2026"
        assert amine.put(f"/api/categories/{maroc}", json={"nom": ""}).status_code == 400
        assert sara.put(f"/api/categories/{maroc}", json={"nom": "Pirate"}).status_code == 404
        assert len(amine.get("/api/categories").json) == 3

        # --- Chargement : 3 images d'un coup, plus 3 fichiers refusés ---
        reponse = envoyer(amine, [
            ("a.jpg", image()), ("b.png", image(".png")), ("c.JPG", image(largeur=64, hauteur=48)),
            ("notes.txt", b"bonjour"),                 # mauvaise extension
            ("faux.jpg", b"ceci n'est pas une image"),  # bonne extension, contenu illisible
            ("gros.png", b"0" * (10 * 1024 * 1024 + 1)),  # plus de 10 Mo
        ])
        assert reponse.status_code == 201
        creees, refusees = reponse.json["creees"], reponse.json["refusees"]
        assert [i["nom"] for i in creees] == ["a.jpg", "b.png", "c.JPG"]
        assert (creees[2]["largeur"], creees[2]["hauteur"]) == (64, 48)
        assert [r["nom"] for r in refusees] == ["notes.txt", "faux.jpg", "gros.png"]
        assert "fichier" not in creees[0]  # le nom sur le disque n'est pas exposé
        a, b, c = (i["id"] for i in creees)
        # Les fichiers sont rangés dans un dossier au nom du compte, suivi de son id
        assert len(list((Path(dossier) / "uploads" / "Amine_1").glob("*.*"))) == 3
        # Un nom de compte ne peut pas servir de chemin : ses caractères spéciaux sont remplacés
        pirate = app.test_client()
        pirate.post("/api/auth/inscription", json={"nom": "../../x", "mot_de_passe": "motdepasse3"})
        assert envoyer(pirate, [("a.jpg", image())]).status_code == 201
        assert len(list((Path(dossier) / "uploads" / "______x_3").glob("*.jpg"))) == 1
        assert pirate.post("/api/images/suppression", json={"ids": [4]}).json == {"supprimees": 1}
        # Aucun fichier valide : 400 ; catégorie d'un autre : 404
        assert envoyer(amine, [("notes.txt", b"bonjour")]).status_code == 400
        assert envoyer(sara, [("a.jpg", image())], voyages).status_code == 404

        # --- Rangement ---
        assert len(amine.get("/api/images").json) == 3  # sans catégorie
        assert amine.put(f"/api/images/{a}", json={"categorie_id": voyages}).json["categorie_id"] == voyages
        assert amine.put(f"/api/images/{b}", json={"categorie_id": maroc}).status_code == 200
        assert amine.put(f"/api/images/{c}", json={"categorie_id": 999}).status_code == 404
        assert amine.put(f"/api/images/{c}", json={}).status_code == 400
        assert [i["id"] for i in amine.get(f"/api/images?categorie_id={voyages}").json] == [a]
        assert [i["id"] for i in amine.get("/api/images").json] == [c]
        compte = {cat["id"]: cat["nb_images"] for cat in amine.get("/api/categories").json}
        assert compte[voyages] == 1 and compte[maroc] == 1
        # Catégorie non vide (image ou sous-catégorie) : suppression refusée
        assert amine.delete(f"/api/categories/{maroc}").status_code == 409
        assert amine.delete(f"/api/categories/{voyages}").status_code == 409
        # Retour vers « sans catégorie »
        assert amine.put(f"/api/images/{b}", json={"categorie_id": None}).json["categorie_id"] is None
        assert amine.delete(f"/api/categories/{maroc}").status_code == 204

        # --- Téléchargement ---
        fichier = amine.get(f"/api/images/{a}/fichier")
        assert fichier.status_code == 200 and fichier.data == image()
        assert "attachment" not in fichier.headers.get("Content-Disposition", "")
        joint = amine.get(f"/api/images/{a}/fichier?telecharger=1")
        assert "attachment" in joint.headers["Content-Disposition"] and "a.jpg" in joint.headers["Content-Disposition"]
        # Sous Windows, un fichier encore ouvert ne peut pas être supprimé : on ferme les réponses.
        fichier.close()
        joint.close()
        archive = amine.post("/api/images/zip", json={"ids": [a, b]})
        assert archive.status_code == 200
        assert zipfile.ZipFile(io.BytesIO(archive.data)).namelist() == ["a.jpg", "b.png"]
        assert amine.post("/api/images/zip", json={"ids": []}).status_code == 400

        # --- Un second compte ne voit rien et ne peut rien toucher ---
        assert sara.get("/api/images").json == []
        assert [cat["nom"] for cat in sara.get("/api/categories").json] == ["Voyages"]
        assert sara.get(f"/api/images?categorie_id={voyages}").status_code == 404
        assert sara.get(f"/api/images/{a}/fichier").status_code == 404
        assert sara.put(f"/api/images/{a}", json={"categorie_id": None}).status_code == 404
        assert sara.delete(f"/api/images/{a}").status_code == 404
        assert sara.post("/api/images/zip", json={"ids": [a, b]}).status_code == 400
        assert sara.post("/api/images/suppression", json={"ids": [a, b, c]}).json == {"supprimees": 0}
        assert len(list((Path(dossier) / "uploads").rglob("*.*"))) == 3

        # --- Suppression : la ligne et le fichier disparaissent ---
        assert amine.delete(f"/api/images/{c}").status_code == 204
        assert amine.post("/api/images/suppression", json={"ids": [a, b, a, "x", 999]}).json == {"supprimees": 2}
        assert list((Path(dossier) / "uploads").rglob("*.*")) == []
        assert amine.get(f"/api/images/{a}/fichier").status_code == 404
        assert amine.delete(f"/api/categories/{voyages}").status_code == 204

    print("Galerie : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
