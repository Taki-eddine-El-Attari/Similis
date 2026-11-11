"""Similis — crée l'application Flask et déclare les routes de l'API."""

import secrets
from pathlib import Path

from flasgger import Swagger
from flask import Flask
from flask_restful import Api, Resource

import auth
import db

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


def creer_app(donnees=DOSSIER.parent / "data"):
    """Crée l'application. « donnees » est le dossier de la base et de la clé."""
    donnees = Path(donnees)
    donnees.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config["BASE"] = donnees / "similis.db"
    app.config["SECRET_KEY"] = cle_secrete(donnees)
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

    # Documentation interactive des services : http://localhost:5000/apidocs
    # « auth » vide : sans lui, la page de flasgger 0.9.7.1 lève une erreur JavaScript.
    Swagger(app, template_file=str(DOSSIER / "openapi.yaml"), config={"auth": {}}, merge=True)
    return app


if __name__ == "__main__":
    # Serveur de développement, accessible seulement depuis cette machine.
    creer_app().run(port=5000, debug=True)
