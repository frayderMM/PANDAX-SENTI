#!/usr/bin/env bash
#
# Descarga los GGUF que SENTI necesita.
#
# Docker NO los descarga: a diferencia de Ollama, el servidor de llama.cpp solo
# lee un archivo que ya tiene que existir. Sin esto, el contenedor arranca y
# muere con "failed to load model".
#
# Uso:
#   ./scripts/descargar-modelos.sh            # Gemma 3 4B, para CPU (spec §9)
#   ./scripts/descargar-modelos.sh 4b-gpu     # Gemma 4 E4B, si hay GPU
#
set -euo pipefail

DESTINO="${LLM_MODELS_DIR:-./modelos}"
VARIANTE="${1:-cpu}"

mkdir -p "$DESTINO"

# `--continue-at -` es lo que salva una conexión que se corta: reanuda donde
# iba en vez de empezar de cero. Con 2,5 GB por archivo, la diferencia entre
# terminar y no terminar.
bajar() {
  local url="$1" nombre="$2" ruta="$DESTINO/$2"
  if [ -f "$ruta" ]; then
    echo "  ya existe: $nombre"
    return
  fi
  echo "  bajando: $nombre"
  curl -L --fail --continue-at - --retry 10 --retry-all-errors --retry-delay 5 \
       --progress-bar -o "$ruta" "$url"
}

HF="https://huggingface.co"

case "$VARIANTE" in
  cpu)
    echo "Gemma 3 4B (Q4_K_M) — servidores sin GPU"
    REPO="$HF/ggml-org/gemma-3-4b-it-GGUF/resolve/main"
    bajar "$REPO/gemma-3-4b-it-Q4_K_M.gguf" "gemma-3-4b-it-Q4_K_M.gguf"
    # Proyector de visión. Sin él el modelo IGNORA las imágenes en silencio, y
    # el §15 necesita interpretar alertas en imagen.
    bajar "$REPO/mmproj-model-f16.gguf" "mmproj-gemma-3-4b-f16.gguf"
    ;;
  4b-gpu)
    echo "Gemma 4 E4B (Q4_K_M) — requiere GPU"
    REPO="$HF/lmstudio-community/gemma-4-E4B-it-GGUF/resolve/main"
    bajar "$REPO/gemma-4-E4B-it-Q4_K_M.gguf" "gemma-4-E4B-it-Q4_K_M.gguf"
    bajar "$REPO/mmproj-gemma-4-E4B-it-BF16.gguf" "mmproj-gemma-4-E4B-it-BF16.gguf"
    ;;
  *)
    echo "Variante desconocida: $VARIANTE (usa 'cpu' o '4b-gpu')" >&2
    exit 1
    ;;
esac

# Embeddings del RAG (§19). Gemma es un modelo causal y no produce vectores,
# así que este es imprescindible y no opcional. Son 84 MB.
echo "Embeddings — nomic-embed-text-v1.5"
bajar "$HF/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q4_K_M.gguf" \
      "nomic-embed-text-v1.5.Q4_K_M.gguf"

echo
echo "Listo. Contenido de $DESTINO:"
ls -lh "$DESTINO" | grep -v '^total' | awk '{printf "  %6s  %s\n", $5, $9}'
