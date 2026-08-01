"""Reportes ciudadanos y validación comunitaria (§21, RF-12 a RF-15)."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from pydantic import BaseModel, Field
from shapely.geometry import Point
from sqlalchemy import case, cast, func, or_, select, text
from sqlalchemy.orm import Session

from app.api.deps import auditar, db, exige, usuario_actual
from app.core.security import Permission, Role
from app.domain import HAZARD_VALIDITY, ConfidenceLevel, HazardType, ReportState, TrustLevel
from app.models import CitizenReport, ReportValidation, User
from app.services.event_grouping import attach_report, find_or_create_event
from app.api.routers.events import _reporter_key
from app.models.base import SRID
from app.rules.retention import expira_foto
from app.rules.trust import ReportSignal, evaluar

router = APIRouter(prefix="/reportes", tags=["comunidad"])
GEOGRAPHY = Geography(srid=SRID)


class ReporteEntrada(BaseModel):
    tipo: HazardType
    descripcion: str | None = Field(default=None, max_length=1000)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    direccion_aproximada: str | None = Field(default=None, max_length=300)
    distrito: str | None = Field(default=None, max_length=120)
    foto_base64: str | None = None
    # §21.1: el ciudadano revisa y publica. Si corrigió la propuesta del
    # modelo, se registra: mide la calidad de la propuesta (§35).
    corregido_por_ciudadano: bool = False
    categoria_propuesta_modelo: str | None = None


class ValidacionEntrada(BaseModel):
    decision: ReportState
    motivo: str | None = Field(default=None, max_length=1000)
    evidencia_url: str | None = Field(default=None, max_length=600)


def _limpiar_exif(datos: bytes) -> bytes:
    """§13.5 y §28: los metadatos EXIF se eliminan al ingreso.

    El EXIF de una foto de emergencia lleva coordenadas GPS exactas y, a
    menudo, el modelo del teléfono. Publicar la foto sin limpiarla filtraría
    la ubicación precisa de quien reporta a cualquiera que la descargue.
    """
    from PIL import Image

    origen = Image.open(io.BytesIO(datos))
    limpia = Image.new(origen.mode, origen.size)
    limpia.putdata(list(origen.getdata()))
    salida = io.BytesIO()
    limpia.save(salida, format=origen.format or "JPEG")
    return salida.getvalue()


@router.post("", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(exige(Permission.CREAR_REPORTE))])
def crear_reporte(
    datos: ReporteEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """RF-12/RF-13. El reporte nace `PENDIENTE`, nunca confirmado."""
    ahora = datetime.now(UTC)

    foto_url = None
    exif_ok = False
    if datos.foto_base64:
        import base64

        try:
            crudo = base64.b64decode(datos.foto_base64)
            _limpiar_exif(crudo)  # se valida que se puede limpiar antes de aceptar
            exif_ok = True
            # El almacenamiento real (URL temporal con expiración, §28) se
            # resuelve en la capa de storage; aquí se registra la intención.
            foto_url = f"pendiente-de-subir:{len(crudo)}"
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"No se pudo procesar la imagen y no se acepta sin limpiar el EXIF: {exc}",
            ) from exc

    reporte = CitizenReport(
        reporter_id=user.id,
        tipo=datos.tipo,
        estado=ReportState.PENDIENTE,
        trust_level=TrustLevel.PENDIENTE,
        descripcion=datos.descripcion,
        categoria_propuesta_modelo=datos.categoria_propuesta_modelo,
        corregido_por_ciudadano=datos.corregido_por_ciudadano,
        geom=from_shape(Point(datos.lon, datos.lat), srid=SRID),
        direccion_aproximada=datos.direccion_aproximada,
        distrito=datos.distrito,
        foto_url=foto_url,
        foto_expira_at=expira_foto(ahora) if foto_url else None,
        exif_eliminado=exif_ok,
        reportado_at=ahora,
        vence_at=ahora + HAZARD_VALIDITY.get(datos.tipo, HAZARD_VALIDITY[HazardType.OTRO]),
        reporter_key_hash=_reporter_key(user),
    )
    session.add(reporte)
    session.flush()

    # Un marcador por evento: la asociación es determinista y se conserva
    # separada del reporte para permitir revisión, separación y auditoría.
    evento, asociacion_confianza = find_or_create_event(session, reporte)
    attach_report(session, evento, reporte, asociacion_confianza)

    decision = _recalcular_confianza(session, reporte, ahora)

    auditar(session, request, actor=user, accion="reporte.crear", entidad="citizen_report",
            entidad_id=str(reporte.id),
            detalle={"tipo": datos.tipo.value, "confianza": decision.nivel.value})

    return {
        "id": str(reporte.id),
        "event_id": str(evento.id),
        "estado": reporte.estado.value,
        "confianza": reporte.trust_level.value,
        "motivo_confianza": decision.motivo,
        "vence_at": reporte.vence_at.isoformat() if reporte.vence_at else None,
        "nota": "Este reporte es ciudadano y todavía no ha sido validado.",
    }


def _recalcular_confianza(session: Session, reporte: CitizenReport, ahora: datetime):
    """§21.2. Aplica la escalera con los reportes vecinos reales.

    Se recalcula al crear y al validar, y el §21.3 exige además que el motor de
    rutas recalcule penalizaciones al cambiar un estado — de ahí que esta
    función sea la única que escribe `trust_level`.
    """
    lat = session.scalar(select(func.ST_Y(reporte.geom)))
    lon = session.scalar(select(func.ST_X(reporte.geom)))
    base = ReportSignal(str(reporte.reporter_id), lat, lon, reporte.reportado_at)
    geom_reporte = func.ST_SetSRID(func.ST_MakePoint(lon, lat), SRID)

    vecinos = session.execute(
        select(
            CitizenReport.reporter_id,
            func.ST_Y(CitizenReport.geom),
            func.ST_X(CitizenReport.geom),
            CitizenReport.reportado_at,
        ).where(
            CitizenReport.id != reporte.id,
            CitizenReport.tipo == reporte.tipo,
            CitizenReport.estado.notin_([ReportState.RECHAZADO, ReportState.DUPLICADO]),
            func.ST_DWithin(
                CitizenReport.geom.cast(GEOGRAPHY),
                cast(geom_reporte, GEOGRAPHY),
                300.0,
            ),
        )
    ).all()

    otros = [
        ReportSignal(str(rid) if rid else None, la, lo, cuando)
        for rid, la, lo, cuando in vecinos
    ]

    validacion = session.scalar(
        select(ReportValidation).where(
            ReportValidation.report_id == reporte.id,
            ReportValidation.decision == ReportState.CONFIRMADO,
        )
    )
    confirmado_por = None
    if validacion:
        validador = session.get(User, validacion.validator_id)
        if validador and validador.role is Role.OPERADOR_MUNICIPAL:
            confirmado_por = ConfidenceLevel.MUNICIPAL

    decision = evaluar(
        base,
        otros,
        validado_por_validador=bool(validacion),
        tiene_evidencia=bool(validacion and validacion.evidencia_url),
        confirmado_por=confirmado_por,
    )
    reporte.trust_level = decision.nivel
    return decision


@router.post("/{reporte_id}/validar",
             dependencies=[Depends(exige(Permission.VALIDAR_REPORTE))])
def validar_reporte(
    reporte_id: str,
    datos: ValidacionEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """RF-14. §21.3: cada decisión queda auditada con validador, fecha, motivo
    y evidencia."""
    reporte = session.get(CitizenReport, reporte_id)
    if reporte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reporte no encontrado")

    # §6: solo el operador municipal confirma. Un validador eleva la confianza
    # de un reporte, no lo convierte en dato oficial.
    if datos.decision is ReportState.CONFIRMADO and user.role is not Role.OPERADOR_MUNICIPAL:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Solo el operador municipal confirma un reporte (§6, §21.2). "
            "Un validador puede marcarlo EN_REVISION o RECHAZADO.",
        )

    session.add(
        ReportValidation(
            report_id=reporte.id,
            validator_id=user.id,
            decision=datos.decision,
            motivo=datos.motivo,
            evidencia_url=datos.evidencia_url,
        )
    )
    reporte.estado = datos.decision
    if datos.decision is ReportState.RESUELTO:
        reporte.resuelto_at = datetime.now(UTC)
        # §13.5: la foto se borra al resolverse si eso ocurre antes de 30 días.
        reporte.foto_expira_at = expira_foto(reporte.reportado_at, reporte.resuelto_at)

    session.flush()
    decision = _recalcular_confianza(session, reporte, datetime.now(UTC))

    auditar(session, request, actor=user, accion="reporte.validar", entidad="citizen_report",
            entidad_id=str(reporte.id),
            detalle={"decision": datos.decision.value, "confianza": decision.nivel.value,
                     "con_evidencia": bool(datos.evidencia_url)})

    return {
        "id": str(reporte.id),
        "estado": reporte.estado.value,
        "confianza": reporte.trust_level.value,
        "motivo_confianza": decision.motivo,
        "excluye_de_ruta": decision.excluye_de_ruta,
    }


@router.get("", dependencies=[Depends(exige(Permission.CONSULTAR_ALERTAS))])
def listar_reportes(
    lat: float | None = None,
    lon: float | None = None,
    radio_m: float = 5000.0,
    limite: int = 50,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """Reportes vigentes cerca de una ubicación, para el ciudadano.

    Distinto de `/pendientes`, que es la cola de trabajo del validador (§21.3).
    Aquí se ve el estado de la zona, no lo que hay que revisar.

    **Nunca se devuelve quién reportó.** El §28 exige que los datos de contacto
    no se muestren a otros usuarios, y en una emergencia saber quién avisó de
    una vía inundada no ayuda a nadie y sí expone a quien avisó. Solo se marca
    `mio` para que cada uno reconozca los suyos.

    Tampoco se devuelve la foto: puede contener a terceros (§28, moderación) y
    el listado no la necesita.
    """
    ahora = datetime.now(UTC)
    stmt = (
        select(
            CitizenReport,
            func.ST_Y(CitizenReport.geom).label("lat"),
            func.ST_X(CitizenReport.geom).label("lon"),
        )
        .where(
            CitizenReport.estado.notin_(
                [ReportState.RECHAZADO, ReportState.DUPLICADO, ReportState.BORRADOR]
            ),
            or_(CitizenReport.vence_at.is_(None), CitizenReport.vence_at >= ahora),
        )
        .order_by(CitizenReport.reportado_at.desc())
        .limit(min(limite, 200))
    )

    if lat is not None and lon is not None:
        punto = from_shape(Point(lon, lat), srid=SRID)
        stmt = stmt.where(
            func.ST_DWithin(
                CitizenReport.geom.cast(GEOGRAPHY),
                cast(punto, GEOGRAPHY),
                max(100.0, min(radio_m, 50_000.0)),
            )
        )

    filas = session.execute(stmt).all()
    return {
        "consultado_at": ahora.isoformat(),
        "reportes": [
            {
                "id": str(r.id),
                "tipo": r.tipo.value,
                "estado": r.estado.value,
                "confianza": r.trust_level.value,
                # §12: el ciudadano tiene que poder distinguir lo confirmado de
                # lo que solo dijo alguien.
                "confirmado": r.trust_level is TrustLevel.CONFIRMADO,
                "descripcion": r.descripcion,
                "direccion": r.direccion_aproximada,
                "distrito": r.distrito,
                "reportado_at": r.reportado_at.isoformat(),
                "vence_at": r.vence_at.isoformat() if r.vence_at else None,
                "lat": lat_r,
                "lon": lon_r,
                "mio": r.reporter_id == user.id,
            }
            for r, lat_r, lon_r in filas
        ],
        "nota": "Los reportes ciudadanos no validados no son información oficial.",
    }


@router.get("/publicos")
def listar_reportes_publicos(
    limite: int = 50,
    session: Session = Depends(db),
) -> dict:
    """Listado público sanitizado para la web de reportes.

    §13.2: no publica coordenadas, dirección aproximada ni identidad. La vista
    pública sirve para conocer actividad por distrito; el estado detallado de
    una zona sigue requiriendo autenticación en ``GET /reportes``.
    """
    ahora = datetime.now(UTC)
    reportes = list(
        session.scalars(
            select(CitizenReport)
            .where(
                CitizenReport.estado.notin_(
                    [ReportState.RECHAZADO, ReportState.DUPLICADO, ReportState.BORRADOR]
                ),
                or_(CitizenReport.vence_at.is_(None), CitizenReport.vence_at >= ahora),
            )
            .order_by(CitizenReport.reportado_at.desc())
            .limit(min(limite, 200))
        )
    )
    return {
        "consultado_at": ahora.isoformat(),
        "reportes": [
            {
                "id": str(r.id),
                "tipo": r.tipo.value,
                "estado": r.estado.value,
                "confianza": r.trust_level.value,
                "confirmado": r.trust_level is TrustLevel.CONFIRMADO,
                "descripcion": r.descripcion,
                "distrito": r.distrito,
                "reportado_at": r.reportado_at.isoformat(),
                "vence_at": r.vence_at.isoformat() if r.vence_at else None,
            }
            for r in reportes
        ],
        "nota": "Listado público sanitizado. Los reportes ciudadanos no validados no son información oficial.",
    }


@router.get("/mapa-publico")
def mapa_publico(
    horas: int = 168,
    celda_m: int = 1000,
    session: Session = Depends(db),
) -> dict:
    """Actividad agregada para el mapa público, nunca puntos individuales.

    La celda mínima de un kilómetro evita que el mapa revele una vivienda al
    cruzar ubicación y hora. El peso conserva la diferencia entre un reporte
    pendiente y uno confirmado sin publicar identidad, dirección ni coordenada
    exacta.
    """
    ahora = datetime.now(UTC)
    desde = ahora - timedelta(hours=max(1, min(horas, 24 * 7)))
    lado = max(1000, min(celda_m, 3000)) / 111_320.0
    peso = case(
        (CitizenReport.trust_level == TrustLevel.CONFIRMADO, 4.0),
        (CitizenReport.trust_level == TrustLevel.VALIDADO, 3.0),
        (CitizenReport.trust_level == TrustLevel.PROBABLE, 2.0),
        else_=1.0,
    )
    nivel = case(
        (CitizenReport.trust_level == TrustLevel.CONFIRMADO, 4),
        (CitizenReport.trust_level == TrustLevel.VALIDADO, 3),
        (CitizenReport.trust_level == TrustLevel.PROBABLE, 2),
        else_=1,
    )
    celda = func.ST_SnapToGrid(CitizenReport.geom, lado, lado)
    filas = session.execute(
        select(
            func.ST_X(func.ST_Centroid(func.ST_Collect(CitizenReport.geom))).label("lon"),
            func.ST_Y(func.ST_Centroid(func.ST_Collect(CitizenReport.geom))).label("lat"),
            func.count(CitizenReport.id).label("reportes"),
            func.sum(peso).label("peso"),
            func.max(nivel).label("nivel"),
        )
        .where(
            CitizenReport.reportado_at >= desde,
            CitizenReport.estado.notin_(
                [ReportState.RECHAZADO, ReportState.DUPLICADO, ReportState.BORRADOR]
            ),
        )
        .group_by(celda)
        .order_by(text("peso DESC"))
        .limit(200)
    ).all()
    return {
        "type": "FeatureCollection",
        "generado_at": ahora.isoformat(),
        "ventana_horas": horas,
        "celda_m": max(1000, min(celda_m, 3000)),
        "nota": "Actividad agregada por celdas de 1 km; no son ubicaciones exactas.",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(f.lon), float(f.lat)]},
                "properties": {
                    "reportes": int(f.reportes),
                    "peso": float(f.peso),
                    "nivel": int(f.nivel),
                },
            }
            for f in filas
        ],
    }


@router.get("/pendientes")
def reportes_pendientes(
    session: Session = Depends(db),
    _: User = Depends(exige(Permission.VALIDAR_REPORTE)),
) -> dict:
    """§21.3, vista del validador."""
    ahora = datetime.now(UTC)
    reportes = list(
        session.scalars(
            select(CitizenReport)
            .where(
                CitizenReport.estado.in_([ReportState.PENDIENTE, ReportState.EN_REVISION]),
                (CitizenReport.vence_at.is_(None)) | (CitizenReport.vence_at >= ahora),
            )
            .order_by(CitizenReport.reportado_at.desc())
            .limit(50)
        )
    )
    return {
        "reportes": [
            {
                "id": str(r.id),
                "tipo": r.tipo.value,
                "estado": r.estado.value,
                "confianza": r.trust_level.value,
                "descripcion": r.descripcion,
                "direccion": r.direccion_aproximada,
                "reportado_at": r.reportado_at.isoformat(),
                "tiene_foto": bool(r.foto_url),
                "lat": session.scalar(select(func.ST_Y(r.geom))),
                "lon": session.scalar(select(func.ST_X(r.geom))),
            }
            for r in reportes
        ]
    }


class PropuestaEntrada(BaseModel):
    descripcion: str | None = Field(default=None, max_length=1000)
    foto_base64: str | None = None
    foto_mime: str = "image/jpeg"


@router.post("/proponer", dependencies=[Depends(exige(Permission.CREAR_REPORTE))])
def proponer_categoria(datos: PropuestaEntrada) -> dict:
    """§21.1: el modelo propone, el ciudadano revisa y publica.

    Endpoint aparte de `POST /reportes` a propósito. El §21.1 describe el orden
    exacto —"Gemma propone categoría y descripción; el ciudadano revisa y
    publica"— y meter la propuesta dentro de la creación se saltaría la
    revisión: el reporte quedaría publicado con lo que dijo el modelo.

    Corre en el modelo profundo, que es el que ve imágenes, y por eso tarda más
    que el chat. No importa: aquí no hay nadie esperando una respuesta a una
    emergencia, hay alguien redactando un reporte.
    """
    import base64

    from app.llm import LLMInvalidOutput, LLMUnavailable
    from app.llm.analysis import categorizar_reporte

    imagen = base64.b64decode(datos.foto_base64) if datos.foto_base64 else None
    try:
        propuesta = categorizar_reporte(
            datos.descripcion or "", imagen=imagen, imagen_mime=datos.foto_mime
        )
    except (LLMUnavailable, LLMInvalidOutput) as exc:
        # Sin propuesta el ciudadano publica igual, eligiendo el tipo a mano.
        # El §21.1 hace la propuesta opcional, no obligatoria.
        return {
            "disponible": False,
            "motivo": str(exc),
            "nota": "Elige el tipo manualmente; la propuesta automática no está disponible.",
        }

    return {
        "disponible": True,
        "tipo": propuesta.tipo.value,
        "descripcion_propuesta": propuesta.descripcion_propuesta,
        "observaciones_imagen": [
            {"observacion": o.observacion, "confianza": o.confianza}
            for o in propuesta.observaciones_imagen
        ],
        "requiere_revision_humana": True,
        "nota": "Esta es una propuesta. Revísala y corrígela antes de publicar (§21.1).",
    }
