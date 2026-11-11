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
K_DEFAUT, K_MAX = 50, 500  # nombre de résultats : par défaut, et au plus
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


EPSILON = 0.0001  # ε de la formule 4 : évite une division par zéro quand une composante ne varie pas

# Place de chaque descripteur dans le vecteur de 141 valeurs, pour le graphique des poids.
GROUPES = {"histogrammes": (0, 96), "moments": (96, 105), "dominantes": (105, 125), "glcm": (125, 131), "lbp": (131, 141)}


def chercher(affiner):
    """Code commun aux deux services de recherche.

    affiner = False : recherche simple, distance à poids égaux (formule 1).
    affiner = True  : retour de pertinence FRE. Le corps contient en plus « pertinentes », la liste
    complète des images cochées depuis le début : le serveur ne garde aucun état entre deux appels.
    """
    idx = index()
    if idx is None:
        return ABSENT
    corps = corps_json()
    k = corps.get("k", K_DEFAUT)
    if not est_entier(k) or not 5 <= k <= K_MAX:
        return {"erreur": f"k doit être un entier entre 5 et {K_MAX}."}, 400
    designations = [corps.get("requete")]
    if affiner:
        pertinentes = corps.get("pertinentes")
        if not isinstance(pertinentes, list) or len(pertinentes) > 500:
            return {"erreur": "« pertinentes » doit être une liste de 500 images au plus."}, 400
        designations += pertinentes

    # La base de recherche réunit GHIM-10K et la galerie de l'utilisateur, dans cet ordre.
    # Tout est normalisé avec les statistiques de GHIM-10K, fixes et communes à tous.
    dans_galerie, bruts = galerie()
    base = np.vstack([idx["normalises"], normaliser(bruts, idx["moyenne"], idx["ecart_type"])])
    nb_ghim = len(idx["chemins"])
    ids_galerie = [image["id"] for image in dans_galerie]

    # Ligne de chaque image désignée dans « base » ; la première est la requête.
    positions = []
    for designation in designations:
        source, id, erreur, code = lire_designation(designation, idx)
        if erreur:
            return {"erreur": erreur}, code
        positions.append(id if source == "ghim" else nb_ghim + ids_galerie.index(id))
    requete = positions[0]

    poids = None
    if affiner:
        # Ensemble pertinent R : la requête et les images cochées, chacune une seule fois.
        pertinents = base[list(dict.fromkeys(positions))]
        # Formule 4 : w_i = 1 / (ε + σ_i), σ_i étant l'écart-type de la composante i sur R.
        # Une composante qui varie peu entre les images pertinentes compte beaucoup, et inversement.
        # Si R ne contient que la requête, tous les σ_i sont nuls : poids égaux, donc recherche simple.
        poids = 1 / (EPSILON + pertinents.std(axis=0))
        # Nouvelle requête (tableau 1 du papier) : la moyenne des vecteurs de R.
        d = distances(base, pertinents.mean(axis=0), poids)
    else:
        d = distances(base, base[requete])

    # Tri par distance croissante. À distance égale (copie exacte), l'image requête passe en premier.
    autre = np.arange(len(base)) != requete
    # k + 1 lignes : en recherche simple, la requête elle-même (distance 0) puis les k images demandées.
    ordre = np.lexsort((autre, d))[:k + 1]

    def decrire(i):
        image = decrire_ghim(idx, int(i)) if i < nb_ghim else dans_galerie[i - nb_ghim]
        return {**image, "distance": float(d[i])}

    reponse = {"requete": decrire(requete), "resultats": [decrire(i) for i in ordre]}
    if affiner:
        # Part du poids total portée par chaque descripteur (la somme des 5 parts vaut 1).
        reponse["poids_par_descripteur"] = {
            nom: float(poids[debut:fin].sum() / poids.sum()) for nom, (debut, fin) in GROUPES.items()
        }
    return reponse


class Recherche(Resource):
    def post(self):
        """POST /api/recherche — la requête puis ses k images les plus proches : {requete: {source, id}, k}."""
        return chercher(affiner=False)


class Affiner(Resource):
    def post(self):
        """POST /api/recherche/affiner — retour de pertinence FRE : {requete, pertinentes: [...], k}."""
        return chercher(affiner=True)
