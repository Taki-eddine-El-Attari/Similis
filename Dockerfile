# syntax=docker/dockerfile:1
# Image de Similis pour Render (service web Docker, offre gratuite).
# Le code vient du dépôt ; GHIM-10K et son index viennent d'un dépôt de données privé sur Hugging Face,
# téléchargé pendant la construction avec le fichier secret HF_TOKEN du service Render.

# 1. Frontend compilé
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. Backend
FROM python:3.13-slim
# libgl1 et libglib2.0-0 : bibliothèques système demandées par opencv-python.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /app
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt gunicorn==23.0.0

# Archive : data/GHIM-10K/, storage/index/ghim.npz, storage/evaluation.csv.
# Placée avant la copie du code : une modification du code ne relance pas le téléchargement.
ARG DONNEES=https://huggingface.co/datasets/said30/similis-data/resolve/main/similis-donnees.tar
RUN --mount=type=secret,id=HF_TOKEN,mode=0444,required=true \
    curl -fsSL -H "Authorization: Bearer $(cat /run/secrets/HF_TOKEN)" "$DONNEES" | tar -x -C /app \
    && chown -R user /app/storage

COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist

USER user
WORKDIR /app/backend
# Sans --bind, gunicorn écoute sur 0.0.0.0:$PORT ; Render fournit PORT (10000 par défaut).
ENV PORT=10000
EXPOSE 10000
# Un seul processus : la clé de session et l'index en mémoire restent communs à toutes les requêtes.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "120", "app:creer_app()"]
