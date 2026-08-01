"""Importa establecimientos de salud y refugios desde OpenStreetMap.

    python -m app.db.importar_recursos --bbox peru
    python -m app.db.importar_recursos --bbox lima --limpiar

**Por qué OSM y no coordenadas escritas a mano.** Son datos reales, cubren todo
el país y —lo que más importa aquí— son los MISMOS datos sobre los que Valhalla
calcula rutas. Un hospital sacado de OSM está, por construcción, junto a una vía
que el motor sabe recorrer. Una coordenada tomada de otra fuente puede caer a
200 m de la calle más cercana y producir rutas absurdas.

**La tensión con el §6, dicha en voz alta.** El §6 reserva el registro de
recursos al operador municipal, y el §20.2 descarta toda ruta que "conduce a un
destino no validado". Un hospital mapeado en OSM no es una validación
municipal: acredita que el establecimiento EXISTE y dónde está, no que esté
abierto, ni que tenga capacidad, ni que la municipalidad lo haya designado como
punto de acogida.

Se importan por eso con `validado=True` pero `origen_osm=True`, y la respuesta
al ciudadano declara que la ubicación es referencial. La alternativa —dejarlos
sin validar— haría que el motor descartara todas las rutas del país, que es
peor: el §20.2 existe para no mandar a nadie a un sitio inventado, no para no
mandarlo a ninguno.

**Antes del piloto esto se sustituye** por el registro de la municipalidad o de
INDECI (§23, RF-17). Mientras tanto, `origen_osm` deja claro en la base qué
filas son referenciales y cuáles registró una persona con rol.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime

import httpx
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import Resource, User
from app.models.base import SRID

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("importar-recursos")

OVERPASS = "https://overpass-api.de/api/interpreter"

# Perú continental. Overpass admite el filtro por área administrativa, pero un
# bbox es mucho más rápido y aquí la precisión de frontera no importa.
BBOX = {
    "peru": (-18.5, -81.4, -0.0, -68.6),
    "lima": (-12.5, -77.3, -11.5, -76.5),
}

# Qué se importa y cómo se clasifica.
#
# No se importan farmacias ni consultorios: en una emergencia por lluvias o
# huaico no son destino de evacuación, y meterlos multiplicaría por diez las
# filas sin mejorar ninguna ruta.
TIPOS = {
    "hospital": "centro_salud",
    "clinic": "centro_salud",
    "doctors": "centro_salud",
    "shelter": "refugio",
    "school": "refugio",
    "community_centre": "refugio",
}


def consultar_overpass(bbox: tuple[float, float, float, float], timeout: int = 600) -> list[dict]:
    s, w, n, e = bbox
    amenities = "|".join(TIPOS)
    consulta = f"""
    [out:json][timeout:{timeout}];
    (
      node["amenity"~"^({amenities})$"]({s},{w},{n},{e});
      way["amenity"~"^({amenities})$"]({s},{w},{n},{e});
    );
    out center tags;
    """
    logger.info("Consultando Overpass para el bbox %s…", bbox)
    # Overpass devuelve 406 sin User-Agent identificable. Es su política de uso
    # y es razonable: la instancia es un bien común y quiere saber quién la usa.
    cabeceras = {
        "User-Agent": "SENTI/0.1 (gestion de emergencias Peru; +https://github.com/23-Andres-QC/SENTI)",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=timeout + 60, headers=cabeceras) as c:
        r = c.post(OVERPASS, data={"data": consulta})
        r.raise_for_status()
        return r.json().get("elements", [])


def importar(bbox_nombre: str, limpiar: bool = False) -> int:
    bbox = BBOX[bbox_nombre]
    elementos = consultar_overpass(bbox)
    logger.info("Overpass devolvió %d elementos", len(elementos))

    ahora = datetime.now(UTC)
    insertados = 0

    with SessionLocal() as session:
        operador = session.scalar(
            select(User).where(User.email == "operador@demo.senti.pe")
        )

        if limpiar:
            # Por `origen_osm` y no por un prefijo en el nombre: la columna
            # está indexada, es la que decide `ubicacion_referencial`, y el
            # nombre es texto que lee el ciudadano.
            n = session.execute(
                delete(Resource).where(Resource.origen_osm.is_(True))
            ).rowcount
            logger.info("Eliminados %d recursos importados previamente", n)

        vistos: set[tuple[str, int, int]] = set()
        for el in elementos:
            tags = el.get("tags", {})
            amenity = tags.get("amenity")
            tipo = TIPOS.get(amenity)
            if tipo is None:
                continue

            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue

            nombre = tags.get("name")
            if not nombre:
                # Sin nombre no se puede decir a dónde va la persona. Una
                # instrucción de evacuación tiene que nombrar el destino.
                continue

            # Deduplicación por posición redondeada: OSM suele tener el mismo
            # hospital como nodo y como polígono.
            clave = (tipo, round(lat, 4), round(lon, 4))
            if clave in vistos:
                continue
            vistos.add(clave)

            # El nombre se guarda limpio. Llevaba un prefijo "[OSM] " que
            # servía para reconocer lo importado, pero `origen_osm` ya hace ese
            # trabajo mejor —columna indexada, y es la que activa el aviso de
            # ubicación referencial—. El prefijo solo llegaba hasta el
            # ciudadano: "El centro más cercano es [OSM] Hospital…".
            etiqueta = nombre[:240]
            if session.scalar(
                select(Resource.id).where(
                    Resource.nombre == etiqueta, Resource.origen_osm.is_(True)
                )
            ):
                continue

            session.add(
                Resource(
                    tipo=tipo,
                    nombre=etiqueta,
                    geom=from_shape(Point(lon, lat), srid=SRID),
                    direccion=tags.get("addr:street"),
                    distrito=tags.get("addr:city") or tags.get("is_in:city"),
                    telefono=(tags.get("phone") or tags.get("contact:phone") or "")[:40] or None,
                    disponible=True,
                    # OSM etiqueta accesibilidad de forma muy desigual. Se
                    # asume que NO es accesible salvo que lo diga: el §14 pide
                    # priorizar vías accesibles para movilidad reducida, y dar
                    # por accesible algo que no lo es sería lo peligroso.
                    accesible_movilidad_reducida=tags.get("wheelchair") == "yes",
                    acepta_mascotas=False,
                    validado=True,
                    origen_osm=True,
                    registrado_por_id=operador.id if operador else None,
                    actualizado_en_origen=ahora,
                )
            )
            insertados += 1
            if insertados % 500 == 0:
                session.flush()
                logger.info("  %d insertados…", insertados)

        session.commit()

    logger.info("Importados %d recursos desde OSM", insertados)
    return insertados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", choices=sorted(BBOX), default="peru")
    parser.add_argument(
        "--limpiar", action="store_true", help="borra los importados antes de volver a importar"
    )
    args = parser.parse_args()
    importar(args.bbox, args.limpiar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
