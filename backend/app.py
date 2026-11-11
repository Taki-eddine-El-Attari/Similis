"""Similis — crée l'application Flask et déclare les routes de l'API."""

import secrets
from pathlib import Path

from flasgger import Swagger
from flask import Flask
from flask_restful import Api, Resource

import auth
import categories
import db
import images
import recherche
import transformations

DOSSIER = Path(__file__).parent


class Sante(Resource):
    """GET /api/sante — permet de vérifier que l'API répond."""

    def get(self):
        return {"etat": "ok", "application": "Similis"}


def cle_secrete(donnees):
    """Lit la clé qui signe les cookies de session ; la crée au premier lancement."""
    fichier = donnees / "cle_secrete"
    if not fichier.exists():
        fichier.write_bytes(secrets.token_bytes(32))
    return fichier.read_bytes()


def creer_app(donnees=DOSSIER.parent / "storage", ghim=DOSSIER.parent / "data" / "GHIM-10K"):
    """Crée l'application. « donnees » : dossier de la base, de la clé, des images et de l'index ; « ghim » : dossier de GHIM-10K."""
    donnees = Path(donnees)
    donnees.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config["BASE"] = donnees / "similis.db"
    app.config["UPLOADS"] = donnees / "uploads"
    app.config["INDEX"] = donnees / "index" / "ghim.npz"  # écrit par indexer.py
    app.config["GHIM"] = Path(ghim)  # images de GHIM-10K, en lecture seule
    app.config["SECRET_KEY"] = cle_secrete(donnees)
    # Taille maximale d'un envoi complet (plusieurs fichiers) ; au-delà : 413.
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
    # Le cookie de session n'est pas envoyé par les requêtes venant d'un autre site.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    db.initialiser(app)
    app.before_request(auth.exiger_session)

    api = Api(app)
    api.add_resource(Sante, "/api/sante")
    api.add_resource(auth.Inscription, "/api/auth/inscription")
    api.add_resource(auth.Connexion, "/api/auth/connexion")
    api.add_resource(auth.Deconnexion, "/api/auth/deconnexion")
    api.add_resource(auth.Moi, "/api/auth/moi")
    api.add_resource(categories.Categories, "/api/categories")
    api.add_resource(categories.Categorie, "/api/categories/<int:id>")
    api.add_resource(images.Images, "/api/images")
    api.add_resource(images.Image, "/api/images/<int:id>")
    api.add_resource(images.Fichier, "/api/images/<int:id>/fichier")
    api.add_resource(transformations.Transformations, "/api/images/<int:id>/transformations")
    api.add_resource(recherche.Descripteurs, "/api/descripteurs")
    api.add_resource(recherche.Ghim, "/api/ghim")
    api.add_resource(recherche.GhimFichier, "/api/ghim/<int:id>/fichier")
    api.add_resource(recherche.Recherche, "/api/recherche")
    api.add_resource(images.Zip, "/api/images/zip")
    api.add_resource(images.Suppression, "/api/images/suppression")

    # Documentation interactive des services : http://localhost:5000/apidocs
    # « auth » vide : sans lui, la page de flasgger 0.9.7.1 lève une erreur JavaScript.
    Swagger(app, template_file=str(DOSSIER / "openapi.yaml"), config={"auth": {}}, merge=True)
    return app


if __name__ == "__main__":
    # Serveur de développement, accessible seulement depuis cette machine.
    creer_app().run(port=5000, debug=True)
