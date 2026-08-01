"""Perfil del hogar, plan familiar y paquete offline (§14, §17, §26)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import auditar, db, exige, usuario_actual
from app.core.crypto import FieldCipherUnavailable, encrypt_field
from app.core.security import Permission
from app.domain import ConsentPurpose, HazardType
from app.models import Alert, Consent, FamilyPlan, HouseholdProfile, PlanTask, Protocol, User
from app.rules import phones

router = APIRouter(tags=["ciudadano"])


class PerfilEntrada(BaseModel):
    """§13.2: cada campo sensible se solicita por separado y puede omitirse.

    Todos opcionales a propósito: el perfil es opcional y el sistema funciona
    sin él con recomendaciones generales.
    """

    distrito: str | None = Field(default=None, max_length=120)
    zona_aproximada: str | None = Field(default=None, max_length=120)
    integrantes: int = Field(default=1, ge=1, le=30)
    ninos: int = Field(default=0, ge=0, le=20)
    adultos_mayores: int = Field(default=0, ge=0, le=20)
    mascotas: int = Field(default=0, ge=0, le=20)
    movilidad_reducida: bool = False
    discapacidad: bool = False
    medicamentos_habituales: bool = False
    vehiculo: bool = False
    medio_transporte: str | None = Field(default=None, max_length=32)
    punto_reunion_descripcion: str | None = Field(default=None, max_length=240)
    contacto_confianza_telefono: str | None = Field(default=None, max_length=32)
    mochila_lista: bool = False


@router.get("/perfil")
def leer_perfil(session: Session = Depends(db), user: User = Depends(usuario_actual)) -> dict:
    perfil = session.scalar(select(HouseholdProfile).where(HouseholdProfile.user_id == user.id))
    if perfil is None:
        return {
            "tiene_perfil": False,
            "nota": (
                "El perfil del hogar es opcional (§13.2). Sin él SENTI da "
                "recomendaciones generales."
            ),
        }
    return {
        "tiene_perfil": True,
        "distrito": perfil.distrito,
        "zona_aproximada": perfil.zona_aproximada,
        "integrantes": perfil.integrantes,
        "ninos": perfil.ninos,
        "adultos_mayores": perfil.adultos_mayores,
        "mascotas": perfil.mascotas,
        "movilidad_reducida": perfil.movilidad_reducida,
        "discapacidad": perfil.discapacidad,
        "medicamentos_habituales": perfil.medicamentos_habituales,
        "vehiculo": perfil.vehiculo,
        "punto_reunion_configurado": perfil.punto_reunion_configurado,
        "mochila_lista": perfil.mochila_lista,
        "contacto_confianza_configurado": bool(perfil.contacto_confianza_telefono_cifrado),
    }


@router.put("/perfil", dependencies=[Depends(exige(Permission.CONFIGURAR_HOGAR))])
def guardar_perfil(
    datos: PerfilEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """§13.2: no se guarda ningún campo sensible sin consentimiento para esa
    finalidad y sin cifrado disponible."""
    sensibles = datos.movilidad_reducida or datos.discapacidad or datos.medicamentos_habituales
    if sensibles and not _consentido(session, user, ConsentPurpose.PERFIL_HOGAR):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Falta el consentimiento para la finalidad 'perfil_hogar' (§13.4). "
            "Los datos de salud no se guardan sin él.",
        )

    telefono_cifrado = None
    if datos.contacto_confianza_telefono:
        if not _consentido(session, user, ConsentPurpose.CONTACTO_CONFIANZA):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Falta el consentimiento para 'contacto_confianza' (§13.4). Es un "
                "dato personal de un tercero que no ha consentido nada.",
            )
        try:
            telefono_cifrado = encrypt_field(datos.contacto_confianza_telefono)
        except FieldCipherUnavailable as exc:
            # §13.2: sin clave, el sistema NO lo almacena en claro.
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    perfil = session.scalar(select(HouseholdProfile).where(HouseholdProfile.user_id == user.id))
    if perfil is None:
        perfil = HouseholdProfile(user_id=user.id)
        session.add(perfil)

    for campo in (
        "distrito", "zona_aproximada", "integrantes", "ninos", "adultos_mayores",
        "mascotas", "movilidad_reducida", "discapacidad", "medicamentos_habituales",
        "vehiculo", "medio_transporte", "punto_reunion_descripcion", "mochila_lista",
    ):
        setattr(perfil, campo, getattr(datos, campo))
    perfil.punto_reunion_configurado = bool(datos.punto_reunion_descripcion)
    if telefono_cifrado is not None:
        perfil.contacto_confianza_telefono_cifrado = telefono_cifrado

    # El detalle auditado NO incluye los valores sensibles: la auditoría vive
    # 24 meses y el perfil se borra a solicitud; copiarlo ahí sería burlar el
    # propio derecho de supresión.
    auditar(session, request, actor=user, accion="perfil.guardar", entidad="household_profile",
            entidad_id=str(user.id), detalle={"campos_sensibles_presentes": sensibles})

    return {"ok": True, "distrito": perfil.distrito}


def _consentido(session: Session, user: User, purpose: ConsentPurpose) -> bool:
    c = session.scalar(
        select(Consent).where(Consent.user_id == user.id, Consent.purpose == purpose)
    )
    return bool(c and c.granted and c.revoked_at is None)


@router.post("/plan-familiar", dependencies=[Depends(exige(Permission.GENERAR_PLAN))])
def generar_plan(
    request: Request,
    alert_id: str | None = None,
    horizonte_horas: int = 2,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """§17. Las acciones críticas salen del protocolo, no del modelo.

    El modelo puede reordenar y explicar (lo hace el orquestador cuando el
    ciudadano pregunta), pero este endpoint garantiza que el plan existe y es
    correcto aunque el modelo esté apagado.
    """
    ahora = datetime.now(UTC)
    perfil = session.scalar(select(HouseholdProfile).where(HouseholdProfile.user_id == user.id))

    tipo = HazardType.INUNDACION
    alerta = session.get(Alert, alert_id) if alert_id else None
    if alerta:
        tipo = alerta.tipo_evento

    protocolo = session.scalar(
        select(Protocol).where(Protocol.activo.is_(True), Protocol.hazard_type == tipo.value)
    ) or session.scalar(select(Protocol).where(Protocol.activo.is_(True)))
    if protocolo is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No hay protocolo configurado. SENTI no inventa acciones críticas (§17).",
        )

    plan = FamilyPlan(
        user_id=user.id,
        alert_id=alerta.id if alerta else None,
        titulo=f"Plan para las próximas {horizonte_horas} horas",
        horizonte_horas=horizonte_horas,
        perfil_snapshot=perfil.as_routing_profile() if perfil else None,
        protocolo_version=protocolo.version,
        generado_at=ahora,
    )
    session.add(plan)
    session.flush()

    for i, accion in enumerate(_filtrar_por_hogar(protocolo.acciones, perfil)):
        session.add(
            PlanTask(
                plan_id=plan.id,
                prioridad=accion.get("prioridad", i),
                texto=accion["texto"],
                critica=accion.get("critica", False),
                origen_protocolo=protocolo.codigo,
                motivo_personalizacion=accion.get("motivo"),
            )
        )

    auditar(session, request, actor=user, accion="plan.generar", entidad="family_plan",
            entidad_id=str(plan.id), detalle={"protocolo": protocolo.codigo})
    session.flush()

    return {
        "plan_id": str(plan.id),
        "titulo": plan.titulo,
        "protocolo": protocolo.codigo,
        "protocolo_version": protocolo.version,
        "tareas": [
            {"prioridad": t.prioridad, "texto": t.texto, "critica": t.critica,
             "motivo": t.motivo_personalizacion}
            for t in sorted(plan.tasks, key=lambda t: t.prioridad)
        ],
    }


def _filtrar_por_hogar(acciones: list[dict], perfil: HouseholdProfile | None) -> list[dict]:
    """§14: el perfil decide qué tareas aparecen y en qué orden.

    Una acción con `condicion_hogar` solo aparece si el hogar la cumple: una
    tarea sobre la mascota en un hogar sin mascotas es ruido en un momento en
    que el ruido cuesta tiempo.
    """
    resultado = []
    for accion in acciones:
        condicion = accion.get("condicion_hogar")
        if condicion and perfil is not None:
            campo, esperado = next(iter(condicion.items()))
            actual = getattr(perfil, campo, None)
            cumple = bool(actual) if isinstance(esperado, bool) and esperado else actual == esperado
            if isinstance(esperado, bool) and esperado and not cumple:
                continue
            if isinstance(esperado, int) and not isinstance(esperado, bool):
                if (actual or 0) < esperado:
                    continue
        elif condicion and perfil is None:
            continue

        copia = dict(accion)
        if condicion and perfil is not None:
            copia["motivo"] = f"aplica por el perfil del hogar: {condicion}"
        resultado.append(copia)
    return sorted(resultado, key=lambda a: a.get("prioridad", 99))


@router.get("/offline/paquete")
def paquete_offline(
    session: Session = Depends(db), user: User = Depends(usuario_actual)
) -> dict:
    """§26. Todo lo que se guarda lleva su fecha de sincronización.

    "No presenta una alerta antigua como vigente": el cliente muestra
    `sincronizado_at`, no la hora actual.
    """
    ahora = datetime.now(UTC)
    perfil = session.scalar(select(HouseholdProfile).where(HouseholdProfile.user_id == user.id))
    plan = session.scalar(
        select(FamilyPlan)
        .where(FamilyPlan.user_id == user.id)
        .order_by(FamilyPlan.generado_at.desc())
    )
    ultima_alerta = session.scalar(
        select(Alert).where(Alert.vigente.is_(True)).order_by(Alert.created_at.desc())
    )

    from app.rules.fixed_responses import SIN_SENAL

    return {
        "sincronizado_at": ahora.isoformat(),
        "telefonos": [
            {"situacion": c.situacion, "numero": c.numero, "entidad": c.entidad}
            for c in phones.para_region(
                phones.REGION_LIMA_CALLAO
                if (perfil and perfil.distrito and "lima" in (perfil.distrito or "").lower())
                else phones.REGION_NACIONAL
            )
        ],
        "instruccion_sin_senal": SIN_SENAL,
        "plan": (
            {
                "titulo": plan.titulo,
                "generado_at": plan.generado_at.isoformat(),
                "tareas": [
                    {"texto": t.texto, "critica": t.critica, "completada": t.completada}
                    for t in sorted(plan.tasks, key=lambda t: t.prioridad)
                ],
            }
            if plan
            else None
        ),
        "ultima_alerta": (
            {
                "titulo": ultima_alerta.titulo,
                "nivel": ultima_alerta.nivel_oficial,
                "entidad": ultima_alerta.entidad_emisora,
                "fecha": ultima_alerta.created_at.isoformat(),
                "advertencia": (
                    "Esta es la última alerta que se pudo descargar. "
                    "Puede no estar vigente."
                ),
            }
            if ultima_alerta
            else None
        ),
        "no_disponible_offline": [
            "alertas nuevas",
            "estado de vías en tiempo real",
            "nuevos reportes",
            "confirmaciones municipales",
            "recálculo con datos externos recientes",
        ],
    }
