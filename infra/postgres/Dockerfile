# PostGIS y pgvector en la misma instancia (§9): el RAG vive junto a los
# datos geográficos, que es justamente la razón por la que el §9 descarta
# FAISS y Chroma.
FROM postgis/postgis:17-3.5

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-17-pgvector \
 && rm -rf /var/lib/apt/lists/*
