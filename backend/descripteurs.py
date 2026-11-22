"""Descripteurs visuels d'une image : un vecteur de 141 valeurs (couleur puis texture).

Positions dans le vecteur :
    0–95     histogrammes R, G, B (32 cases chacun)
    96–104   moments de couleur en HSV (moyenne, écart-type, asymétrie pour H, S, V)
    105–124  5 couleurs dominantes (R, G, B, proportion)
    125–130  texture GLCM (6 propriétés)
    131–140  texture LBP (histogramme de 10 motifs)

Ce fichier ne dépend pas de Flask : il sert à l'API et au script d'indexation de GHIM-10K.
"""

import cv2
import numpy as np
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern

TAILLE = 141
CASES = 32  # cases par histogramme de couleur
K = 5  # nombre de couleurs dominantes
PROPRIETES_GLCM = ["contrast", "correlation", "energy", "homogeneity", "dissimilarity", "ASM"]
# Noms français des mêmes propriétés, dans le même ordre, pour la réponse de l'API.
NOMS_GLCM = ["contraste", "correlation", "energie", "homogeneite", "dissimilarite", "asm"]


def histogrammes(pixels):
    """96 valeurs : histogrammes R, G, B de 32 cases, divisés par le nombre de pixels."""
    nb_pixels = pixels.shape[0] * pixels.shape[1]
    # OpenCV range les canaux dans l'ordre B, G, R : on les lit à l'envers (2, 1, 0).
    return np.concatenate([
        np.histogram(pixels[:, :, canal], bins=CASES, range=(0, 256))[0] / nb_pixels
        for canal in (2, 1, 0)
    ])


def moments(pixels):
    """9 valeurs : moyenne, écart-type et asymétrie de H, puis de S, puis de V (canaux entre 0 et 1)."""
    hsv = cv2.cvtColor(pixels, cv2.COLOR_BGR2HSV_FULL)  # _FULL : H va de 0 à 255, comme S et V
    valeurs = []
    for canal in range(3):
        # ponytail: un canal entier en float32 ; réduire l'image avant si de très grandes photos saturent la mémoire
        x = hsv[:, :, canal].astype(np.float32) / 255
        moyenne = x.mean(dtype=np.float64)
        ecart = x - moyenne
        # Asymétrie : racine cubique du moment centré d'ordre 3, pour rester dans l'unité du canal.
        asymetrie = np.cbrt(np.mean(ecart ** 3, dtype=np.float64))
        valeurs += [moyenne, np.sqrt(np.mean(ecart ** 2, dtype=np.float64)), asymetrie]
    return np.array(valeurs)


def dominantes(pixels, masque=None):
    """20 valeurs : 5 couleurs (R, G, B entre 0 et 1, proportion), de la plus présente à la moins présente."""
    # L'image est d'abord réduite (plus grand côté à 100 pixels) pour que k-means reste rapide.
    hauteur, largeur = pixels.shape[:2]
    rapport = 100 / max(hauteur, largeur)
    petite, petit_masque = pixels, masque
    if rapport < 1:
        taille = (max(1, round(largeur * rapport)), max(1, round(hauteur * rapport)))
        petite = cv2.resize(pixels, taille, interpolation=cv2.INTER_AREA)
        if masque is not None:
            petit_masque = cv2.resize(masque.astype(np.uint8), taille, interpolation=cv2.INTER_NEAREST) > 0
    if masque is None:
        points = petite.reshape(-1, 3)
    else:
        # Seulement les pixels de l'objet ; si la réduction les a tous perdus, ceux de l'image d'origine.
        points = petite[petit_masque] if petit_masque.any() else pixels[masque]
    points = points.astype(np.float32)
    if len(points) < K:  # image de moins de 5 pixels : on répète ses pixels
        points = np.resize(points, (K, 3))
    # Graine fixée : une même image donne toujours les mêmes couleurs.
    cv2.setRNGSeed(0)
    arret = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, etiquettes, centres = cv2.kmeans(points, K, None, arret, 3, cv2.KMEANS_PP_CENTERS)
    proportions = np.bincount(etiquettes.ravel(), minlength=K) / len(points)
    ordre = np.argsort(-proportions, kind="stable")
    rgb = centres[ordre][:, ::-1] / 255  # B, G, R → R, G, B
    return np.column_stack([rgb, proportions[ordre]]).ravel()


