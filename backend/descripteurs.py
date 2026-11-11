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


def dominantes(pixels):
    """20 valeurs : 5 couleurs (R, G, B entre 0 et 1, proportion), de la plus présente à la moins présente."""
    # L'image est d'abord réduite (plus grand côté à 100 pixels) pour que k-means reste rapide.
    hauteur, largeur = pixels.shape[:2]
    rapport = 100 / max(hauteur, largeur)
    if rapport < 1:
        pixels = cv2.resize(pixels, (max(1, round(largeur * rapport)), max(1, round(hauteur * rapport))),
                            interpolation=cv2.INTER_AREA)
    points = pixels.reshape(-1, 3).astype(np.float32)
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


def glcm(gris):
    """6 valeurs : contraste, corrélation, énergie, homogénéité, dissimilarité, ASM.

    Matrice de cooccurrence sur 256 niveaux, distance 1, directions 0°, 45°, 90° et 135°,
    symétrique et normalisée ; chaque propriété est la moyenne des 4 directions.
    """
    angles = [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]
    matrice = graycomatrix(gris, distances=[1], angles=angles, levels=256, symmetric=True, normed=True)
    return np.array([graycoprops(matrice, propriete).mean() for propriete in PROPRIETES_GLCM])


def lbp(gris):
    """10 valeurs : histogramme des motifs LBP uniformes (8 voisins, rayon 1), divisé par le nombre de pixels."""
    motifs = local_binary_pattern(gris, P=8, R=1, method="uniform")  # valeurs de 0 à 9
    return np.bincount(motifs.astype(np.int64).ravel(), minlength=10) / motifs.size


def calculer(pixels):
    """Renvoie le vecteur de 141 valeurs (float32) d'une image OpenCV (B, G, R sur 8 bits)."""
    gris = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY)
    vecteur = np.concatenate([histogrammes(pixels), moments(pixels), dominantes(pixels), glcm(gris), lbp(gris)])
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


def demo():
    """Petite vérification : python backend/descripteurs.py"""
    rouge = np.zeros((40, 60, 3), np.uint8)
    rouge[:, :, 2] = 255  # image entièrement rouge
    d = detailler(calculer(rouge))
    assert len(calculer(rouge)) == TAILLE
    assert d["histogrammes"]["r"][31] == 1 and d["histogrammes"]["g"][0] == 1 and d["histogrammes"]["b"][0] == 1
    assert d["moments"]["s"] == [1, 0, 0] and d["moments"]["v"] == [1, 0, 0]  # saturation et valeur maximales, uniformes
    assert (d["dominantes"][0]["r"], d["dominantes"][0]["g"], d["dominantes"][0]["b"]) == (1, 0, 0)
    assert d["glcm"]["contraste"] == 0 and d["glcm"]["homogeneite"] == 1  # aucune variation de texture
    print("Descripteurs : la vérification passe.")


if __name__ == "__main__":
    demo()
