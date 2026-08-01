"""Creación del esquema y datos de arranque.

Uso:
    python -m app.db.bootstrap            # extensiones + tablas
    python -m app.db.bootstrap --seed     # + catálogo, protocolos, teléfonos
    python -m app.db.bootstrap --demo     # + escenario Rosa del §34

`--demo` carga datos ficticios de Lurigancho-Chosica para la demostración del
§34. No se ejecuta si `SENTI_ENV` es producción: una alerta de mentira en un
sistema de emergencias es exactamente el tipo de cosa que el §12 combate.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models import Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("bootstrap")

EXTENSIONES = ("postgis", "vector", "pg_trgm")


def crear_extensiones() -> None:
    with engine.begin() as conn:
        for ext in EXTENSIONES:
            conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}"'))
    logger.info("Extensiones listas: %s", ", ".join(EXTENSIONES))


# Columnas añadidas después de que la base ya existiera. `create_all` crea
# tablas nuevas pero **no altera** las que ya están, así que sin esto un
# despliegue con datos se queda con el modelo viejo y revienta al primer uso.
# Son idempotentes: se pueden ejecutar en cada arranque sin efecto.
MIGRACIONES = (
    # §13.4: consentimiento de quien escribe por WhatsApp y no tiene cuenta.
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS consentimiento_at "
    "TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS consentimiento_version VARCHAR(32)",
    # La ubicación y la pregunta llegan en mensajes distintos por WhatsApp.
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS ultima_lat DOUBLE PRECISION",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS ultima_lon DOUBLE PRECISION",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS ubicacion_at TIMESTAMP WITH TIME ZONE",
    "CREATE INDEX IF NOT EXISTS ix_conversations_ubicacion_at ON conversations (ubicacion_at)",
    # §18: el nivel NEGRO. `create_all` no toca un tipo enum que ya existe, así
    # que sin esto la primera pregunta fuera de alcance revienta al guardar el
    # mensaje. NARANJA se deja en el tipo: hay filas antiguas que lo usan y
    # borrar un valor de un enum en uso obliga a reescribir la tabla entera.
    "ALTER TYPE urgency_level ADD VALUE IF NOT EXISTS 'NEGRO'",
    # El prefijo "[OSM] " se guardaba en el nombre para reconocer lo importado.
    # `origen_osm` ya lo hace, y el nombre lo lee el ciudadano: llegó a salir en
    # WhatsApp como "El centro más cercano es [OSM] Hospital Nacional…".
    "UPDATE resources SET nombre = substr(nombre, 7) WHERE nombre LIKE '[OSM] %'",
    "ALTER TABLE citizen_reports ADD COLUMN IF NOT EXISTS reporter_key_hash VARCHAR(128)",
    "CREATE INDEX IF NOT EXISTS ix_citizen_reports_reporter_key_hash ON citizen_reports (reporter_key_hash)",
    "ALTER TABLE event_sources ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(128)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_event_sources_fingerprint ON event_sources (fingerprint) WHERE fingerprint IS NOT NULL",
    # GeoSINPAD pasó de catálogo pendiente a OGC API oficial verificada.
    "UPDATE official_sources SET institucion = 'INDECI', "
    "descripcion = 'GeoSINPAD. OGC API oficial de emergencias registradas, con fecha y geometría.', "
    "url = 'https://geosinpad.indeci.gob.pe/indeci/rest/services/Emergencias/EMERGENCIAS_SINPAD/OGCFeatureServer/collections/0/items', "
    "healthcheck_url = 'https://geosinpad.indeci.gob.pe/indeci/rest/services/Emergencias/EMERGENCIAS_SINPAD/OGCFeatureServer', "
    "kind = 'API_OFICIAL', verificada = TRUE, vigencia_horas = 24 "
    "WHERE slug = 'indeci-geosinpad'",
    "UPDATE official_sources SET healthcheck_url = url "
    "WHERE slug IN ('senamhi-avisos', 'sutran-alertas', 'sigrid-cenepred', 'dihidronav-cnat')",
    "UPDATE official_sources SET url = 'https://coen.indeci.gob.pe/', "
    "healthcheck_url = 'https://coen.indeci.gob.pe/' WHERE slug = 'coen-indeci'",
    "UPDATE official_sources SET institucion = 'SENAMHI', "
    "descripcion = 'WIS 2.0 OGC API de observaciones sinópticas horarias; "
    "el servicio oficial responde por HTTP porque su HTTPS publica una cadena "
    "de certificados incompleta.', "
    "url = 'http://wis.senamhi.gob.pe/oapi/collections/"
    "urn%3Awmo%3Amd%3Ape-senamhi%3Asynop-hourly/items', "
    "healthcheck_url = 'http://wis.senamhi.gob.pe/oapi/collections?f=json', "
    "kind = 'API_OFICIAL', verificada = TRUE, activa = TRUE, vigencia_horas = 6 "
    "WHERE slug = 'senamhi-wis-horario'",
    "UPDATE official_sources SET activa = FALSE WHERE slug IN "
    "('ana-geosnirh', 'igp-ultimo-sismo', 'ingemmet-geocatmin', 'senamhi-avisos', "
    "'sutran-alertas', 'sigrid-cenepred', 'dihidronav-cnat', 'coen-indeci')",
    # §13.4: nueva finalidad de consentimiento para alertas por WhatsApp.
    # SQLAlchemy guarda el `.name` del enum de Python en el tipo de Postgres,
    # no el `.value` (así quedó creado `consent_purpose` desde el principio;
    # ver `ALTER TYPE urgency_level` arriba para el mismo caso con NEGRO).
    "ALTER TYPE consent_purpose ADD VALUE IF NOT EXISTS 'ALERTAS_WHATSAPP'",
)


def crear_tablas() -> None:
    Base.metadata.create_all(engine)
    logger.info("Tablas creadas: %d", len(Base.metadata.tables))
    with engine.begin() as conn:
        for sentencia in MIGRACIONES:
            conn.execute(text(sentencia))
    logger.info("Migraciones idempotentes aplicadas: %d", len(MIGRACIONES))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap de la base de datos de SENTI")
    parser.add_argument("--seed", action="store_true", help="carga el catálogo base")
    parser.add_argument("--demo", action="store_true", help="carga el escenario del §34")
    args = parser.parse_args()

    crear_extensiones()
    crear_tablas()

    if args.seed or args.demo:
        from app.db.seeds import sembrar_base

        with SessionLocal() as session:
            sembrar_base(session)
            session.commit()
        logger.info("Catálogo base sembrado")

    if args.demo:
        if settings.is_production:
            logger.error(
                "SENTI_ENV=%s: los datos de demostración no se cargan en producción. "
                "Una alerta ficticia en un sistema de emergencias es indefendible (§12).",
                settings.env,
            )
            return 1
        from app.db.seeds import sembrar_demo

        with SessionLocal() as session:
            sembrar_demo(session)
            session.commit()
        logger.info("Escenario del §34 cargado (Lurigancho-Chosica)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
