"""Vérification de l'authentification. Lancer : .venv\\Scripts\\python.exe backend\\test_auth.py

Utilise une base temporaire : la vraie base n'est pas touchée.
"""

import tempfile

from app import creer_app


def verifier():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        app = creer_app(dossier)
        client = app.test_client()
        bons = {"nom": "Amine", "mot_de_passe": "motdepasse1"}

        # Sans session : service protégé refusé, service public accepté
        assert client.get("/api/auth/moi").status_code == 401
        assert client.get("/api/sante").status_code == 200

        # Inscription : données invalides refusées
        for corps in ({"nom": "ab", "mot_de_passe": "motdepasse1"},
                      {"nom": "Amine", "mot_de_passe": "court"},
                      {"nom": 12, "mot_de_passe": "motdepasse1"},
                      ["pas", "un", "objet"]):
            assert client.post("/api/auth/inscription", json=corps).status_code == 400
        assert client.post("/api/auth/inscription", data="pas du json").status_code == 400

        # Inscription valide : compte créé, session ouverte
        reponse = client.post("/api/auth/inscription", json=bons)
        assert reponse.status_code == 201 and reponse.json["nom"] == "Amine"
        assert client.get("/api/auth/moi").json["nom"] == "Amine"

        # Le mot de passe n'est pas stocké en clair
        with app.app_context():
            from db import connexion
            stocke = connexion().execute("SELECT mot_de_passe FROM utilisateurs").fetchone()[0]
        assert "motdepasse1" not in stocke

        # Nom déjà pris, même avec une autre casse
        assert client.post("/api/auth/inscription",
                           json={"nom": "amine", "mot_de_passe": "motdepasse2"}).status_code == 409

        # Déconnexion : la session est fermée
        assert client.post("/api/auth/deconnexion").status_code == 204
        assert client.get("/api/auth/moi").status_code == 401

        # Connexion : mauvais mot de passe et nom inconnu donnent la même réponse
        mauvais = client.post("/api/auth/connexion", json={"nom": "Amine", "mot_de_passe": "mauvais123"})
        inconnu = client.post("/api/auth/connexion", json={"nom": "Personne", "mot_de_passe": "mauvais123"})
        assert mauvais.status_code == inconnu.status_code == 401
        assert mauvais.json == inconnu.json

        # Connexion valide
        assert client.post("/api/auth/connexion", json=bons).status_code == 200
        assert client.get("/api/auth/moi").status_code == 200

        # Cookie falsifié : refusé
        client.set_cookie("session", "valeur.inventee")
        assert client.get("/api/auth/moi").status_code == 401

    print("Authentification : toutes les vérifications passent.")


if __name__ == "__main__":
    verifier()
