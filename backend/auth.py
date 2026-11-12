"""Authentification : inscription, connexion, déconnexion, session par cookie."""

import sqlite3

from flask import g, jsonify, request, session
from flask_restful import Resource
from werkzeug.security import check_password_hash, generate_password_hash

from db import connexion

# Seuls services accessibles sans session.
CHEMINS_PUBLICS = {"/api/auth/inscription", "/api/auth/connexion", "/api/sante", "/api/vitrine"}
# La vitrine de la page d'accueil sert aussi ses 24 fichiers : /api/vitrine/<n>/fichier.
PREFIXE_PUBLIC = "/api/vitrine/"


def exiger_session():
    """Exécutée avant chaque requête : refuse tout service /api sans session valide.

    La protection est faite ici, une seule fois, pour qu'un nouveau service
    soit protégé par défaut. L'utilisateur connecté est rangé dans g.utilisateur.
    """
    public = request.path in CHEMINS_PUBLICS or request.path.startswith(PREFIXE_PUBLIC)
    if not request.path.startswith("/api/") or public:
        return None
    g.utilisateur = connexion().execute(
        "SELECT id, nom FROM utilisateurs WHERE id = ?", (session.get("utilisateur_id"),)
    ).fetchone()
    if g.utilisateur is None:
        session.clear()  # cookie d'un compte qui n'existe plus
        return jsonify(erreur="Connexion requise."), 401
    return None


def lire_identifiants():
    """Lit « nom » et « mot_de_passe » du corps JSON. Renvoie (nom, mot_de_passe, erreur)."""
    corps = request.get_json(silent=True)
    if not isinstance(corps, dict):
        return None, None, "Le corps de la requête doit être un objet JSON."
    nom, mot_de_passe = corps.get("nom"), corps.get("mot_de_passe")
    if not isinstance(nom, str) or not isinstance(mot_de_passe, str):
        return None, None, "Le nom et le mot de passe sont obligatoires."
    return nom.strip(), mot_de_passe, None


def ouvrir_session(utilisateur):
    session.clear()
    session["utilisateur_id"] = utilisateur["id"]
    return {"id": utilisateur["id"], "nom": utilisateur["nom"]}


class Inscription(Resource):
    """POST /api/auth/inscription — crée un compte et ouvre la session."""

    def post(self):
        nom, mot_de_passe, erreur = lire_identifiants()
        if erreur:
            return {"erreur": erreur}, 400
        if not 3 <= len(nom) <= 30:
            return {"erreur": "Le nom doit contenir entre 3 et 30 caractères."}, 400
        if not 8 <= len(mot_de_passe) <= 128:
            return {"erreur": "Le mot de passe doit contenir entre 8 et 128 caractères."}, 400
        db = connexion()
        try:
            curseur = db.execute(
                "INSERT INTO utilisateurs (nom, mot_de_passe) VALUES (?, ?)",
                (nom, generate_password_hash(mot_de_passe)),
            )
            db.commit()
        except sqlite3.IntegrityError:  # contrainte UNIQUE sur le nom
            return {"erreur": "Ce nom est déjà utilisé."}, 409
        return ouvrir_session({"id": curseur.lastrowid, "nom": nom}), 201


class Connexion(Resource):
    """POST /api/auth/connexion — vérifie le mot de passe et ouvre la session."""

    def post(self):
        nom, mot_de_passe, erreur = lire_identifiants()
        if erreur:
            return {"erreur": erreur}, 400
        utilisateur = connexion().execute(
            "SELECT id, nom, mot_de_passe FROM utilisateurs WHERE nom = ?", (nom,)
        ).fetchone()
        # Même message dans les deux cas : on ne révèle pas si le nom existe.
        if utilisateur is None or not check_password_hash(utilisateur["mot_de_passe"], mot_de_passe):
            return {"erreur": "Nom ou mot de passe incorrect."}, 401
        return ouvrir_session(utilisateur)


class Deconnexion(Resource):
    """POST /api/auth/deconnexion — ferme la session."""

    def post(self):
        session.clear()
        return "", 204


class Moi(Resource):
    """GET /api/auth/moi — renvoie l'utilisateur connecté (401 sinon, par exiger_session)."""

    def get(self):
        return {"id": g.utilisateur["id"], "nom": g.utilisateur["nom"]}
