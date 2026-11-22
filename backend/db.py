"""Accès à la base SQLite : une connexion par requête HTTP."""

import sqlite3

from flask import current_app, g

# COLLATE NOCASE : « Amine » et « amine » sont le même nom d'utilisateur.
SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    id            INTEGER PRIMARY KEY,
    nom           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    mot_de_passe  TEXT NOT NULL,
    cree_le       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- parent_id nul : catégorie racine. Les clés étrangères empêchent de supprimer
-- une catégorie qui contient encore des sous-catégories ou des images.
CREATE TABLE IF NOT EXISTS categories (
    id              INTEGER PRIMARY KEY,
    utilisateur_id  INTEGER NOT NULL REFERENCES utilisateurs(id),
    parent_id       INTEGER REFERENCES categories(id),
    nom             TEXT NOT NULL COLLATE NOCASE
);

-- Pas deux catégories de même nom sous le même parent.
-- IFNULL : pour SQLite deux NULL sont différents, les racines échapperaient à la règle.
CREATE UNIQUE INDEX IF NOT EXISTS categories_nom_unique
    ON categories (utilisateur_id, IFNULL(parent_id, 0), nom);

"""

# fichier : nom généré sur le disque (UUID + extension). nom : nom affiché.
# descripteurs : les 141 valeurs en float32, remplies à l'étape 5.
# AUTOINCREMENT : l'id d'une image supprimée n'est jamais redonné. Sans lui, SQLite reprend l'id
# de la dernière image supprimée, et le navigateur affiche l'ancien fichier gardé pour cette adresse.
IMAGES = """
CREATE TABLE IF NOT EXISTS images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id  INTEGER NOT NULL REFERENCES utilisateurs(id),
    categorie_id    INTEGER REFERENCES categories(id),
    nom             TEXT NOT NULL,
    fichier         TEXT NOT NULL,
    largeur         INTEGER NOT NULL,
    hauteur         INTEGER NOT NULL,
    descripteurs    BLOB,
    cree_le         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connexion():
    """Renvoie la connexion de la requête en cours (ouverte au premier appel)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["BASE"])
        g.db.row_factory = sqlite3.Row  # lignes lisibles par nom de colonne
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def fermer(erreur=None):
    """Ferme la connexion à la fin de la requête."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def initialiser(app):
    """Crée les tables si elles manquent et programme la fermeture automatique."""
    with sqlite3.connect(app.config["BASE"]) as db:
        db.executescript(SCHEMA)
        ancienne = db.execute("SELECT sql FROM sqlite_master WHERE name = 'images'").fetchone()
        if ancienne is None:
            db.executescript(IMAGES)
        elif "AUTOINCREMENT" not in ancienne[0]:
            # Base créée avant AUTOINCREMENT : on refait la table en gardant les lignes et leurs id.
            # Une seule transaction : en cas de panne, la base reste comme avant.
            db.executescript(
                "BEGIN; ALTER TABLE images RENAME TO images_ancienne;" + IMAGES
                + "INSERT INTO images SELECT * FROM images_ancienne; DROP TABLE images_ancienne; COMMIT;"
            )
    db.close()
    app.teardown_appcontext(fermer)
