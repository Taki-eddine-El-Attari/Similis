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
    db.close()
    app.teardown_appcontext(fermer)
