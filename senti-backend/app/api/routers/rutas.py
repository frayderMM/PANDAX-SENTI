"""Rutas de menor riesgo (§20, RF-10, RF-11)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from pydantic import BaseModel, Field
from shapely.geometry import Point
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.api.deps import auditar, db, exige, usuario_actual
from app.core.security import Permission
from app.models import HouseholdProfile, Resource, User
from app.models.base import SRID
from app.routing.engine import RouteEngine
from app.routing.valhalla import ValhallaUnavailable, costing_para_perfil
from app.rules.fixed_responses import SIN_RUTA_VERIFICABLE
from app.rules.scoring import HouseholdFacts

router = APIRouter(prefix="/rutas", tags=["rutas"])


class PuntoEvitar(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RutaEntrada(BaseModel):
    origen_lat: float = Field(ge=-90, le=90)
    origen_lon: float = Field(ge=-180, le=180)
    destino_lat: float | None = Field(default=None, ge=-90, le=90)
    destino_lon: float | None = Field(default=None, ge=-180, le=180)
    destino_resource_id: str | None = None
    guardar: bool = True
    # Puntos que el usuario marcó en el mapa como intransitables. Valen para
    # esta petición y para nadie más: no cierran la vía (§6, §21.2).
    evitar: list[PuntoEvitar] = Field(default_factory=list, max_length=24)
    hacia_refugio: bool = False


@router.post("", dependencies=[Depends(exige(Permission.CONSULTAR_RUTAS))])
def calcular(
    datos: RutaEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """§20.1 completo. Devuelve ruta recomendada, alternativa y descartes.

    Cuando no hay ruta, devuelve la respuesta literal del §20.5 con estado 200:
    "sin ruta verificable" es un resultado correcto del sistema, no un error, y
    devolver un 4xx haría que un cliente lo tratara como fallo y reintentara.
    """
    ahora = datetime.now(UTC)
    perfil = session.scalar(select(HouseholdProfile).where(HouseholdProfile.user_id == user.id))
    hogar = (
        HouseholdFacts(
            movilidad_reducida=perfil.movilidad_reducida,
            adultos_mayores=perfil.adultos_mayores,
            ninos=perfil.ninos,
            vehiculo=perfil.vehiculo,
        )
        if perfil
        else HouseholdFacts()
    )
    costing, _ = costing_para_perfil(
        vehiculo=hogar.vehiculo,
        movilidad_reducida=hogar.movilidad_reducida,
        adultos_mayores=hogar.adultos_mayores,
    )

    destino_lat = datos.destino_lat
    destino_lon = datos.destino_lon
    destino_resource_id = datos.destino_resource_id
    if destino_lat is None or destino_lon is None:
        if not datos.hacia_refugio:
            raise HTTPException(status_code=422, detail="Falta el destino")
        origen = from_shape(Point(datos.origen_lon, datos.origen_lat), srid=SRID)
        recurso = session.scalar(
            select(Resource)
            .where(
                Resource.tipo == "refugio",
                Resource.validado.is_(True),
                Resource.disponible.is_(True),
                func.ST_DWithin(
                    cast(Resource.geom, Geography), cast(origen, Geography), 15000.0
                ),
            )
            .order_by(
                func.ST_Distance(cast(Resource.geom, Geography), cast(origen, Geography))
            )
            .limit(1)
        )
        if recurso is None:
            return {"sin_ruta_verificable": True, "mensaje": SIN_RUTA_VERIFICABLE}
        destino_lat = float(session.scalar(select(func.ST_Y(recurso.geom))))
        destino_lon = float(session.scalar(select(func.ST_X(recurso.geom))))
        destino_resource_id = recurso.id

    engine = RouteEngine(session)
    try:
        resultado = engine.calcular(
            (datos.origen_lat, datos.origen_lon),
            (destino_lat, destino_lon),
            hogar,
            ahora,
            distrito=perfil.distrito if perfil else None,
            destino_resource_id=destino_resource_id,
            evitar=[(p.lat, p.lon) for p in datos.evitar],
        )
    except ValhallaUnavailable as exc:
        return {
            "sin_ruta_verificable": True,
            "mensaje": SIN_RUTA_VERIFICABLE,
            "motivo": f"motor de rutas no disponible: {exc}",
        }

    auditar(session, request, actor=user, accion="ruta.calcular", entidad="route",
            detalle={"sin_ruta": resultado.sin_ruta_verificable,
                     "descartadas": len(resultado.ranking.descartadas)})

    if resultado.sin_ruta_verificable:
        return {
            "sin_ruta_verificable": True,
            # §20.5 sin excepciones: si al esquivar lo que marcó el usuario no
            # queda ninguna ruta verificable, se dice. No se devuelve "la menos
            # mala" ni se ignoran sus marcas para poder enseñar algo.
            "mensaje": SIN_RUTA_VERIFICABLE,
            "descartadas": [
                {"ruta": rid, "motivo": m} for rid, m in resultado.ranking.descartadas
            ],
            "fuentes": resultado.fuentes,
        }

    rec = resultado.ranking.recomendada
    assert rec is not None
    valhalla = resultado.rutas_valhalla[rec.ruta_id]

    guardada = None
    if datos.guardar:
        guardada = engine.guardar(
            resultado,
            user_id=user.id,
            origen=(datos.origen_lat, datos.origen_lon),
            destino=(destino_lat, destino_lon),
            costing=costing,
        )

    return {
        "sin_ruta_verificable": False,
        "route_id": str(guardada.id) if guardada else None,
        "distancia_m": round(valhalla.distancia_m),
        "duracion_s": round(valhalla.duracion_s),
        "costing": costing,
        # §20.5, el lenguaje obligatorio. Nunca "esta ruta es segura".
        "frase": resultado.cobertura.frase,
        "motivo": rec.motivo_riesgo_maximo,
        "nivel_confianza": guardada.nivel_confianza if guardada else None,
        "cobertura_suficiente": resultado.cobertura.suficiente,
        "puntaje": {
            "total": round(rec.puntaje, 3),
            "s_seguridad": round(rec.s_seguridad, 3),
            "s_fuente": round(rec.s_fuente, 3),
            "s_accesible": round(rec.s_accesible, 3),
            "s_duracion": round(rec.s_duracion, 3),
            "s_distancia": round(rec.s_distancia, 3),
        },
        "pasos": [
            {"instruccion": m.instruccion, "distancia_m": round(m.distancia_m)}
            for m in valhalla.maniobras
        ],
        "geometria": valhalla.shape,
        # Lo que el mapa del cliente necesita para redibujarse sin volver a
        # preguntar por ello.
        "origen_lat": datos.origen_lat,
        "origen_lon": datos.origen_lon,
        "destino_lat": destino_lat,
        "destino_lon": destino_lon,
        "bloqueos": resultado.bloqueos_dibujables,
        "evitados": len(datos.evitar),
        "alternativa": (
            {
                "puntaje": round(resultado.ranking.alternativa.puntaje, 3),
                "motivo": resultado.ranking.alternativa.motivo_riesgo_maximo,
            }
            if resultado.ranking.alternativa
            else None
        ),
        "descartadas": [{"ruta": rid, "motivo": m} for rid, m in resultado.ranking.descartadas],
        "fuentes": resultado.fuentes,
        "actualizado_at": ahora.isoformat(),
    }
