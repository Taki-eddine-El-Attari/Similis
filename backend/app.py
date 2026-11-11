"""Similis — crée l'application Flask et déclare les routes de l'API."""

from pathlib import Path

from flasgger import Swagger
from flask import Flask
from flask_restful import Api, Resource

DOSSIER = Path(__file__).parent


class Sante(Resource):
    """GET /api/sante — permet de vérifier que l'API répond."""

    def get(self):
        return {"etat": "ok", "application": "Similis"}


def creer_app():
    app = Flask(__name__)
    api = Api(app)
    api.add_resource(Sante, "/api/sante")
    # Documentation interactive des services : http://localhost:5000/apidocs
    # « auth » vide : sans lui, la page de flasgger 0.9.7.1 lève une erreur JavaScript.
    Swagger(app, template_file=str(DOSSIER / "openapi.yaml"), config={"auth": {}}, merge=True)
    return app


if __name__ == "__main__":
    # Serveur de développement, accessible seulement depuis cette machine.
    creer_app().run(port=5000, debug=True)
