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
# Suppression du fond : écart de couleur (distance entre deux couleurs BGR, de 0 à 441) en dessous
# duquel un pixel ressemble au fond. Plus grand : on enlève plus, au risque de mordre sur l'objet.
SEUIL_FOND = 30


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
    """Passe l'image en niveaux de gris, enregistrée sur 3 canaux comme les autres (plus la transparence)."""
    resultat = cv2.cvtColor(cv2.cvtColor(pixels[:, :, :3], cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    return np.dstack([resultat, pixels[:, :, 3:]]), None


def fond(pixels, p):
    """Supprime le fond avec GrabCut : il devient transparent (image PNG).

    L'objet doit être vers le centre : une marge de 5 % sur chaque bord sert d'exemple de fond.
    Les descripteurs de la nouvelle image ne comptent que les pixels de l'objet.
    """
    transparence = pixels[:, :, 3] if pixels.shape[2] == 4 else None
    pixels = np.ascontiguousarray(pixels[:, :, :3])  # GrabCut ne travaille que sur une image en couleurs
    hauteur, largeur = pixels.shape[:2]
    if min(hauteur, largeur) < 20:
        return None, "L'image est trop petite pour supprimer le fond (20 pixels de côté au minimum)."
    # GrabCut est lent sur une grande image : le masque est calculé sur une copie de 400 pixels au plus.
    reduction = min(1, 400 / max(hauteur, largeur))
    petite = cv2.resize(pixels, None, fx=reduction, fy=reduction, interpolation=cv2.INTER_AREA)
    h, l = petite.shape[:2]
    marge_x, marge_y = max(1, l // 20), max(1, h // 20)
    rectangle = (marge_x, marge_y, l - 2 * marge_x, h - 2 * marge_y)  # tout ce qui est dehors est du fond
    masque = np.zeros((h, l), np.uint8)
    # Les deux tableaux de 65 valeurs sont la mémoire de travail de GrabCut (modèles du fond et de l'objet).
    cv2.grabCut(petite, masque, rectangle, np.zeros((1, 65)), np.zeros((1, 65)), 5, cv2.GC_INIT_WITH_RECT)

    # Seconde passe : un morceau de fond entouré par l'objet (le ciel entre les pales et la cabine
    # d'un hélicoptère) ne touche pas le bord, et la première passe le garde. On cherche les 5 couleurs
    # principales de la marge (k-moyennes) ; un pixel gardé proche de l'une d'elles devient « fond probable ».
    marges = (petite[:marge_y], petite[-marge_y:], petite[:, :marge_x], petite[:, -marge_x:])
    bord = np.concatenate([m.reshape(-1, 3) for m in marges]).astype(np.float32)
    critere = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1)
    _, _, couleurs_fond = cv2.kmeans(bord, 5, None, critere, 3, cv2.KMEANS_PP_CENTERS)
    ecart = np.linalg.norm(petite[:, :, None].astype(np.float32) - couleurs_fond, axis=3).min(axis=2)
    seconde = masque.copy()
    seconde[(seconde == cv2.GC_PR_FGD) & (ecart < SEUIL_FOND)] = cv2.GC_PR_BGD
    # GrabCut refuse un masque sans aucun pixel d'objet : on garde alors la première passe.
    if np.isin(seconde, (cv2.GC_FGD, cv2.GC_PR_FGD)).any():
        masque = seconde
        cv2.grabCut(petite, masque, None, np.zeros((1, 65)), np.zeros((1, 65)), 5, cv2.GC_INIT_WITH_MASK)

    # On garde l'objet sûr et l'objet probable.
    objet = np.isin(masque, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
    if objet.mean() < 0.01:
        return None, "Aucun objet trouvé vers le centre de l'image : le fond n'a pas pu être séparé."
    objet = cv2.resize(objet, (largeur, hauteur), interpolation=cv2.INTER_NEAREST)  # retour à la taille d'origine
    if transparence is not None:
        objet &= transparence > 0  # ce qui était déjà transparent le reste
    # 4e canal : 255 sur l'objet, 0 sur le fond (transparent). Le fond est aussi mis en noir.
    return np.dstack([pixels * objet[:, :, None], objet * 255]), None


# Nom du type reçu dans la requête → fonction qui l'applique.
TYPES = {"recadrage": recadrage, "echelle": echelle, "rotation": rotation, "miroir": miroir, "gris": gris,
         "fond": fond}

# Ce qui est ajouté au nom de la nouvelle image : le type et son paramètre.
# Exemples : plage_miroir_H.jpg, plage_echelle_0.5.jpg, plage_rotation_90.jpg, plage_recadrage_200x150.jpg.
ETIQUETTES = {
    "recadrage": lambda p: f"recadrage_{p['largeur']}x{p['hauteur']}",
    "echelle": lambda p: f"echelle_{p['facteur']:g}",  # :g écrit 2 et non 2.0
    "rotation": lambda p: f"rotation_{p['angle']}",
    "miroir": lambda p: "miroir_" + p["axe"][0].upper(),  # H ou V
    "gris": lambda p: "gris",
    "fond": lambda p: "sans_fond",
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
        pixels, masque = images.decoder(np.fromfile(images.dossier() / image["fichier"], np.uint8))
        if masque is not None:
            # Image transparente : la transparence est un 4e canal, transformé avec le reste.
            pixels = np.dstack([pixels, masque.astype(np.uint8) * 255])
        resultat, erreur = TYPES[type](pixels, corps)
        if erreur:
            return {"erreur": erreur}, 400

        # Une image transparente est enregistrée en PNG (le JPG n'a pas de transparence).
        origine = Path(image["nom"])
        transparente = resultat.shape[2] == 4
        extension = ".png" if transparente else origine.suffix
        # Nom de la nouvelle image : nom d'origine (raccourci s'il est très long) suivi de l'étiquette.
        nom = f"{origine.stem[:80]}_{ETIQUETTES[type](corps)}{extension}"
        contenu = cv2.imencode(extension.lower(), resultat)[1].tobytes()
        masque = resultat[:, :, 3] > 0 if transparente else None
        couleurs = np.ascontiguousarray(resultat[:, :, :3])
        return images.ajouter(nom, contenu, couleurs, image["categorie_id"], masque), 201
