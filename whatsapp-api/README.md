# WhatsApp: Evolution API propia (§10.1)

El transporte de WhatsApp es **Evolution API sobre Baileys**, no la nube de
Meta: no hay plantillas aprobadas ni `phone_number_id`. La ventana de 24 h se
respeta igual, porque es una regla de WhatsApp y no del proveedor.

**Esta instancia es nuestra.** Antes se apuntaba a una de un tercero, y por ese
transporte pasan los mensajes de gente pidiendo ayuda y el teléfono en claro de
quien escribe. El §13.5 obliga a que el número no se guarde en claro en SENTI;
sostener eso mientras el transporte es de otro es sostenerlo a medias.

## Qué hay aquí

| Archivo | Qué es |
|---|---|
| `docker-compose.yml` | el servicio `evolution` y el paso que crea su base de datos |
| `README.md` | esto |

El servicio se declara aquí pero lo **incluye** el `docker-compose.yml` de la
raíz. No es un proyecto de Compose aparte a propósito: Evolution y el backend
se hablan en las dos direcciones —el backend envía por `http://evolution:8080`
y Evolution avisa por `http://api:8000`— y desde proyectos separados ese
tráfico tendría que salir al host para volver a entrar.

## Antes de levantarlo

En el `.env` de la raíz (nunca en git):

```bash
SENTI_WHATSAPP_ENABLED=true
SENTI_EVOLUTION_API_URL=http://evolution:8080
SENTI_EVOLUTION_INSTANCE=senti
SENTI_EVOLUTION_API_KEY=$(openssl rand -hex 32)
SENTI_WHATSAPP_WEBHOOK_TOKEN=$(openssl rand -hex 32)
```

Las dos llaves son distintas y no se pueden intercambiar:

| Llave | Protege |
|---|---|
| `SENTI_EVOLUTION_API_KEY` | que solo SENTI pueda **enviar** por tu número |
| `SENTI_WHATSAPP_WEBHOOK_TOKEN` | que solo Evolution pueda **hacer hablar** a SENTI |

Sin la primera, Evolution ni arranca: el paso previo aborta y lo deja parado.

## Levantar

```bash
docker compose --profile whatsapp up -d evolution
docker compose logs -f evolution
```

El puerto solo escucha en `127.0.0.1`. Publicarlo es entregar el WhatsApp de la
institución a quien encuentre la IP, así que para verlo desde tu equipo se hace
un túnel:

```bash
ssh -L 8081:127.0.0.1:8081 usuario@servidor
```

Y ya se abre `http://localhost:8081/manager` con la llave de API.

## Emparejar el número

**El webhook se configura al crear la instancia, no con el global de
Evolution.** El global no admite cabeceras propias y SENTI exige
`X-Senti-Token`; sin ese secreto, quien descubra la URL del webhook hace que
SENTI escriba a quien él diga.

```bash
curl -X POST http://127.0.0.1:8081/instance/create \
  -H "apikey: $SENTI_EVOLUTION_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "instanceName": "senti",
    "integration": "WHATSAPP-BAILEYS",
    "qrcode": true,
    "webhook": {
      "url": "http://api:8000/webhooks/whatsapp",
      "byEvents": false,
      "base64": false,
      "headers": { "X-Senti-Token": "'"$SENTI_WHATSAPP_WEBHOOK_TOKEN"'" },
      "events": ["MESSAGES_UPSERT"]
    }
  }'
```

Solo se suscribe `MESSAGES_UPSERT`. El resto de eventos —presencia, recibos de
lectura, actualizaciones de contacto— son ruido que el webhook descartaría de
todos modos, y cada uno es un mensaje más que atraviesa la cola.

La respuesta trae el QR en base64. También se ve en el panel, o con:

```bash
curl -s http://127.0.0.1:8081/instance/connect/senti \
  -H "apikey: $SENTI_EVOLUTION_API_KEY"
```

Se escanea desde **WhatsApp → Dispositivos vinculados**. Comprobar que quedó:

```bash
curl -s http://127.0.0.1:8081/instance/connectionState/senti \
  -H "apikey: $SENTI_EVOLUTION_API_KEY"
```

Debe decir `"state": "open"`. Eso es lo mismo que consulta el backend.

## Comprobar de punta a punta

```bash
# 1. El backend ve el canal habilitado
curl -fsS http://127.0.0.1:8000/health/detalle

# 2. Un mensaje real desde otro teléfono al número emparejado.
#    Debe aparecer en los logs del worker, no en los del webhook:
#    el webhook responde 200 y encola.
docker compose logs --tail=50 worker
```

El primer contacto recibe el aviso del §13.4 y **no se procesa nada más** hasta
que responda `ACEPTO`.

## Lo que Evolution NO guarda

Por defecto archiva cada mensaje, contacto y chat en claro en su base. Eso
contradice el §13.5 de raíz, así que está desactivado en el compose:
`DATABASE_SAVE_DATA_NEW_MESSAGE`, `..._CONTACTS`, `..._CHATS`, `..._LABELS`,
`..._HISTORIC` y `DATABASE_SAVE_MESSAGE_UPDATE` van todos en `false`.

Se conserva **solo la instancia** (`DATABASE_SAVE_DATA_INSTANCE=true`), que es
la sesión emparejada con el teléfono. Sin ella habría que reescanear el QR en
cada reinicio, y un canal de emergencia que se cae al reiniciar no sirve.

Su base es `evolution`, separada de la de SENTI en el mismo Postgres: una
migración de Evolution no puede tocar las tablas del §27.

## Si algo va mal

| Síntoma | Causa habitual |
|---|---|
| `evolution` no arranca y el log dice `FALTA SENTI_EVOLUTION_API_KEY` | la llave no está en el `.env` |
| El QR caduca una y otra vez | `QRCODE_LIMIT` llegó al tope; borra la instancia y créala de nuevo |
| SENTI no responde a los mensajes | mira el `X-Senti-Token`: si no coincide, el webhook devuelve 401 y Evolution reintenta en vano |
| El webhook devuelve 503 | `SENTI_WHATSAPP_ENABLED` está en `false` |
| Los mensajes llegan por triplicado | se está contestando dentro del webhook en vez de encolar; no debería pasar, el webhook responde 200 y encola |

## Apagarlo

```bash
docker compose --profile whatsapp stop evolution
```

Con `SENTI_WHATSAPP_ENABLED=false` el webhook devuelve 503 a propósito: un
canal de emergencia a medio configurar que traga mensajes en silencio es peor
que uno que declara que no está.
