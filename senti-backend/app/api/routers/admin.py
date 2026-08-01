"""Administración (§23, RF-17, RF-18)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import auditar, db, exige, usuario_actual
from app.core.security import Permission, Role
from app.models import AuditLog, OfficialSource, RiskParameters, User

router = APIRouter(prefix="/admin", tags=["administración"])


class RolEntrada(BaseModel):
    role: Role


class ParametrosEntrada(BaseModel):
    version: str = Field(max_length=32)
    pesos: dict[str, float]
    riesgos: dict[str, float]
    vigencias_horas: dict[str, int]
    umbrales_cobertura: dict | None = None
    nota: str | None = None


@router.put("/usuarios/{user_id}/rol",
            dependencies=[Depends(exige(Permission.GESTIONAR_USUARIOS_Y_FUENTES))])
def cambiar_rol(
    user_id: str,
    datos: RolEntrada,
    request: Request,
    session: Session = Depends(db),
    admin: User = Depends(usuario_actual),
) -> dict:
    objetivo = session.get(User, user_id)
    if objetivo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    anterior = objetivo.role
    objetivo.role = datos.role
    auditar(session, request, actor=admin, accion="usuario.cambiar_rol", entidad="user",
            entidad_id=user_id, detalle={"de": anterior.value, "a": datos.role.value})
    return {"id": user_id, "role_anterior": anterior.value, "role": datos.role.value}


@router.post("/parametros-riesgo",
             dependencies=[Depends(exige(Permission.GESTIONAR_USUARIOS_Y_FUENTES))])
def nueva_version_parametros(
    datos: ParametrosEntrada,
    request: Request,
    session: Session = Depends(db),
    admin: User = Depends(usuario_actual),
) -> dict:
    """§23: todo cambio de parámetro queda versionado y auditado.

    No se edita la versión activa: se crea una nueva y se desactiva la
    anterior. "Una ruta pasada debe poder explicarse con los parámetros
    vigentes en su momento", y eso es imposible si los parámetros se mutan.
    """
    suma = sum(datos.pesos.values())
    if abs(suma - 1.0) > 1e-6:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Los pesos del §20.3 deben sumar 1.0; suman {suma}",
        )
    if session.scalar(select(RiskParameters).where(RiskParameters.version == datos.version)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa versión ya existe")

    for antigua in session.scalars(select(RiskParameters).where(RiskParameters.activo.is_(True))):
        antigua.activo = False

    nueva = RiskParameters(
        version=datos.version,
        activo=True,
        pesos=datos.pesos,
        riesgos=datos.riesgos,
        vigencias_horas=datos.vigencias_horas,
        umbrales_cobertura=datos.umbrales_cobertura,
        creado_por_id=admin.id,
        nota=datos.nota,
    )
    session.add(nueva)
    session.flush()

    auditar(session, request, actor=admin, accion="parametros.nueva_version",
            entidad="risk_parameters", entidad_id=str(nueva.id),
            detalle={"version": datos.version, "pesos": datos.pesos})
    return {"id": str(nueva.id), "version": nueva.version, "activo": True}


@router.get("/fuentes", dependencies=[Depends(exige(Permission.GESTIONAR_USUARIOS_Y_FUENTES))])
def listar_fuentes(session: Session = Depends(db)) -> dict:
    ahora = datetime.now(UTC)
    fuentes = list(session.scalars(select(OfficialSource)))
    return {
        "fuentes": [
            {
                "id": str(f.id),
                "slug": f.slug,
                "institucion": f.institucion,
                "url": f.url,
                "kind": f.kind.value,
                "verificada": f.verificada,
                "activa": f.activa,
                "estado": f.ultimo_estado.value,
                "citable": f.puede_citarse_como_vigente(ahora),
                "vigencia_horas": f.vigencia_horas,
            }
            for f in fuentes
        ]
    }


@router.get("/auditoria", dependencies=[Depends(exige(Permission.CONSULTAR_AUDITORIA))])
def auditoria(
    entidad: str | None = None,
    limite: int = 100,
    session: Session = Depends(db),
) -> dict:
    """RF-18. §13.5: la auditoría se conserva 24 meses."""
    stmt = select(AuditLog).order_by(AuditLog.ocurrido_at.desc()).limit(min(limite, 500))
    if entidad:
        stmt = stmt.where(AuditLog.entidad == entidad)

    return {
        "registros": [
            {
                "accion": a.accion,
                "entidad": a.entidad,
                "entidad_id": a.entidad_id,
                "actor_rol": a.actor_rol,
                "ocurrido_at": a.ocurrido_at.isoformat(),
                "detalle": a.detalle,
            }
            for a in session.scalars(stmt)
        ]
    }


class DocumentoEntrada(BaseModel):
    texto: str = Field(max_length=60000)
    titulo: str | None = Field(default=None, max_length=400)
    entidad: str | None = Field(default=None, max_length=160)
    url_origen: str | None = Field(default=None, max_length=600)
    indexar_en_rag: bool = True


@router.post("/alertas/interpretar",
             dependencies=[Depends(exige(Permission.GESTIONAR_USUARIOS_Y_FUENTES))])
def interpretar_documento(
    datos: DocumentoEntrada,
    request: Request,
    session: Session = Depends(db),
    admin: User = Depends(usuario_actual),
) -> dict:
    """§15: interpreta un boletín oficial y devuelve una PROPUESTA.

    No crea la alerta. El §15 dice que Gemma no puede cambiar el nivel oficial,
    inventar zonas, extender la vigencia ni publicar una alerta por sí sola; el
    operador revisa esta salida y publica con `POST /municipal/...` si procede.

    Si `indexar_en_rag`, el documento entra además al RAG (§19) con su hash y su
    URL, que es lo que permite citarlo después.
    """
    from app.llm import LLMInvalidOutput, LLMUnavailable
    from app.llm.analysis import extraer_alerta
    from app.rag import ingerir

    try:
        propuesta = extraer_alerta(
            datos.texto, titulo=datos.titulo, entidad=datos.entidad
        )
    except (LLMUnavailable, LLMInvalidOutput) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"No se pudo interpretar el documento: {exc}",
        ) from exc

    fragmentos = 0
    if datos.indexar_en_rag:
        resultado = ingerir(
            session,
            titulo=datos.titulo or propuesta.titulo,
            texto=datos.texto,
            url_origen=datos.url_origen,
            hazard=propuesta.tipo_evento,
            coleccion=propuesta.tipo_evento.value,
        )
        fragmentos = resultado.fragmentos

    auditar(session, request, actor=admin, accion="alerta.interpretar",
            entidad="document", detalle={"tipo": propuesta.tipo_evento.value,
                                        "fragmentos_rag": fragmentos})

    return {
        "propuesta": propuesta.model_dump(mode="json"),
        "fragmentos_indexados": fragmentos,
        "publicada": False,
        "nota": (
            "Esto es una propuesta del modelo. El §15 no le permite publicar una "
            "alerta ni fijar su nivel o vigencia: revísala y publícala tú."
        ),
    }
