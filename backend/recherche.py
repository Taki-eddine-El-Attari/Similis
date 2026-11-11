"""Recherche d'images par le contenu : index de GHIM-10K, services GHIM, descripteurs, recherche simple.

Une image est désignée partout par {"source": "galerie" | "ghim", "id": entier}.
Pour GHIM-10K, l'id est la position de l'image dans l'index (0 à 9 999).
"""

from collections import Counter
from functools import lru_cache
from math import ceil
from pathlib import Path

import numpy as np
from flask import current_app, g, request, send_file
from flask_restful import Resource

import descripteurs
import images
from categories import corps_json, est_entier
from db import connexion

PAR_PAGE = 60  # images GHIM par page
ABSENT = ({"erreur": "Index de GHIM-10K absent : lancer backend/indexer.py."}, 503)


# --- Index de GHIM-10K ---

def normaliser(vecteurs, moyenne, ecart_type):
    """Centre et réduit chaque composante : (valeur − moyenne) / écart-type.

    Sans cela, une composante aux grandes valeurs (le contraste GLCM) écraserait les autres
    dans la distance. Une composante d'écart-type nul est laissée à 0.
    """
    diviseur = np.where(ecart_type > 0, ecart_type, 1)
    return np.where(ecart_type > 0, (vecteurs - moyenne) / diviseur, 0).astype(np.float32)


@lru_cache(maxsize=2)
def charger(fichier, modifie_le):
    """Lit l'index et normalise ses vecteurs. Gardé en mémoire : lu une seule fois par lancement.

    « modifie_le » (date du fichier) fait relire l'index s'il a été recalculé entre-temps.
    """
    lu = np.load(fichier)
    return {
        "vecteurs": lu["vecteurs"],
        "chemins": lu["chemins"].tolist(),
        "categories": lu["categories"].tolist(),
        "moyenne": lu["moyenne"],
        "ecart_type": lu["ecart_type"],
        "normalises": normaliser(lu["vecteurs"], lu["moyenne"], lu["ecart_type"]),
    }


def index():
    """Renvoie l'index de GHIM-10K, ou None si le fichier n'existe pas encore."""
    fichier = Path(current_app.config["INDEX"])
    return charger(str(fichier), fichier.stat().st_mtime) if fichier.exists() else None


def decrire_ghim(idx, id):
    """Ce que l'API renvoie pour une image de GHIM-10K."""
    return {"source": "ghim", "id": id, "nom": Path(idx["chemins"][id]).name, "categorie": idx["categories"][id]}


# --- Images de la galerie de l'utilisateur ---

def galerie():
    """Renvoie les images de l'utilisateur connecté : (descriptions, vecteurs bruts, un par ligne)."""
    lignes = connexion().execute(
        """SELECT i.id, i.nom, i.fichier, c.nom AS categorie
           FROM images i LEFT JOIN categories c ON c.id = i.categorie_id
           WHERE i.utilisateur_id = ? ORDER BY i.id""",
        (g.utilisateur["id"],),
    ).fetchall()
    descriptions = [{"source": "galerie", "id": l["id"], "nom": l["nom"], "categorie": l["categorie"]} for l in lignes]
    vecteurs = np.array([images.vecteur(l) for l in lignes], np.float32).reshape(-1, descripteurs.TAILLE)
    return descriptions, vecteurs


def lire_designation(designation, idx):
    """Vérifie une désignation {source, id}. Renvoie (source, id, erreur, code HTTP de l'erreur)."""
    if not isinstance(designation, dict) or not est_entier(designation.get("id")):
        return None, None, 'Une image s\'écrit {"source": "galerie" ou "ghim", "id": 12}.', 400
    source, id = designation.get("source"), designation["id"]
    if source == "ghim" and 0 <= id < len(idx["chemins"]):
        return source, id, None, None
    if source == "galerie" and images.trouver(id) is not None:
        return source, id, None, None
    if source in ("ghim", "galerie"):
        return None, None, f"Image {id} introuvable.", 404
    return None, None, "Source inconnue. Sources acceptées : galerie, ghim.", 400


# --- Distance ---

