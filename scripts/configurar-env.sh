#!/usr/bin/env bash
#
# Genera un .env con secretos nuevos.
#
# Solo necesita openssl: no depende de que el servidor tenga instalado el
# paquete `cryptography` de Python, que en una Debian recién creada no está.
# La clave Fernet es 32 bytes aleatorios en base64 URL-SAFE; el `tr` que
# convierte +/ en -_ no es cosmético, sin él Fernet rechaza la clave.
#
# Uso:
#   ./scripts/configurar-env.sh          # servidor sin GPU (perfil llm-cpu)
#   ./scripts/configurar-env.sh gpu      # equipo con GPU (perfil llm-cuda)
#   ./scripts/configurar-env.sh lmstudio 192.168.1.11   # LM Studio en la red
#
set -euo pipefail

MODO="${1:-cpu}"
HOST_LM="${2:-}"

cd "$(dirname "$0")/.."

if [ -f .env ]; then
    echo "Ya existe un .env. No lo sobrescribo: contendría secretos en uso." >&2
    echo "Si quieres regenerarlo: mv .env .env.bak && $0 $MODO" >&2
    exit 1
fi

cp .env.example .env

poner() { sed -i "s|^$1=.*|$1=$2|" .env; }

PG=$(openssl rand -hex 12)
poner SENTI_SECRET_KEY        "$(openssl rand -hex 32)"
poner SENTI_PHONE_HASH_SALT   "$(openssl rand -hex 16)"
poner POSTGRES_PASSWORD       "$PG"
# La contraseña vive en DOS sitios: la variable de Postgres y la URL de
# conexión de la API. Cambiar solo una deja la base arrancada con una
# contraseña y la API intentando entrar con otra.
poner SENTI_DATABASE_URL      "postgresql+psycopg://senti:$PG@db:5432/senti"
poner SENTI_FIELD_ENCRYPTION_KEY "$(openssl rand -base64 32 | tr '+/' '-_')"

case "$MODO" in
  cpu)
    # Un solo servidor del modelo: `llama-cpu` atiende chat, imágenes y
    # análisis. El servicio `llama-chat-cpu` que se nombraba aquí ya no existe,
    # así que este script dejaba un .env que apuntaba a la nada.
    poner SENTI_LLM_BASE_URL        "http://llama-cpu:1234/v1"
    poner SENTI_LLM_DEEP_BASE_URL   "http://llama-cpu:1234/v1"
    poner SENTI_EMBEDDING_BASE_URL  "http://llama-embed-cpu:1235/v1"
    # Gemma 4, no Gemma 3: la plantilla de Gemma 3 no declara herramientas y
    # llama.cpp rechaza la petición entera con "Unable to generate parser".
    poner SENTI_LLM_MODEL           "google/gemma-4-e4b"
    poner SENTI_LLM_DEEP_MODEL      "google/gemma-4-e4b"
    poner SENTI_LLM_CONTEXT_LENGTH  "8192"
    PERFIL="llm-cpu"
    ;;
  gpu)
    poner SENTI_LLM_BASE_URL        "http://llama-chat:1234/v1"
    poner SENTI_EMBEDDING_BASE_URL  "http://llama-embed:1235/v1"
    PERFIL="llm-cuda"
    ;;
  lmstudio)
    if [ -z "$HOST_LM" ]; then
        echo "Falta la IP de LM Studio: $0 lmstudio 192.168.1.11" >&2
        exit 1
    fi
    poner SENTI_LLM_BASE_URL       "http://$HOST_LM:1234/v1"
    poner SENTI_EMBEDDING_BASE_URL "http://$HOST_LM:1234/v1"
    PERFIL="(ninguno)"
    ;;
  *)
    echo "Modo desconocido: $MODO (usa cpu, gpu o lmstudio)" >&2
    exit 1
    ;;
esac

echo ".env generado para el modo '$MODO'."
echo
grep -E "^(SENTI_LLM_BASE_URL|SENTI_EMBEDDING_BASE_URL|SENTI_LLM_MODEL|SENTI_LLM_CONTEXT_LENGTH)=" .env \
  | sed 's/^/  /'
echo
echo "Secretos generados (no se muestran)."
echo
echo "Siguiente paso:"
if [ "$MODO" != "lmstudio" ]; then
    echo "  make modelos                                  # Docker NO baja los GGUF"
    echo "  docker compose --profile $PERFIL up -d"
else
    echo "  docker compose up -d"
fi
echo "  make db-demo"
