"""Images de la galerie : chargement, liste, déplacement, téléchargement, suppression."""

import io
import re
import uuid
import zipfile
from pathlib import Path

import cv2
import numpy as np
from flask import current_app, g, request, send_file
from flask_restful import Resource
from werkzeug.exceptions import RequestEntityTooLarge

import categories
from db import connexion

EXTENSIONS = {".jpg", ".jpeg", ".png"}
TAILLE_MAX = 10 * 1024 * 1024  # 10 Mo par fichier
COLONNES = "id, categorie_id, nom, largeur, hauteur, cree_le"


def dossier():
    """Dossier des fichiers de l'utilisateur connecté : data/uploads/<nom>_<id>/, par exemple « amine_3 ».

    Le nom rend le dossier reconnaissable. Il vient de l'utilisateur : tout caractère autre
    qu'une lettre, un chiffre, « _ » ou « - » est remplacé, pour qu'il ne puisse pas servir
    de chemin (« ../ »). L'id garantit que deux comptes n'ont jamais le même dossier.
    """
    nom = re.sub(r"[^\w-]", "_", g.utilisateur["nom"])
    return Path(current_app.config["UPLOADS"]) / f"{nom}_{g.utilisateur['id']}"


def trouver(id):
    """Renvoie l'image « id » si elle appartient à l'utilisateur connecté, sinon None."""
    return connexion().execute(
        f"SELECT {COLONNES}, fichier FROM images WHERE id = ? AND utilisateur_id = ?",
        (id, g.utilisateur["id"]),
    ).fetchone()


def publique(image):
    """Ce que l'API renvoie pour une image : tout sauf le nom du fichier sur le disque."""
    return {cle: image[cle] for cle in COLONNES.split(", ")}


def lire_ids():
    """Lit « ids » du corps JSON et renvoie les images de l'utilisateur qui y figurent."""
    ids = categories.corps_json().get("ids")
    if not isinstance(ids, list):
        return []
    # dict.fromkeys : retire les doublons en gardant l'ordre.
    uniques = dict.fromkeys(i for i in ids if categories.est_entier(i))
    return [image for image in map(trouver, uniques) if image]


def supprimer(image):
    """Supprime la ligne en base, puis le fichier."""
    connexion().execute("DELETE FROM images WHERE id = ?", (image["id"],))
    connexion().commit()
    (dossier() / image["fichier"]).unlink(missing_ok=True)


def enregistrer(fichier, categorie_id):
    """Vérifie un fichier envoyé et l'enregistre. Renvoie (image, raison du refus)."""
    nom = Path(fichier.filename or "").name[:100]
    extension = Path(nom).suffix.lower()
    if extension not in EXTENSIONS:
        return None, "Format non accepté (JPG ou PNG seulement)."
    contenu = fichier.read(TAILLE_MAX + 1)
    if len(contenu) > TAILLE_MAX:
        return None, "Fichier trop gros (10 Mo maximum)."
    # L'extension ne suffit pas : OpenCV doit réussir à décoder l'image.
    pixels = cv2.imdecode(np.frombuffer(contenu, np.uint8), cv2.IMREAD_COLOR) if contenu else None
    if pixels is None:
        return None, "Ce fichier n'est pas une image lisible."
    hauteur, largeur = pixels.shape[:2]
    # Nom généré : deux fichiers de même nom ne s'écrasent pas, et le nom reçu ne sert jamais de chemin.
    sur_disque = uuid.uuid4().hex + extension
    dossier().mkdir(parents=True, exist_ok=True)
    (dossier() / sur_disque).write_bytes(contenu)
    db = connexion()
    curseur = db.execute(
        "INSERT INTO images (utilisateur_id, categorie_id, nom, fichier, largeur, hauteur) VALUES (?, ?, ?, ?, ?, ?)",
        (g.utilisateur["id"], categorie_id, nom, sur_disque, largeur, hauteur),
    )
    db.commit()
    return publique(trouver(curseur.lastrowid)), None


