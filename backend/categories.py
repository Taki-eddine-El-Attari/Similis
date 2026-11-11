"""Catégories : hiérarchie libre, propre à chaque utilisateur."""

import sqlite3

from flask import g, request
from flask_restful import Resource

from db import connexion


def corps_json():
    """Renvoie le corps JSON de la requête, ou un dictionnaire vide s'il est absent ou invalide."""
    corps = request.get_json(silent=True)
    return corps if isinstance(corps, dict) else {}


def est_entier(valeur):
    """Vrai pour un entier JSON (true et false sont exclus : en Python ce sont aussi des int)."""
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def trouver(id):
    """Renvoie la catégorie « id » si elle appartient à l'utilisateur connecté, sinon None."""
    if not est_entier(id):
        return None
    return connexion().execute(
        "SELECT id, parent_id, nom FROM categories WHERE id = ? AND utilisateur_id = ?",
        (id, g.utilisateur["id"]),
    ).fetchone()


def lire_nom():
    """Lit « nom » du corps JSON. Renvoie (nom, erreur)."""
    nom = corps_json().get("nom")
    if not isinstance(nom, str) or not 1 <= len(nom.strip()) <= 50:
        return None, "Le nom doit contenir entre 1 et 50 caractères."
    return nom.strip(), None


class Categories(Resource):
    def get(self):
        """GET /api/categories — liste à plat ; le frontend construit l'arbre avec parent_id."""
        lignes = connexion().execute(
            """SELECT c.id, c.parent_id, c.nom, COUNT(i.id) AS nb_images
               FROM categories c LEFT JOIN images i ON i.categorie_id = c.id
               WHERE c.utilisateur_id = ?
               GROUP BY c.id ORDER BY c.nom""",
            (g.utilisateur["id"],),
        ).fetchall()
        return [dict(ligne) for ligne in lignes]

    def post(self):
        """POST /api/categories — crée une catégorie (parent_id nul : à la racine)."""
        nom, erreur = lire_nom()
        if erreur:
            return {"erreur": erreur}, 400
        parent_id = corps_json().get("parent_id")
        if parent_id is not None and trouver(parent_id) is None:
            return {"erreur": "Catégorie parente introuvable."}, 404
        db = connexion()
        try:
            curseur = db.execute(
                "INSERT INTO categories (utilisateur_id, parent_id, nom) VALUES (?, ?, ?)",
                (g.utilisateur["id"], parent_id, nom),
            )
            db.commit()
        except sqlite3.IntegrityError:  # index unique (parent, nom)
            return {"erreur": "Une catégorie porte déjà ce nom à cet endroit."}, 409
        return {"id": curseur.lastrowid, "parent_id": parent_id, "nom": nom, "nb_images": 0}, 201


class Categorie(Resource):
    def put(self, id):
        """PUT /api/categories/<id> — renomme la catégorie."""
        if trouver(id) is None:
            return {"erreur": "Catégorie introuvable."}, 404
        nom, erreur = lire_nom()
        if erreur:
            return {"erreur": erreur}, 400
        db = connexion()
        try:
            db.execute("UPDATE categories SET nom = ? WHERE id = ?", (nom, id))
            db.commit()
        except sqlite3.IntegrityError:
            return {"erreur": "Une catégorie porte déjà ce nom à cet endroit."}, 409
        return dict(trouver(id))

    def delete(self, id):
        """DELETE /api/categories/<id> — refusé (409) si elle contient des images ou des sous-catégories."""
        if trouver(id) is None:
            return {"erreur": "Catégorie introuvable."}, 404
        db = connexion()
        try:
            db.execute("DELETE FROM categories WHERE id = ?", (id,))
            db.commit()
        except sqlite3.IntegrityError:  # clés étrangères : la catégorie n'est pas vide
            return {"erreur": "Cette catégorie n'est pas vide : déplacez ou supprimez d'abord son contenu."}, 409
        return "", 204
