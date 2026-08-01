#!/usr/bin/env bash
#
# Genera los packs de teselas del modo sin conexión (§26).
#
# No se versionan: `.gitignore` excluye `*.pmtiles` porque son datos generados
# y multiplicarían por diecisiete el tamaño del repositorio. Este script es lo
# que los reconstruye, y por eso el APK se puede ensamblar desde un clon limpio
# ejecutándolo antes.
#
#   ./scripts/generar-teselas.sh
#
# Se extraen por `range requests` contra el planeta público de Protomaps: NO se
# descarga el planeta entero, solo los bytes de los recuadros pedidos. Son unos
# 64 MB de descarga y tarda pocos minutos.
#
# Sin el pack nacional la app compila igual y arranca igual: la pantalla sin
# conexión declara que el mapa base no está disponible en esa instalación y las
# guías y los teléfonos siguen funcionando. Es una degradación honesta, no un
# build roto.
set -euo pipefail

cd "$(dirname "$0")/.."
ASSETS="senti-android/app/src/main/assets"
IMAGEN="protomaps/go-pmtiles:latest"

# Construcción del planeta. Protomaps publica una diaria y conserva las
# recientes; si esta caducó, cámbiala por otra fecha de build.protomaps.com.
PLANETA="${SENTI_PLANETA_PMTILES:-https://build.protomaps.com/20260728.pmtiles}"

# Perú continental hasta zoom 11 y área metropolitana de Lima y Callao hasta
# zoom 15. El reparto está medido y explicado en el README: subir un nivel de
# zoom en todo el país cuesta más megas que llevar Lima entera a nivel de calle.
PERU_BBOX="-81.4,-18.4,-68.6,-0.03"
PERU_ZOOM=11
LIMA_BBOX="-77.25,-12.45,-76.70,-11.70"
LIMA_ZOOM=15

if ! command -v docker >/dev/null 2>&1; then
  echo "Hace falta docker para ejecutar $IMAGEN." >&2
  echo "Alternativa: instalar go-pmtiles y sustituir las llamadas de abajo." >&2
  exit 1
fi

mkdir -p "$ASSETS"
docker pull --quiet "$IMAGEN"

extraer() {
  local salida="$1" bbox="$2" zoom="$3"
  echo "▸ $salida  (bbox $bbox, zoom 0-$zoom)"
  # El contenedor escribe como root; se corrige el propietario al terminar para
  # que Gradle pueda leer el asset sin sudo.
  docker run --rm -v "$PWD/$ASSETS:/data" "$IMAGEN" \
    extract "$PLANETA" "/data/$salida" --bbox="$bbox" --maxzoom="$zoom"
  if [ "$(id -u)" -ne 0 ]; then
    sudo chown "$(id -u):$(id -g)" "$ASSETS/$salida" 2>/dev/null \
      || chmod 644 "$ASSETS/$salida" 2>/dev/null || true
  fi
  chmod 644 "$ASSETS/$salida"
}

extraer "peru.pmtiles" "$PERU_BBOX" "$PERU_ZOOM"
extraer "lima_callao.pmtiles" "$LIMA_BBOX" "$LIMA_ZOOM"

echo
echo "Packs generados en $ASSETS:"
ls -la "$ASSETS"/*.pmtiles | awk '{printf "  %-28s %.1f MB\n", $9, $5/1048576}'
