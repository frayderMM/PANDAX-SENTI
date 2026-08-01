#!/usr/bin/env bash
#
# Trae un QR fresco para vincular el número de WhatsApp (§10.1).
#
#   ./scripts/qr-whatsapp.sh            # QR nuevo, abre la imagen
#   ./scripts/qr-whatsapp.sh --estado   # solo dice cómo está la instancia
#   ./scripts/qr-whatsapp.sh --recrear  # borra la instancia y la crea de cero
#
# **Existe por una razón concreta: el QR de WhatsApp caduca en unos 40
# segundos.** Pedirlo, guardarlo y abrirlo a mano no cabe en ese tiempo, así
# que el escaneo falla con "no se puede vincular el dispositivo" aunque todo
# esté bien configurado. Este script hace el viaje entero de una vez y deja la
# imagen abierta; si caduca, se vuelve a ejecutar y ya.
#
# Con `--recrear` se borra y se rehace la instancia. Hace falta cuando se
# agotaron los intentos de `QRCODE_LIMIT`: pasado ese tope Evolution deja de
# emitir códigos y la instancia se queda en `connecting` para siempre, sin dar
# ningún error que lo explique.
set -euo pipefail

SERVIDOR="${SENTI_SSH:-andresoquilichec@35.253.231.219}"
REPO="${SENTI_REPO_REMOTO:-~/PANDAX-SENTI}"
INSTANCIA="${SENTI_EVOLUTION_INSTANCE:-senti}"
SALIDA="${SENTI_QR_SALIDA:-$HOME/senti-whatsapp-qr.png}"

# La llave y el token NUNCA viajan a este equipo: se leen del .env del
# servidor dentro de la propia sesión SSH y se usan allí.
remoto() { ssh -o ConnectTimeout=20 "$SERVIDOR" "cd $REPO && $1"; }

estado() {
  remoto 'LLAVE=$(grep "^SENTI_EVOLUTION_API_KEY=" .env | cut -d= -f2);
    curl -s http://127.0.0.1:8081/instance/connectionState/'"$INSTANCIA"' -H "apikey: $LLAVE"'
}

case "${1:-}" in
  --estado)
    estado; echo; exit 0
    ;;
  --recrear)
    echo "▸ borrando la instancia $INSTANCIA…"
    remoto 'LLAVE=$(grep "^SENTI_EVOLUTION_API_KEY=" .env | cut -d= -f2);
      curl -s -X DELETE http://127.0.0.1:8081/instance/delete/'"$INSTANCIA"' -H "apikey: $LLAVE" >/dev/null;
      curl -s -X POST http://127.0.0.1:8081/instance/logout/'"$INSTANCIA"' -H "apikey: $LLAVE" >/dev/null 2>&1 || true'
    sleep 2
    echo "▸ creándola con su webhook…"
    # El webhook se pone AQUÍ y no con el global de Evolution: el global no
    # admite cabeceras propias y SENTI exige X-Senti-Token. Sin ese secreto,
    # quien descubra la URL hace que SENTI escriba a quien él diga.
    remoto 'LLAVE=$(grep "^SENTI_EVOLUTION_API_KEY=" .env | cut -d= -f2);
      TOKEN=$(grep "^SENTI_WHATSAPP_WEBHOOK_TOKEN=" .env | cut -d= -f2);
      curl -s -X POST http://127.0.0.1:8081/instance/create -H "apikey: $LLAVE" \
        -H "Content-Type: application/json" \
        -d "{\"instanceName\":\"'"$INSTANCIA"'\",\"integration\":\"WHATSAPP-BAILEYS\",\"qrcode\":true,\"webhook\":{\"url\":\"http://api:8000/webhooks/whatsapp\",\"byEvents\":false,\"base64\":false,\"headers\":{\"X-Senti-Token\":\"$TOKEN\"},\"events\":[\"MESSAGES_UPSERT\"]}}" >/dev/null'
    sleep 3
    ;;
esac

echo "▸ estado actual: $(estado)"

echo "▸ pidiendo QR…"
remoto 'LLAVE=$(grep "^SENTI_EVOLUTION_API_KEY=" .env | cut -d= -f2);
  curl -s http://127.0.0.1:8081/instance/connect/'"$INSTANCIA"' -H "apikey: $LLAVE"' \
  | python3 -c "
import sys, json, base64, pathlib
crudo = sys.stdin.read()
try:
    d = json.loads(crudo)
except Exception:
    print('Evolution no devolvió JSON:', crudo[:200]); raise SystemExit(1)

if d.get('instance', {}).get('state') == 'open':
    print('Ya está vinculado: no hace falta QR.'); raise SystemExit(0)

b64 = (d.get('base64') or '').split(',')[-1]
if not b64:
    print('Sin QR. Se agotaron los intentos: vuelve a lanzarlo con --recrear.')
    raise SystemExit(1)

pathlib.Path('$SALIDA').write_bytes(base64.b64decode(b64))
print('QR escrito en $SALIDA')
"

echo
echo "▸ ESCANÉALO YA: caduca en unos 40 segundos."
echo "  WhatsApp → Ajustes → Dispositivos vinculados → Vincular dispositivo"
echo "  Si caduca, vuelve a ejecutar este script."
command -v xdg-open >/dev/null && xdg-open "$SALIDA" >/dev/null 2>&1 &
