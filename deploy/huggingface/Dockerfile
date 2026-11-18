# Image de Similis pour un Space Hugging Face (SDK docker).
# Le code vient du dépôt GitHub public ; GHIM-10K et son index viennent d'un dépôt de données privé,
# téléchargé pendant la construction avec le secret HF_TOKEN du Space.

# 1. Code et frontend compilé
FROM node:22-slim AS code
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG DEPOT=https://github.com/Taki-eddine-El-Attari/Similis.git
RUN git clone --depth 1 "$DEPOT" /app
WORKDIR /app/frontend
RUN npm ci && npm run build

# 2. Backend
FROM python:3.13-slim
# libgl1 et libglib2.0-0 : bibliothèques système demandées par opencv-python.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*
# Hugging Face lance le conteneur avec l'utilisateur 1000.
RUN useradd -m -u 1000 user
COPY --from=code /app/backend /app/backend
COPY --from=code /app/frontend/dist /app/frontend/dist
RUN pip install --no-cache-dir -r /app/backend/requirements.txt gunicorn==23.0.0

# Archive : data/GHIM-10K/, storage/index/ghim.npz, storage/evaluation.csv
ARG DONNEES=https://huggingface.co/datasets/said30/similis-data/resolve/main/similis-donnees.tar
RUN --mount=type=secret,id=HF_TOKEN,mode=0444,required=true \
    curl -fsSL -H "Authorization: Bearer $(cat /run/secrets/HF_TOKEN)" "$DONNEES" | tar -x -C /app \
    && chown -R user /app/storage

USER user
WORKDIR /app/backend
EXPOSE 7860
# Un seul processus : la clé de session et l'index en mémoire restent communs à toutes les requêtes.
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "1", "--threads", "8", "--timeout", "120", "app:creer_app()"]
