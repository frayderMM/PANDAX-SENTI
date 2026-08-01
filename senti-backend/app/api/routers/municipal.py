"""Panel municipal (§22, RF-15, RF-16)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from geoalchemy2.shape import from_shape
from pydantic import BaseModel, Field
from shapely.geometry import Point, Polygon
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.api.deps import auditar, db, exige, usuario_actual
from app.core.security import Permission
from app.domain import ConfidenceLevel, HazardType, ReportState, SourceStatus, TrustLevel
from app.models import (
    Alert,
    CitizenReport,
    MunicipalNotice,
    OfficialSource,
    Resource,
    RoadBlock,
    User,
)
from app.models.base import SRID

router = APIRouter(prefix="/municipal", tags=["municipal"])


class CierreEntrada(BaseModel):
    nombre_via: str = Field(max_length=240)
    motivo: HazardType
    descripcion: str | None = Field(default=None, max_length=1000)
    # Punto para exclude_locations o polígono pequeño para exclude_polygons (§20.1).
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    poligono: list[list[float]] | None = None


class RecursoEntrada(BaseModel):
    tipo: str = Field(max_length=64)
    nombre: str = Field(max_length=240)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    direccion: str | None = Field(default=None, max_length=300)
    distrito: str | None = Field(default=None, max_length=120)
    telefono: str | None = Field(default=None, max_length=40)
    capacidad: int | None = None
    acepta_mascotas: bool = False
    accesible_movilidad_reducida: bool = False
    disponible: bool = True


class ComunicadoEntrada(BaseModel):
    titulo: str = Field(max_length=400)
    cuerpo: str = Field(max_length=8000)
    vigencia_horas: int = Field(default=24, ge=1, le=720)


@router.post("/cierres", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(exige(Permission.CONFIRMAR_CIERRE_VIA))])
def confirmar_cierre(
    datos: CierreEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """RF-15. §6: solo el operador municipal o una fuente oficial cierran una vía.

    Un cierre creado aquí es MUNICIPAL y, por tanto, vinculante: provoca
    descarte duro de toda ruta que lo cruce (§20.2). Es la acción de mayor
    consecuencia de todo el sistema para un solo usuario.
    """
    if datos.lat is None and datos.poligono is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Un cierre necesita un punto o un polígono: sin geometría no se puede "
            "excluir de la ruta (§20.1).",
        )

    cierre = RoadBlock(
        nombre_via=datos.nombre_via,
        motivo=datos.motivo,
        descripcion=datos.descripcion,
        confianza=ConfidenceLevel.MUNICIPAL,
        confirmado_por_id=user.id,
        punto=from_shape(Point(datos.lon, datos.lat), srid=SRID)
        if datos.lat is not None and datos.lon is not None
        else None,
        poligono=from_shape(Polygon([(p[1], p[0]) for p in datos.poligono]), srid=SRID)
        if datos.poligono
        else None,
        vigente=True,
        inicio_at=datetime.now(UTC),
    )
    session.add(cierre)
    session.flush()

    auditar(session, request, actor=user, accion="cierre.confirmar", entidad="road_block",
            entidad_id=str(cierre.id),
            detalle={"via": datos.nombre_via, "motivo": datos.motivo.value})

    return {
        "id": str(cierre.id),
        "via": cierre.nombre_via,
        "confianza": cierre.confianza.value,
        "vinculante": cierre.es_vinculante(),
        "efecto": "descarte duro de toda ruta que cruce este cierre (§20.2)",
    }


@router.post("/cierres/{cierre_id}/reabrir",
             dependencies=[Depends(exige(Permission.CONFIRMAR_CIERRE_VIA))])
def reabrir_via(
    cierre_id: str,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """RF-15. La reapertura también es municipal y también se audita."""
    cierre = session.get(RoadBlock, cierre_id)
    if cierre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cierre no encontrado")

    ahora = datetime.now(UTC)
    cierre.vigente = False
    cierre.reabierto_at = ahora
    cierre.fin_at = ahora

    auditar(session, request, actor=user, accion="cierre.reabrir", entidad="road_block",
            entidad_id=str(cierre.id))
    return {"id": str(cierre.id), "reabierto_at": ahora.isoformat()}


@router.post("/recursos", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(exige(Permission.REGISTRAR_RECURSO))])
def registrar_recurso(
    datos: RecursoEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """RF-16. El recurso nace validado porque lo registra el municipio (§6).

    Sin `validado=True` ninguna ruta podría terminar aquí: el §20.2 descarta
    toda ruta que conduzca a un destino no validado.
    """
    recurso = Resource(
        tipo=datos.tipo,
        nombre=datos.nombre,
        geom=from_shape(Point(datos.lon, datos.lat), srid=SRID),
        direccion=datos.direccion,
        distrito=datos.distrito,
        telefono=datos.telefono,
        capacidad=datos.capacidad,
        disponible=datos.disponible,
        acepta_mascotas=datos.acepta_mascotas,
        accesible_movilidad_reducida=datos.accesible_movilidad_reducida,
        validado=True,
        registrado_por_id=user.id,
        actualizado_en_origen=datetime.now(UTC),
    )
    session.add(recurso)
    session.flush()

    auditar(session, request, actor=user, accion="recurso.registrar", entidad="resource",
            entidad_id=str(recurso.id), detalle={"tipo": datos.tipo})
    return {"id": str(recurso.id), "nombre": recurso.nombre, "validado": True}


@router.post("/comunicados", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(exige(Permission.PUBLICAR_COMUNICADO))])
def publicar_comunicado(
    datos: ComunicadoEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """§22: se publica con entidad, responsable, fecha y vigencia."""
    from datetime import timedelta

    ahora = datetime.now(UTC)
    comunicado = MunicipalNotice(
        municipalidad=user.municipality or "Municipalidad sin identificar",
        responsable_id=user.id,
        titulo=datos.titulo,
        cuerpo=datos.cuerpo,
        vigencia_inicio=ahora,
        vigencia_fin=ahora + timedelta(hours=datos.vigencia_horas),
        publicado=True,
    )
    session.add(comunicado)
    session.flush()

    auditar(session, request, actor=user, accion="comunicado.publicar",
            entidad="municipal_notice", entidad_id=str(comunicado.id))
    return {
        "id": str(comunicado.id),
        "municipalidad": comunicado.municipalidad,
        "vigencia_fin": comunicado.vigencia_fin.isoformat(),
        "precedencia_rag": "comunicado_municipal (§19, posición 5 de 10)",
    }


@router.get("/tablero", dependencies=[Depends(exige(Permission.PUBLICAR_COMUNICADO))])
def tablero(session: Session = Depends(db)) -> dict:
    """§22, indicadores del panel municipal."""
    ahora = datetime.now(UTC)

    def contar(stmt) -> int:
        return session.scalar(stmt) or 0

    fuentes = list(session.scalars(select(OfficialSource).where(OfficialSource.activa.is_(True))))

    return {
        "consultado_at": ahora.isoformat(),
        "alertas_activas": contar(
            select(func.count(Alert.id)).where(Alert.vigente.is_(True))
        ),
        "reportes_pendientes": contar(
            select(func.count(CitizenReport.id)).where(
                CitizenReport.estado == ReportState.PENDIENTE
            )
        ),
        "reportes_confirmados": contar(
            select(func.count(CitizenReport.id)).where(
                CitizenReport.estado == ReportState.CONFIRMADO
            )
        ),
        "vias_bloqueadas": contar(
            select(func.count(RoadBlock.id)).where(
                RoadBlock.vigente.is_(True), RoadBlock.reabierto_at.is_(None)
            )
        ),
        "centros_apoyo": contar(
            select(func.count(Resource.id)).where(
                Resource.validado.is_(True), Resource.disponible.is_(True)
            )
        ),
        "estado_fuentes": {
            "ok": sum(1 for f in fuentes if f.ultimo_estado is SourceStatus.OK),
            "degradado": sum(1 for f in fuentes if f.ultimo_estado is SourceStatus.DEGRADADO),
            "caido": sum(1 for f in fuentes if f.ultimo_estado is SourceStatus.CAIDO),
            "obsoleto": sum(1 for f in fuentes if f.ultimo_estado is SourceStatus.OBSOLETO),
        },
    }


@router.get("/mapa-calor", dependencies=[Depends(exige(Permission.PUBLICAR_COMUNICADO))])
def mapa_calor(
    horas: int = 24,
    celda_m: int = 300,
    session: Session = Depends(db),
) -> dict:
    """§22: mapa de calor para priorizar zonas.

    Devuelve GeoJSON agregado por celda, no los reportes sueltos. Son dos cosas
    distintas y la diferencia importa:

    - Agregar es lo que hace útil el mapa. Cien puntos encimados no dicen dónde
      concentrar recursos; una rejilla con conteos, sí.
    - Y protege a quien reporta. Un punto exacto en un mapa municipal, cruzado
      con la hora, señala una vivienda concreta. El §13.2 obliga a minimizar, y
      aquí no hace falta la precisión para decidir.

    El peso usa la escalera del §21.2: un reporte confirmado pesa más que uno
    pendiente, porque priorizar por número bruto premia al que más reporta y no
    a la zona más afectada.
    """
    from datetime import timedelta

    ahora = datetime.now(UTC)
    desde = ahora - timedelta(hours=max(1, min(horas, 24 * 7)))

    peso = case(
        (CitizenReport.trust_level == TrustLevel.CONFIRMADO, 4.0),
        (CitizenReport.trust_level == TrustLevel.VALIDADO, 3.0),
        (CitizenReport.trust_level == TrustLevel.PROBABLE, 2.0),
        else_=1.0,
    )
    # ST_SnapToGrid trabaja en grados; se convierte el tamaño de celda pedido
    # en metros a su equivalente aproximado en latitud.
    lado = celda_m / 111_320.0

    celda = func.ST_SnapToGrid(CitizenReport.geom, lado, lado)
    stmt = (
        select(
            func.ST_X(func.ST_Centroid(func.ST_Collect(CitizenReport.geom))).label("lon"),
            func.ST_Y(func.ST_Centroid(func.ST_Collect(CitizenReport.geom))).label("lat"),
            func.count(CitizenReport.id).label("reportes"),
            func.sum(peso).label("peso"),
        )
        .where(
            CitizenReport.reportado_at >= desde,
            CitizenReport.estado.notin_(
                [ReportState.RECHAZADO, ReportState.DUPLICADO, ReportState.BORRADOR]
            ),
        )
        .group_by(celda)
        .order_by(text("peso DESC"))
        .limit(500)
    )

    filas = session.execute(stmt).all()
    return {
        "type": "FeatureCollection",
        "generado_at": ahora.isoformat(),
        "ventana_horas": horas,
        "celda_m": celda_m,
        "nota": (
            "Posiciones agregadas por celda, no ubicaciones de reportes "
            "individuales (§13.2)."
        ),
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(f.lon), float(f.lat)]},
                "properties": {"reportes": int(f.reportes), "peso": float(f.peso)},
            }
            for f in filas
        ],
    }
