-- Extensiones requeridas por §9 y §27.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Configuración de búsqueda de texto en español para el índice propio
-- del §10.2 (PostgreSQL Full Text Search + pgvector).
-- CREATE TEXT SEARCH CONFIGURATION no admite IF NOT EXISTS.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'senti_es'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION senti_es (COPY = spanish);
    END IF;
END
$$;