def glcm(gris, masque=None):
    """6 valeurs : contraste, corrélation, énergie, homogénéité, dissimilarité, ASM.

    Matrice de cooccurrence sur 256 niveaux, distance 1, directions 0°, 45°, 90° et 135°,
    symétrique et normalisée ; chaque propriété est la moyenne des 4 directions.
    """
    angles = [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]
    if masque is None:
        matrice = graycomatrix(gris, distances=[1], angles=angles, levels=256, symmetric=True, normed=True)
    else:
        # Les pixels hors de l'objet reçoivent un 257e niveau (256), puis sa ligne et sa colonne sont
        # retirées : seules restent les paires de deux pixels de l'objet. graycoprops renormalise la matrice.
        niveaux = gris.astype(np.uint16)
        niveaux[~masque] = 256
        matrice = graycomatrix(niveaux, distances=[1], angles=angles, levels=257, symmetric=True)[:256, :256]
    return np.array([graycoprops(matrice, propriete).mean() for propriete in PROPRIETES_GLCM])


def lbp(gris, masque=None):
    """10 valeurs : histogramme des motifs LBP uniformes (8 voisins, rayon 1), divisé par le nombre de pixels."""
    motifs = local_binary_pattern(gris, P=8, R=1, method="uniform")  # valeurs de 0 à 9
    if masque is not None:
        # ponytail: un pixel au bord de l'objet compare aussi ses voisins du fond ; éroder le masque si ça gêne
        motifs = motifs[masque]
    return np.bincount(motifs.astype(np.int64).ravel(), minlength=10) / motifs.size


def calculer(pixels, masque=None):
    """Renvoie le vecteur de 141 valeurs (float32) d'une image OpenCV (B, G, R sur 8 bits).

    masque : tableau booléen de la taille de l'image, vrai sur les pixels à compter (l'objet d'une
    image dont le fond a été supprimé). None : tous les pixels comptent, comme pour GHIM-10K.
    """
    gris = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY)
    if masque is not None and not masque.any():
        masque = None  # image entièrement transparente : on compte tout plutôt que rien
    # Histogrammes et moments n'ont pas besoin de voisins : on leur donne seulement les pixels de l'objet,
    # rangés sur une ligne. Couleurs dominantes et textures, elles, ont besoin de l'image et du masque.
    couleurs = pixels if masque is None else pixels[masque][None]
    vecteur = np.concatenate([histogrammes(couleurs), moments(couleurs), dominantes(pixels, masque),
                              glcm(gris, masque), lbp(gris, masque)])
    # Une valeur indéfinie (image d'un seul pixel, par exemple) est remplacée par 0.
    return np.nan_to_num(vecteur).astype(np.float32)


def detailler(vecteur):
    """Découpe un vecteur de 141 valeurs en dictionnaire lisible, pour la réponse de l'API."""
    v = [float(x) for x in vecteur]
    return {
        "histogrammes": {"r": v[0:32], "g": v[32:64], "b": v[64:96]},
        # Pour chaque canal : [moyenne, écart-type, asymétrie]
        "moments": {"h": v[96:99], "s": v[99:102], "v": v[102:105]},
        "dominantes": [
            {"r": v[i], "g": v[i + 1], "b": v[i + 2], "proportion": v[i + 3]} for i in range(105, 125, 4)
        ],
        "glcm": dict(zip(NOMS_GLCM, v[125:131])),
        "lbp": v[131:141],
    }