class Images(Resource):
    def get(self):
        """GET /api/images?categorie_id= — images d'une catégorie (sans paramètre : sans catégorie)."""
        categorie_id = request.args.get("categorie_id", type=int)
        if "categorie_id" in request.args and categories.trouver(categorie_id) is None:
            return {"erreur": "Catégorie introuvable."}, 404
        # « IS ? » : fonctionne aussi quand categorie_id vaut NULL, contrairement à « = ? ».
        lignes = connexion().execute(
            f"SELECT {COLONNES} FROM images WHERE utilisateur_id = ? AND categorie_id IS ? ORDER BY id DESC",
            (g.utilisateur["id"], categorie_id),
        ).fetchall()
        return [dict(ligne) for ligne in lignes]

    def post(self):
        """POST /api/images — charge un ou plusieurs fichiers (formulaire : fichiers, categorie_id)."""
        try:
            fichiers = request.files.getlist("fichiers")
            categorie_id = request.form.get("categorie_id") or None
        except RequestEntityTooLarge:
            return {"erreur": "Envoi trop volumineux (200 Mo maximum au total)."}, 413
        if categorie_id is not None:
            categorie_id = int(categorie_id) if categorie_id.isdigit() else None
            if categories.trouver(categorie_id) is None:
                return {"erreur": "Catégorie introuvable."}, 404
        if not fichiers:
            return {"erreur": "Aucun fichier envoyé."}, 400
        creees, refusees = [], []
        for fichier in fichiers:
            image, raison = enregistrer(fichier, categorie_id)
            if image:
                creees.append(image)
            else:
                refusees.append({"nom": fichier.filename, "raison": raison})
        if not creees:
            detail = " ; ".join(f"{refus['nom']} : {refus['raison']}" for refus in refusees)
            return {"erreur": "Aucun fichier accepté. " + detail, "refusees": refusees}, 400
        return {"creees": creees, "refusees": refusees}, 201


class Image(Resource):
    def put(self, id):
        """PUT /api/images/<id> — déplace l'image (categorie_id nul : sans catégorie)."""
        if trouver(id) is None:
            return {"erreur": "Image introuvable."}, 404
        corps = categories.corps_json()
        if "categorie_id" not in corps:
            return {"erreur": "Le champ categorie_id est obligatoire."}, 400
        categorie_id = corps["categorie_id"]
        if categorie_id is not None and categories.trouver(categorie_id) is None:
            return {"erreur": "Catégorie introuvable."}, 404
        connexion().execute("UPDATE images SET categorie_id = ? WHERE id = ?", (categorie_id, id))
        connexion().commit()
        return publique(trouver(id))

    def delete(self, id):
        """DELETE /api/images/<id> — supprime la ligne et le fichier."""
        image = trouver(id)
        if image is None:
            return {"erreur": "Image introuvable."}, 404
        supprimer(image)
        return "", 204


class Fichier(Resource):
    def get(self, id):
        """GET /api/images/<id>/fichier?telecharger=1 — le fichier ; avec le paramètre, en pièce jointe."""
        image = trouver(id)
        if image is None:
            return {"erreur": "Image introuvable."}, 404
        return send_file(
            dossier() / image["fichier"],
            as_attachment="telecharger" in request.args,
            download_name=image["nom"],
        )


class Zip(Resource):
    def post(self):
        """POST /api/images/zip — renvoie les images demandées dans une archive ZIP."""
        choisies = lire_ids()
        if not choisies:
            return {"erreur": "Aucune image à télécharger."}, 400
        tampon = io.BytesIO()
        # ZIP_STORED : JPG et PNG sont déjà compressés, les recompresser ne gagne rien.
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as archive:
            noms = set()
            for image in choisies:
                nom = image["nom"]
                if nom in noms:  # deux images de même nom : on ajoute l'identifiant
                    nom = f"{Path(nom).stem}_{image['id']}{Path(nom).suffix}"
                noms.add(nom)
                archive.write(dossier() / image["fichier"], nom)
        tampon.seek(0)
        return send_file(tampon, mimetype="application/zip", as_attachment=True, download_name="similis.zip")


class Suppression(Resource):
    def post(self):
        """POST /api/images/suppression — supprime plusieurs images ; renvoie leur nombre."""
        choisies = lire_ids()
        for image in choisies:
            supprimer(image)
        return {"supprimees": len(choisies)}
