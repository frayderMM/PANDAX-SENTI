"""Catálogo de fuentes oficiales (§11.1, §11.2).

Cada fuente lleva su estado real según el documento. Las marcadas
`verificada=False` **existen en el catálogo pero no se citan como confirmadas**:
el §11.1 las clasifica como "por verificar" y el §11.4 exige que una fuente
citada tenga institución, URL, fecha, hora de consulta, ámbito, vigencia y
tipo. Una ruta REST sin confirmar no cumple eso.

El §11.1 también fija dos límites que este catálogo respeta:

- No se hace scraping de endpoints internos no documentados de ninguna
  institución. Por eso SENAMHI, SUTRAN, SIGRID y DIHIDRONAV entran como
  ingesta documental y no como API.
- Para SUTRAN en producción se consume únicamente un feed autorizado por
  SUTRAN/MTC. El campo `requiere_autorizacion` lo marca.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain import HazardType, SourceKind


@dataclass(frozen=True)
class SourceDef:
    slug: str
    institucion: str
    descripcion: str
    url: str
    kind: SourceKind
    healthcheck_url: str | None = None
    verificada: bool = False
    vigencia_horas: int | None = None
    ambito_geografico: str = "Perú"
    tipo_informacion: str = ""
    requiere_autorizacion: bool = False


# §11.1, tabla de estado, literal.
CATALOGO: tuple[SourceDef, ...] = (
    # ── Confirmadas ────────────────────────────────────────────────────────
    SourceDef(
        slug="igp-censis-sismos",
        institucion="IGP / CENSIS",
        descripcion="Capa «Sismos Reportados». Campos fecha y hora. MaxRecordCount 2000.",
        url=(
            "https://ide.igp.gob.pe/arcgis/rest/services/monitoreocensis/"
            "Sismicidad/MapServer/0/query"
        ),
        healthcheck_url=(
            "https://ide.igp.gob.pe/arcgis/rest/services/monitoreocensis/"
            "Sismicidad/MapServer/0"
        ),
        kind=SourceKind.SERVICIO_GEOGRAFICO_OFICIAL,
        verificada=True,
        vigencia_horas=6,
        tipo_informacion="Sismicidad",
    ),
    SourceDef(
        slug="indeci-geosinpad",
        institucion="INDECI",
        descripcion="GeoSINPAD. OGC API oficial de emergencias registradas, con fecha y geometría.",
        url=(
            "https://geosinpad.indeci.gob.pe/indeci/rest/services/Emergencias/"
            "EMERGENCIAS_SINPAD/OGCFeatureServer/collections/0/items"
        ),
        healthcheck_url=(
            "https://geosinpad.indeci.gob.pe/indeci/rest/services/Emergencias/"
            "EMERGENCIAS_SINPAD/OGCFeatureServer"
        ),
        kind=SourceKind.API_OFICIAL,
        verificada=True,
        vigencia_horas=24,
        tipo_informacion="Emergencias registradas",
    ),
    SourceDef(
        slug="senamhi-wis-horario",
        institucion="SENAMHI",
        descripcion=(
            "WIS 2.0 OGC API de observaciones sinópticas horarias de estaciones "
            "terrestres: precipitación, temperatura, viento, presión y humedad. "
            "El catálogo de estaciones está disponible en "
            "http://wis.senamhi.gob.pe/oapi/collections/stations/items. "
            "El servicio oficial actualmente responde por HTTP; su HTTPS "
            "publica una cadena de certificados incompleta."
        ),
        url=(
            "http://wis.senamhi.gob.pe/oapi/collections/"
            "urn%3Awmo%3Amd%3Ape-senamhi%3Asynop-hourly/items"
        ),
        healthcheck_url="http://wis.senamhi.gob.pe/oapi/collections?f=json",
        kind=SourceKind.API_OFICIAL,
        verificada=True,
        vigencia_horas=6,
        tipo_informacion="Observaciones meteorológicas horarias",
    ),
)

POR_SLUG: dict[str, SourceDef] = {s.slug: s for s in CATALOGO}

# §11.2, selección por tema. Determina qué fuente se consulta para qué
# pregunta, sin dejárselo al criterio del modelo.
POR_TEMA: dict[HazardType, tuple[str, ...]] = {
    HazardType.SISMO: ("igp-censis-sismos",),
    HazardType.INUNDACION: ("indeci-geosinpad", "senamhi-wis-horario"),
    HazardType.LLUVIA: ("senamhi-wis-horario",),
}


def fuentes_para(tipo: HazardType) -> tuple[SourceDef, ...]:
    """Fuentes que corresponden a un tipo de peligro (§11.2).

    Devuelve solo las verificadas. Las fuentes por verificar no se consultan
    para crear eventos oficiales hasta que su endpoint esté confirmado.
    """
    slugs = POR_TEMA.get(tipo, ())
    return tuple(POR_SLUG[s] for s in slugs if POR_SLUG[s].verificada)