def distances(base, requete, poids=None):
    """Distance entre la requête et chaque ligne de « base » (vecteurs normalisés).

    Formule 3 du papier : D(X, Y) = Σ w_i (x_i − y_i)² / Σ w_i.
    Sans poids, tous valent 1 : on retrouve la formule 1, Σ (x_i − y_i)² / d.
    """
    if poids is None:
        poids = np.ones(base.shape[1], np.float32)
    return ((base - requete) ** 2 * poids).sum(axis=1) / poids.sum()


# --- Services ---

class Ghim(Resource):
    def get(self):
        """GET /api/ghim?categorie=&page= — sans catégorie : les catégories ; avec : une page de ses images."""
        idx = index()
        if idx is None:
            return ABSENT
        categorie = request.args.get("categorie")
        if not categorie:
            return [{"nom": nom, "nb_images": nombre} for nom, nombre in sorted(Counter(idx["categories"]).items())]
        ids = [i for i, nom in enumerate(idx["categories"]) if nom == categorie]
        if not ids:
            return {"erreur": "Catégorie introuvable."}, 404
        pages = ceil(len(ids) / PAR_PAGE)
        page = min(max(request.args.get("page", 1, type=int) or 1, 1), pages)
        debut = (page - 1) * PAR_PAGE
        return {
            "images": [decrire_ghim(idx, i) for i in ids[debut:debut + PAR_PAGE]],
            "page": page,
            "pages": pages,
            "total": len(ids),
        }


class GhimFichier(Resource):
    def get(self, id):
        """GET /api/ghim/<id>/fichier — le fichier d'une image de GHIM-10K."""
        idx = index()
        if idx is None:
            return ABSENT
        if not 0 <= id < len(idx["chemins"]):
            return {"erreur": "Image introuvable."}, 404
        # La base ne change jamais : le navigateur peut garder l'image une journée.
        return send_file(Path(current_app.config["GHIM"]) / idx["chemins"][id], max_age=86400)


class Descripteurs(Resource):
    def post(self):
        """POST /api/descripteurs — descripteurs d'une ou plusieurs images : {images: [{source, id}, ...]}."""
        demandees = corps_json().get("images")
        if not isinstance(demandees, list) or not 1 <= len(demandees) <= 100:
            return {"erreur": "« images » doit être une liste de 1 à 100 images."}, 400
        # Sans index, les images de la galerie restent accessibles : on fait comme si GHIM était vide.
        idx = index() or {"chemins": [], "vecteurs": []}
        reponse = []
        for demandee in demandees:
            source, id, erreur, code = lire_designation(demandee, idx)
            if erreur:
                return {"erreur": erreur}, code
            # GHIM lit ses descripteurs dans l'index, la galerie dans la base.
            vecteur = idx["vecteurs"][id] if source == "ghim" else images.vecteur(images.trouver(id))
            reponse.append({"source": source, "id": id, **descripteurs.detailler(vecteur)})
        return reponse


class Recherche(Resource):
    def post(self):
        """POST /api/recherche — les k images les plus proches de la requête : {requete: {source, id}, k}."""
        idx = index()
        if idx is None:
            return ABSENT
        corps = corps_json()
        source, id, erreur, code = lire_designation(corps.get("requete"), idx)
        if erreur:
            return {"erreur": erreur}, code
        k = corps.get("k", 20)
        if not est_entier(k) or not 5 <= k <= 100:
            return {"erreur": "k doit être un entier entre 5 et 100."}, 400

        # La base de recherche réunit GHIM-10K et la galerie de l'utilisateur, dans cet ordre.
        # Tout est normalisé avec les statistiques de GHIM-10K, fixes et communes à tous.
        dans_galerie, bruts = galerie()
        base = np.vstack([idx["normalises"], normaliser(bruts, idx["moyenne"], idx["ecart_type"])])
        nb_ghim = len(idx["chemins"])
        position = id if source == "ghim" else nb_ghim + [image["id"] for image in dans_galerie].index(id)

        d = distances(base, base[position])
        # Tri par distance croissante. À distance égale (copie exacte), la requête passe en premier.
        autre = np.arange(len(base)) != position
        ordre = np.lexsort((autre, d))[:k]

        def decrire(i):
            image = decrire_ghim(idx, int(i)) if i < nb_ghim else dans_galerie[i - nb_ghim]
            return {**image, "distance": float(d[i])}

        return {"requete": decrire(position), "resultats": [decrire(i) for i in ordre]}
