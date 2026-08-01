"""Chat dinámico de SENTI (§16, RF-07)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import auditar, contexto_herramientas, db, usuario_opcional
from app.core.queue import profundidad
from app.domain import Channel, OperationLevel
from app.models import Conversation, Message, User
from app.orchestrator import EntradaUsuario, Orchestrator, ToolContext
from app.rules.retention import RetentionPolicy, expira_en
from app.rules.urgency import StructuralSignals
from app.tasks.celery_app import responder_diferido

router = APIRouter(prefix="/chat", tags=["chat"])

# Mensajes del hilo que se le recuerdan al modelo: seis intercambios.
TURNOS_DE_MEMORIA = 12

# De esos, cuántos van literales. Los últimos dos intercambios se mandan tal
# cual porque es donde viven los pronombres: «y por ahí se puede pasar?» no
# significa nada sin la frase anterior entera.
TURNOS_LITERALES = 4

# Los anteriores se resumen a esto. No hace falta un modelo para resumir: en
# una conversación de emergencia lo que importa de un turno viejo es de qué iba,
# y eso está en las primeras palabras. Un resumen generado costaría otra llamada
# al modelo —siete segundos en CPU— para ahorrar unas fichas de prompt.
MAX_CARACTERES_RESUMIDO = 120


def _comprimir(mensajes: list[Message]) -> list[tuple[str, str]]:
    """Deja literales los últimos turnos y resume los anteriores.

    Medido: doce mensajes completos son ~600 fichas de prompt en cada
    petición. Comprimiendo los ocho más viejos bajan a la mitad, y lo que se
    pierde son los finales de frases que el modelo ya no necesita.
    """
    if len(mensajes) <= TURNOS_LITERALES:
        return [(m.rol, m.contenido) for m in mensajes]

    viejos, recientes = mensajes[:-TURNOS_LITERALES], mensajes[-TURNOS_LITERALES:]
    comprimidos = []
    for m in viejos:
        texto = " ".join((m.contenido or "").split())
        if len(texto) > MAX_CARACTERES_RESUMIDO:
            texto = texto[:MAX_CARACTERES_RESUMIDO].rstrip() + "…"
        if texto:
            comprimidos.append((m.rol, texto))
    return comprimidos + [(m.rol, m.contenido) for m in recientes]


class MensajeEntrada(BaseModel):
    texto: str = Field(max_length=4000)
    conversation_id: str | None = None
    canal: Channel = Channel.PWA
    nivel_operacion: OperationLevel = OperationLevel.N0_NORMAL
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    # Imagen en base64. §13.4: la fotografía pide confirmación aparte la
    # primera vez porque puede contener datos de salud de terceros.
    imagen_base64: str | None = None
    imagen_mime: str = "image/jpeg"


class MensajeSalida(BaseModel):
    texto: str
    urgencia: str
    respuesta_plantilla_fija: bool
    motivo_plantilla: str | None = None
    fuentes: list[dict] = []
    herramientas: list[dict] = []
    latencia_ms: float
    modelo: str | None = None
    conversation_id: str | None = None
    advertencias: list[str] = []
    # §7.3: el mapa es una mejora; los pasos van en el texto.
    ruta: dict | None = None
    # Lugar encontrado (nombre, dirección, lat, lon) para abrirlo en el mapa.
    lugar: dict | None = None
    # §29: hay una respuesta más completa en camino.
    respuesta_diferida_en_curso: bool = False
    # §7.4: el backend midió una latencia que aconseja degradar el canal. El
    # cliente decide, porque las otras tres condiciones solo las ve él.
    sugerir_modo_ligero: bool = False
    motivo_modo_ligero: str | None = None


@router.post("", response_model=MensajeSalida)
def conversar(
    entrada: MensajeEntrada,
    request: Request,
    session: Session = Depends(db),
    ctx: ToolContext = Depends(contexto_herramientas),
    user: User | None = Depends(usuario_opcional),
) -> MensajeSalida:
    """§8: el mensaje entra, se clasifica, se consultan herramientas y el
    modelo redacta sobre un resultado ya verificado.

    Funciona sin autenticación (modo invitado del §13.4): sin usuario no hay
    herramientas disponibles, así que la respuesta es información general —
    que es exactamente lo que el §13.4 promete al invitado.
    """
    ahora = datetime.now(UTC)

    conversacion = None
    if entrada.conversation_id:
        conversacion = session.get(Conversation, entrada.conversation_id)
    if conversacion is None:
        conversacion = Conversation(
            user_id=user.id if user else None,
            canal=entrada.canal,
            nivel_operacion=entrada.nivel_operacion,
            expira_at=expira_en(RetentionPolicy.MENSAJES, ahora),
        )
        session.add(conversacion)
        session.flush()

    # Historial de ESTE hilo, y de ninguno más.
    #
    # Sin esto el modelo respondía cada mensaje como si fuera el primero: a
    # «¿qué llevo en mi mochila?» contestaba «necesito saber qué emergencia
    # estás viviendo», después de haber hablado de una alerta naranja dos
    # mensajes antes. Conversar es acordarse de lo anterior.
    #
    # Se acotan los turnos porque el contexto se paga en cada ficha generada y
    # el servidor va en CPU. Y de esos doce, solo los cuatro últimos van
    # literales: los anteriores se resumen, porque de un turno viejo lo que
    # importa es de qué iba y eso está en sus primeras palabras.
    #
    # El aislamiento es por conversación, que es lo que separa un hilo de otro
    # (§13.5): nunca se mezcla lo que alguien dijo en otra conversación suya, y
    # mucho menos en la de otra persona.
    historial = list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversacion.id)
            .order_by(Message.enviado_at.desc())
            .limit(TURNOS_DE_MEMORIA)
        )
    )[::-1]
    contexto_previo = next(
        (m.contenido for m in reversed(historial) if m.rol == "user"), None
    )

    # La imagen del chat NO se persiste. Se decodifica, se le pasa al modelo
    # para que describa lo observable (§25) y se descarta al terminar la
    # petición: `Message` solo tiene texto, y no se registra en el log.
    #
    # Es distinto de la foto de un reporte, que sí se guarda porque un
    # validador tiene que poder verla (§21.3) y por eso el §13.5 le da 30 días.
    # Una foto de chat no la revisa nadie después, así que guardarla sería
    # retener un dato sin finalidad, que es justo lo que prohíbe el §13.2.
    #
    # Lo garantiza `test_privacidad.py`. Si alguien añade un campo de imagen a
    # Message, ese test falla.
    imagen = base64.b64decode(entrada.imagen_base64) if entrada.imagen_base64 else None

    # §29: la profundidad real de la cola decide si naranja cae a plantilla
    # fija. Antes llegaba siempre 0 y la protección bajo carga no se activaba
    # nunca.
    orquestador = Orchestrator(ctx, profundidad_cola=profundidad())
    salida = orquestador.responder(
        EntradaUsuario(
            texto=entrada.texto,
            canal=entrada.canal,
            imagen=imagen,
            imagen_mime=entrada.imagen_mime,
            lat=entrada.lat,
            lon=entrada.lon,
            nivel_operacion=entrada.nivel_operacion,
            senales=StructuralSignals(tiene_imagen=imagen is not None),
            contexto_previo=contexto_previo,
            historial=_comprimir(historial),
        )
    )

    session.add(
        Message(
            conversation_id=conversacion.id,
            rol="user",
            contenido=entrada.texto,
            urgencia=salida.urgencia,
            enviado_at=ahora,
        )
    )

    # §29: ¿va a haber una respuesta de verdad detrás de esta?
    #
    # Lo decide el orquestador, que es quien sabe si la plantilla que devolvió
    # era la respuesta o solo lo que cupo bajo carga. El rojo no se difiere
    # nunca (§18) y `sin ruta verificable` tampoco: recalcularla podría
    # contradecir al §20.5.
    habra_diferida = salida.admite_diferida

    # El acuse no se guarda cuando viene una respuesta detrás. No es una
    # respuesta: es la señal de que se está preparando, y el cliente ya la
    # muestra como estado. Guardarlo dejaba dos mensajes del asistente en el
    # hilo —"estoy consultando" y la respuesta— y al reabrir la conversación
    # aparecían los dos, como si el sistema hubiera contestado dos veces.
    if not habra_diferida:
        session.add(
            Message(
                conversation_id=conversacion.id,
                rol="assistant",
                contenido=salida.texto,
                urgencia=salida.urgencia,
                respuesta_plantilla_fija=salida.respuesta_plantilla_fija,
                modelo_usado=salida.modelo_usado,
                herramientas_invocadas=salida.herramientas_invocadas,
                fuentes_citadas=salida.fuentes_citadas,
                latencia_ms=salida.latencia_ms,
                enviado_at=datetime.now(UTC),
            )
        )
    auditar(
        session,
        request,
        actor=user,
        accion="chat.responder",
        entidad="conversation",
        entidad_id=str(conversacion.id),
        detalle={
            "urgencia": salida.urgencia.value,
            "plantilla_fija": salida.respuesta_plantilla_fija,
            "herramientas": [h.get("herramienta") for h in salida.herramientas_invocadas],
        },
    )

    # La conversación tiene que estar CONFIRMADA antes de encolar. La sesión se
    # cierra al terminar la petición, así que sin este commit el worker arranca
    # con la transacción todavía abierta, no encuentra el hilo y descarta la
    # tarea: medido en el servidor, la buscó 30 ms después de crearse y no
    # existía. El ciudadano se quedaba con el acuse para siempre.
    session.commit()

    diferida = False
    if habra_diferida:
        try:
            responder_diferido.apply_async(
                args=[
                    str(conversacion.id),
                    str(user.id) if user else None,
                    entrada.texto,
                    entrada.nivel_operacion.value,
                ],
                queue=salida.urgencia.value,
                priority=salida.urgencia.priority,
            )
            diferida = True
        except Exception as exc:  # noqa: BLE001
            # Sin broker el usuario se queda con el acuse, que ya es una
            # respuesta correcta y segura. No se propaga.
            import logging

            logging.getLogger(__name__).warning("No se pudo encolar la diferida: %s", exc)

            # Y entonces el acuse SÍ se guarda: es lo único que va a recibir.
            # Sin esto el hilo quedaría con la pregunta y ninguna respuesta.
            session.add(
                Message(
                    conversation_id=conversacion.id,
                    rol="assistant",
                    contenido=salida.texto,
                    urgencia=salida.urgencia,
                    respuesta_plantilla_fija=True,
                    latencia_ms=salida.latencia_ms,
                    enviado_at=datetime.now(UTC),
                )
            )
            session.commit()

    return MensajeSalida(
        texto=salida.texto,
        urgencia=salida.urgencia.value,
        respuesta_plantilla_fija=salida.respuesta_plantilla_fija,
        motivo_plantilla=salida.motivo_plantilla,
        fuentes=salida.fuentes_citadas,
        herramientas=salida.herramientas_invocadas,
        latencia_ms=salida.latencia_ms,
        modelo=salida.modelo_usado,
        conversation_id=str(conversacion.id),
        advertencias=salida.advertencias,
        respuesta_diferida_en_curso=diferida,
        sugerir_modo_ligero=salida.sugerir_modo_ligero,
        motivo_modo_ligero=salida.motivo_modo_ligero,
        ruta=salida.ruta,
        lugar=salida.lugar,
    )


class MensajeHistorial(BaseModel):
    rol: str
    contenido: str
    urgencia: str | None = None
    respuesta_plantilla_fija: bool = False
    fuentes: list[dict] = []
    enviado_at: str


@router.get("/{conversation_id}/mensajes", response_model=list[MensajeHistorial])
def mensajes(
    conversation_id: str,
    desde: str | None = None,
    session: Session = Depends(db),
    user: User | None = Depends(usuario_opcional),
) -> list[MensajeHistorial]:
    """Historial de la conversación, incluidas las respuestas diferidas (§29).

    El cliente llama aquí con `desde` = hora del último mensaje que ya tiene, y
    recoge lo que haya aparecido después. Es la otra mitad del acuse: sin este
    endpoint la respuesta diferida se calcularía y no la vería nadie.

    Se comprueba la propiedad de la conversación: un identificador es un UUID,
    pero adivinable o no, el historial de otra persona no se sirve (§28).
    """
    conversacion = session.get(Conversation, conversation_id)
    if conversacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación no encontrada")
    if conversacion.user_id is not None and (user is None or user.id != conversacion.user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esa conversación no es tuya")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversacion.id)
        .order_by(Message.enviado_at)
    )
    if desde:
        try:
            corte = datetime.fromisoformat(desde)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "`desde` debe ser una fecha ISO 8601"
            ) from exc
        stmt = stmt.where(Message.enviado_at > corte)

    return [
        MensajeHistorial(
            rol=m.rol,
            contenido=m.contenido,
            urgencia=m.urgencia.value if m.urgencia else None,
            respuesta_plantilla_fija=m.respuesta_plantilla_fija,
            fuentes=m.fuentes_citadas or [],
            enviado_at=m.enviado_at.isoformat(),
        )
        for m in session.scalars(stmt)
    ]
