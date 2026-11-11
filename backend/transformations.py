"""Transformations : chacune crée une nouvelle image, l'originale est conservée."""

from pathlib import Path

import cv2
import numpy as np
from flask_restful import Resource

import images
from categories import corps_json, est_entier

# Une image agrandie ne dépasse pas cette taille, pour ne pas saturer la mémoire.
PIXELS_MAX = 40_000_000

ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
# L'axe est la ligne autour de laquelle l'image se retourne. Valeur : le code attendu par cv2.flip.
MIROIRS = {"horizontal": 0, "vertical": 1}


def recadrage(pixels, p):
    """Garde la zone (x, y, largeur, hauteur), qui doit être entièrement dans l'image."""
    x, y, largeur, hauteur = (p.get(cle) for cle in ("x", "y", "largeur", "hauteur"))
    if not all(est_entier(v) for v in (x, y, largeur, hauteur)):
        return None, "x, y, largeur et hauteur doivent être des entiers."
    haut_image, large_image = pixels.shape[:2]
    if x < 0 or y < 0 or largeur < 1 or hauteur < 1 or x + largeur > large_image or y + hauteur > haut_image:
        return None, "La zone de recadrage doit être entièrement dans l'image."
    return pixels[y:y + hauteur, x:x + largeur], None


def echelle(pixels, p):
    """Agrandit ou réduit l'image : facteur entre 0,1 et 4."""
    facteur = p.get("facteur")
    if isinstance(facteur, bool) or not isinstance(facteur, (int, float)) or not 0.1 <= facteur <= 4:
        return None, "Le facteur doit être un nombre entre 0,1 et 4."
    hauteur, largeur = pixels.shape[:2]
    largeur, hauteur = max(1, round(largeur * facteur)), max(1, round(hauteur * facteur))
    if largeur * hauteur > PIXELS_MAX:
        return None, "L'image agrandie serait trop grande (40 millions de pixels maximum)."
    # INTER_AREA donne le meilleur résultat pour réduire, INTER_CUBIC pour agrandir.
    methode = cv2.INTER_AREA if facteur < 1 else cv2.INTER_CUBIC
    return cv2.resize(pixels, (largeur, hauteur), interpolation=methode), None


def rotation(pixels, p):
    """Tourne l'image de 90, 180 ou 270 degrés, dans le sens des aiguilles d'une montre."""
    if p.get("angle") not in ROTATIONS or isinstance(p.get("angle"), bool):
        return None, "L'angle doit valoir 90, 180 ou 270."
    return cv2.rotate(pixels, ROTATIONS[p["angle"]]), None


def miroir(pixels, p):
    """Retourne l'image autour d'un axe : vertical échange la gauche et la droite, horizontal le haut et le bas."""
    if p.get("axe") not in MIROIRS:
        return None, "L'axe doit valoir « horizontal » ou « vertical »."
    return cv2.flip(pixels, MIROIRS[p["axe"]]), None


def gris(pixels, p):
    """Passe l'image en niveaux de gris, enregistrée sur 3 canaux comme les autres."""
    return cv2.cvtColor(cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR), None


# Nom du type reçu dans la requête → fonction qui l'applique.
TYPES = {"recadrage": recadrage, "echelle": echelle, "rotation": rotation, "miroir": miroir, "gris": gris}

# Ce qui est ajouté au nom de la nouvelle image : le type et son paramètre.
# Exemples : plage_miroir_H.jpg, plage_echelle_0.5.jpg, plage_rotation_90.jpg, plage_recadrage_200x150.jpg.
ETIQUETTES = {
    "recadrage": lambda p: f"recadrage_{p['largeur']}x{p['hauteur']}",
    "echelle": lambda p: f"echelle_{p['facteur']:g}",  # :g écrit 2 et non 2.0
    "rotation": lambda p: f"rotation_{p['angle']}",
    "miroir": lambda p: "miroir_" + p["axe"][0].upper(),  # H ou V
    "gris": lambda p: "gris",
}


class Transformations(Resource):
    def post(self, id):
        """POST /api/images/<id>/transformations — crée une nouvelle image dans la même catégorie."""
        image = images.trouver(id)
        if image is None:
            return {"erreur": "Image introuvable."}, 404
        corps = corps_json()
        type = corps.get("type")
        if not isinstance(type, str) or type not in TYPES:
            return {"erreur": "Type inconnu. Types acceptés : " + ", ".join(TYPES) + "."}, 400

        # np.fromfile puis imdecode : cv2.imread échoue sous Windows si le chemin contient un accent.
        octets = np.fromfile(images.dossier() / image["fichier"], np.uint8)
        pixels = cv2.imdecode(octets, cv2.IMREAD_COLOR)
        resultat, erreur = TYPES[type](pixels, corps)
        if erreur:
            return {"erreur": erreur}, 400

        # Nom de la nouvelle image : nom d'origine (raccourci s'il est très long) suivi de l'étiquette.
        origine = Path(image["nom"])
        nom = f"{origine.stem[:80]}_{ETIQUETTES[type](corps)}{origine.suffix}"
        contenu = cv2.imencode(origine.suffix.lower(), resultat)[1].tobytes()
        return images.ajouter(nom, contenu, resultat, image["categorie_id"]), 201
