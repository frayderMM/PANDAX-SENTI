"""Cola por prioridad, healthcheck de fuentes y borrados de retención.

§29: "Cola por prioridad: rojo > amarillo > verde." Las colas se
llaman igual que los niveles del §18 para que la correspondencia sea evidente
en `celery -Q`.

§11.3: healthcheck cada 15 minutos.
§13.5: `retention_jobs` ejecuta los borrados.
"""

from __future__ import annotations

import logging
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import delete, select, update
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.core.config import settings
from app.core.db import SessionLocal
from app.domain import ReportState

logger = logging.getLogger(__name__)

celery_app = Celery("senti", broker=settings.valkey_url, backend=settings.valkey_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Lima",
    enable_utc=True,
    task_default_queue="verde",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "healthcheck-fuentes": {
            "task": "app.tasks.celery_app.healthcheck_fuentes",
            "schedule": timedelta(minutes=settings.source_healthcheck_minutes),
            "options": {"queue": "verde"},
        },
        "sondeo-eventos-fuentes": {
            "task": "app.tasks.celery_app.sondear_eventos_fuentes",
            "schedule": timedelta(minutes=settings.citizen_source_poll_minutes),
            "options": {"queue": "verde"},
        },
        "retencion-datos": {
            "task": "app.tasks.celery_app.aplicar_retencion",
            # De madrugada: son borrados, no hay prisa y compiten menos por E/S.
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "verde"},
        },
        "reindexar-rag": {
            "task": "app.tasks.celery_app.reindexar_rag",
            "schedule": timedelta(minutes=20),
            "options": {"queue": "verde"},
        },
        "vencer-reportes": {
            "task": "app.tasks.celery_app.vencer_reportes",
            "schedule": timedelta(minutes=30),
            "options": {"queue": "verde"},
        },
    },
)


@celery_app.task(name="app.tasks.celery_app.healthcheck_fuentes")
def healthcheck_fuentes() -> dict:
    """§11.3, cada 15 minutos, por fuente."""
    from app.models import OfficialSource, SourceHealth
    from app.sources.health import comprobar

    ahora = datetime.now(UTC)
    resumen: dict[str, str] = {}

    with SessionLocal() as session:
        fuentes = list(
            session.scalars(
                select(OfficialSource).where(
                    OfficialSource.activa.is_(True),
                    OfficialSource.healthcheck_url.isnot(None),
                )
            )
        )
        def comprobar_fuente(fuente):
            return fuente, comprobar(
                fuente.healthcheck_url,
                schema_hash_previo=fuente.schema_hash,
                vigencia_horas=fuente.vigencia_horas,
                ahora=ahora,
            )

        with ThreadPoolExecutor(max_workers=max(1, min(8, len(fuentes)))) as pool:
            resultados = [pool.submit(comprobar_fuente, fuente) for fuente in fuentes]
            for futuro in as_completed(resultados):
                fuente, resultado = futuro.result()
                session.add(
                    SourceHealth(
                        source_id=fuente.id,
                        checked_at=ahora,
                        http_status=resultado.http_status,
                        latencia_ms=resultado.latencia_ms,
                        current_version=resultado.current_version,
                        feature_count=resultado.feature_count,
                        schema_hash=resultado.schema_hash,
                        status=resultado.status,
                        detalle=resultado.detalle,
                    )
                )
                fuente.ultimo_estado = resultado.status
                fuente.ultima_consulta_at = ahora
                # El hash solo se actualiza si la fuente respondió: guardar el hash
                # de una respuesta fallida haría que el próximo éxito pareciera un
                # cambio de esquema.
                if resultado.schema_hash:
                    fuente.schema_hash = resultado.schema_hash
                resumen[fuente.slug] = resultado.status.value
                logger.info("fuente=%s estado=%s", fuente.slug, resultado.status.value)

        session.commit()

    return resumen


def _external_value(attrs: dict, names: tuple[str, ...]) -> str | None:
    lowered = {str(k).lower(): v for k, v in attrs.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return str(value)
    return None


def _source_title(fuente, attrs: dict) -> str:
    """Construye un título factual antes de pedirle un resumen al 2B."""
    if "sismo" in fuente.slug:
        magnitud = _external_value(attrs, ("mag", "magnitud"))
        referencia = _external_value(attrs, ("ref", "referencia", "lugar", "ubicacion"))
        departamento = _external_value(attrs, ("departamento", "region"))
        partes = [f"Sismo de magnitud {magnitud}" if magnitud else "Sismo"]
        if referencia:
            partes.append(f"ubicado en {referencia}")
        if departamento and (not referencia or departamento.lower() not in referencia.lower()):
            partes.append(f"({departamento})")
        return " ".join(partes)[:400]
    if "indeci" in fuente.slug:
        fenomeno = _external_value(attrs, ("fenomeno", "st_temp"))
        detalle = _external_value(attrs, ("des_grupal_fenomeno", "descripcion"))
        distrito = _external_value(attrs, ("distrito",))
        departamento = _external_value(attrs, ("departamento",))
        partes = [p for p in (fenomeno, detalle) if p]
        ubicacion = ", ".join(p for p in (distrito, departamento) if p)
        if ubicacion:
            partes.append(ubicacion)
        return " - ".join(partes)[:400] or fuente.institucion
    if "senamhi-wis" in fuente.slug:
        estacion = _external_value(attrs, ("stationName", "station_name", "station", "wigos_station_identifier"))
        fenomeno = _external_value(attrs, ("phenomenonTime", "phenomenon_time", "datetime", "date"))
        variable = _external_value(attrs, ("name", "variable", "property")) or "observación"
        valor = _external_value(attrs, ("value", "result", "measurement"))
        unidades = _external_value(attrs, ("units", "unit", "uom"))
        variable_legible = {
            "precipitation": "precipitación",
            "precipitation_amount": "precipitación",
            "rainfall": "precipitación",
        }.get(variable.casefold(), variable.replace("_", " "))
        dato = f"{variable_legible} {valor}" if valor else variable_legible
        if unidades:
            dato += f" {unidades}"
        partes = ["Precipitación SENAMHI", dato]
        if estacion:
            partes.append(f"en {estacion}")
        if fenomeno:
            partes.append(f"({fenomeno})")
        return " ".join(partes)[:400]
    return (
        _external_value(attrs, ("titulo", "title", "nombre", "name", "descripcion", "description"))
        or fuente.institucion
    )[:400]


def _external_datetime(value: str | None) -> datetime | None:
    """Acepta ISO-8601 y timestamps Unix en segundos o milisegundos."""
    if not value:
        return None
    if "/" in value:
        value = value.split("/", 1)[0]
    try:
        number = float(value)
        if number > 100_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None


def _hazard_for_source(slug: str):
    from app.domain import HazardType
    if "sismo" in slug:
        return HazardType.SISMO
    if "ingemmet" in slug:
        return HazardType.DESLIZAMIENTO
    return HazardType.OTRO


def _classify_hazard(fuente, titulo: str):
    """Clasifica con vocabulario controlado; el 2B no decide el tipo."""
    from app.domain import HazardType
    texto = titulo.casefold()
    if "sismo" in texto or "terremoto" in texto:
        return HazardType.SISMO
    if "tsunami" in texto or "maremoto" in texto:
        return HazardType.TSUNAMI
    if "huaico" in texto or "huayco" in texto:
        return HazardType.HUAICO
    if "deslizamiento" in texto or "derrumbe" in texto or "alud" in texto:
        return HazardType.DESLIZAMIENTO
    if "inund" in texto or "desborde" in texto:
        return HazardType.INUNDACION
    if "lluvia" in texto or "precipit" in texto:
        return HazardType.LLUVIA
    if "incendio" in texto:
        return HazardType.INCENDIO
    if "puente" in texto:
        return HazardType.PUENTE_AFECTADO
    if "vía" in texto or "via " in texto or "carretera" in texto:
        return HazardType.VIA_BLOQUEADA
    return _hazard_for_source(fuente.slug)


def _source_items(fuente, ahora: datetime) -> list[dict]:
    """Obtiene observaciones estructuradas, sin scraping libre."""
    import httpx
    if "/oapi/collections/" in fuente.url:
        inicio = (ahora - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
        fin = ahora.isoformat().replace("+00:00", "Z")
        params = {"f": "json", "datetime": f"{inicio}/{fin}", "limit": "100"}
        response = httpx.get(fuente.url, params=params, timeout=30.0)
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features", [])
        ogc = True
    elif "/OGCFeatureServer/collections/" in fuente.url:
        params = {"f": "json", "limit": "10"}
        response = httpx.get(fuente.url, params=params, timeout=30.0)
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features", [])
        ogc = True
    elif "/query" in fuente.url:
        params = {"where": "1=1", "outFields": "*", "returnGeometry": "true", "f": "json", "resultRecordCount": "10", "orderByFields": "OBJECTID DESC"}
        response = httpx.get(fuente.url, params=params, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features", [])
        ogc = False
    else:
        # También se consulta la página oficial en paralelo. Sin un feed
        # estructurado no se crea un evento: faltan coordenadas y fecha fiable.
        response = httpx.get(
            fuente.url,
            headers={"User-Agent": "SENTI/0.1 (gestion de emergencias)"},
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        return []
    resultado = []
    for feature in features:
        attrs = feature.get("properties") if ogc else feature.get("attributes")
        attrs = attrs or {}
        if "senamhi-wis" in fuente.slug:
            variable = _external_value(attrs, ("name", "variable", "property")) or ""
            if "precip" not in variable.casefold() and "rain" not in variable.casefold():
                continue
            valor = _external_value(attrs, ("value", "result", "measurement"))
            try:
                if valor is None or float(valor) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
        geometry = feature.get("geometry") or {}
        if ogc:
            coordinates = geometry.get("coordinates") or []
            geometry = {"x": coordinates[0] if len(coordinates) > 0 else None, "y": coordinates[1] if len(coordinates) > 1 else None}
        direccion = _external_value(attrs, ("direccion", "address", "ubicacion", "lugar", "localidad", "distrito", "zona"))
        try:
            lon = float(geometry.get("x") or geometry.get("longitude"))
            lat = float(geometry.get("y") or geometry.get("latitude"))
        except (TypeError, ValueError):
            if not direccion:
                continue
            try:
                geocode = httpx.get(
                    f"{settings.nominatim_url.rstrip('/')}/search",
                    params={"q": direccion, "format": "jsonv2", "limit": 1, "countrycodes": "pe"},
                    headers={"User-Agent": "SENTI/1.0 contacto@senti.pe"},
                    timeout=8.0,
                )
                geocode.raise_for_status()
                geocoded = geocode.json()
                if not geocoded:
                    continue
                lat, lon = float(geocoded[0]["lat"]), float(geocoded[0]["lon"])
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                continue
        titulo = _source_title(fuente, attrs)
        fecha = _external_value(
            attrs,
            (
                "fechaevento", "fecha_hora", "datetime", "eventdate", "fecha", "date",
                "phenomenonTime", "phenomenon_time", "resultTime", "result_time",
            ),
        )
        publicado_at = _external_datetime(fecha)
        if publicado_at and fuente.vigencia_horas and publicado_at < ahora - timedelta(hours=fuente.vigencia_horas):
            continue
        clave = _external_value(attrs, ("ide_sinpad", "id", "objectid", "codigo", "code")) or f"{lat:.5f}:{lon:.5f}:{fecha}:{titulo}"
        resultado.append({"key": clave, "title": titulo[:400], "date": fecha or ahora.isoformat(), "published_at": publicado_at, "lat": lat, "lon": lon, "address": direccion})
    return resultado


def _resumir_fuente(titulo: str) -> str:
    """Gemma 2B redacta un resumen corto; la fuente y los hechos ya están fijados."""
    import httpx
    try:
        response = httpx.post(
            f"{settings.citizen_llm_base_url.rstrip('/')}/chat/completions",
            json={"model": settings.citizen_llm_model,
                  "messages": [{"role": "user", "content": f"Resume en una frase neutral este aviso: {titulo}"}],
                  "max_tokens": 60, "temperature": 0},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()[:1000] or titulo
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemma 2B no disponible para resumen: %s", exc)
        return titulo


@celery_app.task(name="app.tasks.celery_app.sondear_eventos_fuentes")
def sondear_eventos_fuentes() -> dict:
    """Consulta fuentes confiables cada 10 min e ingresa observaciones idempotentes.

    Las fuentes no crean personas ni reportes ciudadanos: solo agregan evidencia
    externa o crean un evento con cero reporteros. Gemma 2B es opcional y solo
    resume el título; nunca decide tipo, coordenadas ni validación.
    """
    from app.models import EmergencyEvent, EventSource, OfficialSource
    from app.services.event_grouping import text_similarity
    from geoalchemy2 import Geography
    from sqlalchemy import cast, func

    ahora = datetime.now(UTC)
    creados = asociados = omitidos = 0
    geog = Geography(srid=4326)
    with SessionLocal() as session:
        fuentes = list(session.scalars(select(OfficialSource).where(OfficialSource.activa.is_(True), OfficialSource.verificada.is_(True))))

        def consultar_fuente(fuente):
            return fuente, _source_items(fuente, ahora)

        consultas = {}
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(fuentes)))) as pool:
            futuros = {pool.submit(consultar_fuente, fuente): fuente for fuente in fuentes}
            for futuro in as_completed(futuros):
                fuente = futuros[futuro]
                try:
                    consultas[fuente.slug] = futuro.result()[1]
                except Exception as exc:  # noqa: BLE001
                    logger.warning("sondeo fuente falló slug=%s error=%s", fuente.slug, exc)
                    consultas[fuente.slug] = []

        for fuente in fuentes:
            for item in consultas.get(fuente.slug, []):
                tipo = _classify_hazard(fuente, item["title"])
                fingerprint = hashlib.sha256(f"{fuente.slug}|{item['key']}".encode()).hexdigest()
                if session.scalar(select(EventSource.id).where(EventSource.fingerprint == fingerprint)):
                    omitidos += 1
                    continue
                punto = func.ST_SetSRID(func.ST_MakePoint(item["lon"], item["lat"]), 4326)
                candidatos = session.scalars(select(EmergencyEvent).where(
                    EmergencyEvent.tipo == tipo,
                    EmergencyEvent.last_reported_at >= ahora - timedelta(hours=settings.citizen_report_group_time_hours),
                    func.ST_DWithin(EmergencyEvent.geom.cast(geog), cast(punto, geog), settings.citizen_report_group_radius_meters),
                )).all()
                evento = next((e for e in candidatos if text_similarity(e.resumen, item["title"]) >= settings.citizen_report_min_text_similarity), None)
                if evento is None:
                    resumen = _resumir_fuente(item["title"])
                    evento = EmergencyEvent(tipo=tipo, titulo=item["title"], resumen=resumen, geom=from_shape(Point(item["lon"], item["lat"]), srid=4326),
                                             first_reported_at=ahora, last_reported_at=ahora, confianza=0.0, estado_validacion="SIN_CONFIRMAR")
                    session.add(evento)
                    session.flush()
                    creados += 1
                else:
                    asociados += 1
                    evento.last_reported_at = max(evento.last_reported_at or ahora, ahora)
                session.add(EventSource(event_id=evento.id, source_id=fuente.id, name=fuente.institucion,
                                        source_type=fuente.kind.value, title=item["title"], published_at=item["published_at"] or ahora,
                                        url=fuente.url, summary=evento.resumen or item["title"], is_official=True, fingerprint=fingerprint))
        session.commit()
    return {"created_events": creados, "associated_sources": asociados, "deduplicated": omitidos}


@celery_app.task(name="app.tasks.celery_app.aplicar_retencion")
def aplicar_retencion() -> dict:
    """§13.5. Ejecuta los borrados y deja constancia en `retention_jobs`.

    Un borrado sin registro no se puede demostrar ante la ANPD, y el
    DS 016-2024-JUS exige medidas de seguridad demostrables (§13.1).
    """
    from app.models import AuditLog, CitizenReport, Conversation, Incident, RetentionJob
    from app.rules.retention import PLAZOS, RetentionPolicy

    ahora = datetime.now(UTC)
    resultados: dict[str, int] = {}

    with SessionLocal() as session:
        # Ubicación exacta: 72 h. Se borra la geometría, no la fila: el
        # incidente sigue existiendo con su distrito, que vive 12 meses.
        n = session.execute(
            update(Incident)
            .where(
                Incident.ubicacion_exacta.isnot(None),
                Incident.ubicacion_exacta_expira_at <= ahora,
            )
            .values(ubicacion_exacta=None, ubicacion_exacta_expira_at=None)
        ).rowcount
        resultados["ubicacion_exacta"] = n

        n = session.execute(
            update(Incident)
            .where(Incident.distrito.isnot(None), Incident.distrito_expira_at <= ahora)
            .values(distrito=None, distrito_expira_at=None)
        ).rowcount
        resultados["ubicacion_distrito"] = n

        n = session.execute(
            update(CitizenReport)
            .where(CitizenReport.foto_url.isnot(None), CitizenReport.foto_expira_at <= ahora)
            .values(foto_url=None, foto_expira_at=None)
        ).rowcount
        resultados["fotografias"] = n

        # §13.5: la ubicación exacta dura 72 h, y la conversación 12 meses. Se
        # borra el punto sin borrar el hilo: son dos plazos distintos y el más
        # corto manda sobre lo suyo. Sin esto, una coordenada exacta viviría un
        # año dentro de la conversación, que es justo lo que el plazo evita.
        n = session.execute(
            update(Conversation)
            .where(
                Conversation.ubicacion_at.isnot(None),
                Conversation.ubicacion_at <= ahora - PLAZOS[RetentionPolicy.UBICACION_EXACTA],
            )
            .values(ultima_lat=None, ultima_lon=None, ubicacion_at=None)
        ).rowcount
        resultados["ubicacion_exacta"] = n

        n = session.execute(
            delete(Conversation).where(
                Conversation.expira_at.isnot(None), Conversation.expira_at <= ahora
            )
        ).rowcount
        resultados["conversaciones"] = n

        n = session.execute(
            delete(AuditLog).where(AuditLog.expira_at.isnot(None), AuditLog.expira_at <= ahora)
        ).rowcount
        resultados["auditoria"] = n

        for politica, filas in resultados.items():
            session.add(
                RetentionJob(
                    politica=politica, ejecutado_at=ahora, filas_afectadas=filas, exito=True
                )
            )
        session.commit()

    logger.info("retención aplicada: %s", resultados)
    return resultados


@celery_app.task(name="app.tasks.celery_app.vencer_reportes")
def vencer_reportes() -> int:
    """§21.1: cualquier estado pasa a DESACTUALIZADO por vencimiento.

    §20.3: un reporte vencido no penaliza ni tranquiliza. El puntaje ya lo
    trata como peso 0 por el decaimiento temporal; marcarlo aquí es lo que lo
    saca de la vista del validador y del mapa.
    """
    from app.models import CitizenReport

    ahora = datetime.now(UTC)
    with SessionLocal() as session:
        n = session.execute(
            update(CitizenReport)
            .where(
                CitizenReport.vence_at.isnot(None),
                CitizenReport.vence_at <= ahora,
                CitizenReport.estado.notin_(
                    [ReportState.RESUELTO, ReportState.DESACTUALIZADO,
                     ReportState.RECHAZADO, ReportState.DUPLICADO]
                ),
            )
            .values(estado=ReportState.DESACTUALIZADO)
        ).rowcount
        session.commit()
    logger.info("reportes vencidos: %d", n)
    return n


@celery_app.task(name="app.tasks.celery_app.reindexar_rag")
def reindexar_rag() -> int:
    """Completa los embeddings pendientes del RAG (§19).

    `ingerir` no aborta cuando el servidor de embeddings está caído: indexa
    solo el texto, porque un documento buscable por palabras es mejor que un
    documento perdido. Esta tarea es la que lo termina después; sin ella, esos
    fragmentos quedarían invisibles para la búsqueda semántica para siempre.
    """
    from app.llm import LLMUnavailable
    from app.rag import reindexar_pendientes

    with SessionLocal() as session:
        try:
            n = reindexar_pendientes(session)
        except LLMUnavailable as exc:
            logger.warning("Embeddings aún no disponibles: %s", exc)
            return 0
        session.commit()
    return n


@celery_app.task(name="app.tasks.celery_app.atender_whatsapp", bind=True, max_retries=2)
def atender_whatsapp(
    self, remitente: str, texto: str, lat: float | None = None, lon: float | None = None
) -> str | None:
    """§10.1: atiende un mensaje de WhatsApp de punta a punta.

    Va en el worker y no en el webhook porque una respuesta puede tardar
    decenas de segundos y Evolution reintenta si el webhook no contesta ya.

    El teléfono **nunca se guarda en claro** (§13.5): la conversación se busca
    y se crea por seudónimo. El número en claro vive solo en memoria, el tiempo
    de contestar.
    """
    from datetime import UTC

    from app.channels import WhatsAppError, WhatsAppNoConfigurado, enviar_texto
    from app.core.crypto import pseudonymize_phone
    from app.domain import Channel, OperationLevel
    from app.models import Conversation, Message, User
    from app.orchestrator import EntradaUsuario, Orchestrator, ToolContext
    from app.rules import fixed_responses as fx
    from app.rules.retention import PLAZOS, RetentionPolicy, expira_en

    seudonimo = pseudonymize_phone(remitente)
    ahora = datetime.now(UTC)

    with SessionLocal() as session:
        conversacion = session.scalar(
            select(Conversation)
            .where(
                Conversation.phone_pseudonym == seudonimo,
                Conversation.canal == Channel.WHATSAPP,
                Conversation.activa.is_(True),
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )

        # §13.4: primer contacto. Se pide consentimiento y no se procesa nada
        # más hasta que llegue. Contestar antes sería tratar un mensaje sin
        # base para hacerlo.
        if conversacion is None:
            conversacion = Conversation(
                canal=Channel.WHATSAPP,
                phone_pseudonym=seudonimo,
                expira_at=expira_en(RetentionPolicy.MENSAJES, ahora),
            )
            session.add(conversacion)
            session.commit()
            _enviar_o_registrar(remitente, fx.CONSENTIMIENTO_WHATSAPP)
            return fx.CONSENTIMIENTO_WHATSAPP

        if not conversacion.ventana_abierta(ahora):
            # Cada mensaje del ciudadano reabre la ventana de 24 h (§10.1).
            conversacion.ventana_servicio_hasta = ahora + timedelta(hours=24)

        # Mientras no acepte, solo se responde el consentimiento. "ACEPTO" es
        # el literal del §13.4 y se compara sin tildes ni mayúsculas.
        if conversacion.consentimiento_at is None:
            if texto.strip().upper().startswith("ACEPTO"):
                conversacion.consentimiento_at = ahora
                conversacion.consentimiento_version = fx.CONSENTIMIENTO_VERSION
                session.commit()
            else:
                session.commit()
                _enviar_o_registrar(remitente, fx.CONSENTIMIENTO_WHATSAPP)
                return fx.CONSENTIMIENTO_WHATSAPP

        # §6: el rol sale de la cuenta, no del canal. Si el número está
        # registrado, quien escribe por WhatsApp tiene sus herramientas; si no,
        # entra como invitado y recibe información general (§13.4). Se busca
        # por seudónimo porque el número en claro no está en la base.
        usuario = session.scalar(select(User).where(User.phone_pseudonym == seudonimo))
        if usuario is not None and conversacion.user_id is None:
            conversacion.user_id = usuario.id

        # En WhatsApp la ubicación y la pregunta son mensajes distintos: se
        # comparte el punto y después se escribe "¿por dónde salgo?". Sin
        # recordarla, la pregunta llega sin coordenadas y el sistema vuelve a
        # pedir lo que le acaban de dar.
        if lat is not None and lon is not None:
            conversacion.ultima_lat = lat
            conversacion.ultima_lon = lon
            conversacion.ubicacion_at = ahora
        elif (
            conversacion.ubicacion_at is not None
            and ahora - conversacion.ubicacion_at <= PLAZOS[RetentionPolicy.UBICACION_EXACTA]
        ):
            # §13.5: 72 h. Pasado ese plazo no se reutiliza, y no solo por la
            # retención: dónde estaba alguien hace tres días no dice dónde está
            # ahora, y una ruta calculada desde ahí lo manda al sitio
            # equivocado.
            lat, lon = conversacion.ultima_lat, conversacion.ultima_lon

        # El mismo hilo, la misma memoria que en la app: quien escribe por
        # WhatsApp también espera que el asistente recuerde lo que acaba de
        # decirle. Solo de esta conversación (§13.5).
        historial = [
            (m.rol, m.contenido)
            for m in reversed(
                list(
                    session.scalars(
                        select(Message)
                        .where(Message.conversation_id == conversacion.id)
                        .order_by(Message.enviado_at.desc())
                        .limit(12)
                    )
                )
            )
        ]

        ctx = ToolContext(session=session, user=usuario, ahora=ahora)
        salida = Orchestrator(ctx, profundidad_cola=0, modo_diferido=True).responder(
            EntradaUsuario(
                texto=texto or "Comparto mi ubicación.",
                canal=Channel.WHATSAPP,
                lat=lat,
                lon=lon,
                nivel_operacion=OperationLevel(conversacion.nivel_operacion),
                historial=historial,
            )
        )

        session.add(
            Message(
                conversation_id=conversacion.id,
                rol="user",
                contenido=texto,
                urgencia=salida.urgencia,
                enviado_at=ahora,
            )
        )
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
        session.commit()

    try:
        enviar_texto(remitente, salida.texto)
    except (WhatsAppError, WhatsAppNoConfigurado) as exc:
        # La respuesta ya está guardada: se reintenta el envío, no el cálculo.
        logger.warning("No se pudo entregar por WhatsApp: %s", exc)
        raise self.retry(exc=exc, countdown=20) from exc

    return salida.texto


def _enviar_o_registrar(remitente: str, texto: str) -> None:
    """Entrega sin reintentar. Se usa para el consentimiento, que se repite
    solo con que el ciudadano vuelva a escribir."""
    from app.channels import WhatsAppError, WhatsAppNoConfigurado, enviar_texto

    try:
        enviar_texto(remitente, texto)
    except (WhatsAppError, WhatsAppNoConfigurado) as exc:
        logger.warning("No se pudo entregar por WhatsApp: %s", exc)


@celery_app.task(name="app.tasks.celery_app.responder_diferido", bind=True, max_retries=2)
def responder_diferido(
    self, conversation_id: str, user_id: str | None, texto: str, nivel_operacion: str
) -> str | None:
    """§29: la respuesta diferida que sigue al acuse.

    Amarillo y verde reciben acuse inmediato y respuesta diferida. El acuse ya
    lo devuelve el orquestador; esta tarea es la otra mitad, la que de verdad
    consulta y redacta, y guarda el resultado como un mensaje más de la
    conversación para que el cliente lo recoja.

    Corre con `profundidad_cola=0` a propósito: quien mide la cola es la API
    para decidir si degrada. El worker ya ES la cola, y volver a degradar aquí
    dejaría la respuesta diferida sin calcular nunca.
    """
    from datetime import UTC

    from app.domain import OperationLevel
    from app.models import Conversation, Message, User
    from app.orchestrator import EntradaUsuario, Orchestrator, ToolContext

    with SessionLocal() as session:
        conversacion = session.get(Conversation, conversation_id)
        if conversacion is None:
            logger.warning("Conversación %s ya no existe", conversation_id)
            return None

        usuario = session.get(User, user_id) if user_id else None
        ahora = datetime.now(UTC)
        ctx = ToolContext(session=session, user=usuario, ahora=ahora)

        salida = Orchestrator(ctx, profundidad_cola=0, modo_diferido=True).responder(
            EntradaUsuario(
                texto=texto,
                canal=conversacion.canal,
                nivel_operacion=OperationLevel(nivel_operacion),
                historial=[
                    (m.rol, m.contenido)
                    for m in reversed(
                        list(
                            session.scalars(
                                select(Message)
                                .where(Message.conversation_id == conversacion.id)
                                .order_by(Message.enviado_at.desc())
                                .limit(12)
                            )
                        )
                    )
                ],
            )
        )

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
        session.commit()
        logger.info("Respuesta diferida lista para %s", conversation_id)
        return salida.texto


def _mensaje_alerta(alerta, distrito: str) -> str:
    """Texto completo para WhatsApp (§7.3): fuente y hora dentro del mensaje,
    sin depender de que alguien abra un enlace o una app."""
    lineas = [
        f"ALERTA {alerta.nivel_oficial.upper()} — {distrito}",
        alerta.titulo,
    ]
    if alerta.resumen_modelo:
        lineas.append("")
        lineas.append(alerta.resumen_modelo)
    if alerta.recomendaciones_oficiales:
        lineas.append("")
        lineas.append("Recomendaciones:")
        lineas.extend(f"- {r}" for r in alerta.recomendaciones_oficiales)
    lineas.append("")
    hora = alerta.vigencia_inicio or alerta.created_at
    lineas.append(f"Fuente: {alerta.entidad_emisora} · {hora.strftime('%d/%m %H:%M')}")
    lineas.append(
        "SENTI no reemplaza al canal oficial del Estado. El canal de alerta "
        "masiva del Perú es SISMATE (MTC e INDECI)."
    )
    return "\n".join(lineas)


@celery_app.task(name="app.tasks.celery_app.enviar_alerta_whatsapp", bind=True, max_retries=2)
def enviar_alerta_whatsapp(self, alert_id: str) -> dict:
    """Difunde una alerta ya publicada a quien dio consentimiento en su distrito.

    Esta tarea no decide nada (§15, §6): solo entrega algo que un operador ya
    confirmó en `POST /municipal/alertas`. Si WhatsApp no está configurado, se
    registra y se corta ahí — no tiene sentido reintentar algo que no va a
    empezar a estar configurado entre un reintento y el siguiente.
    """
    from app.channels import WhatsAppError, WhatsAppNoConfigurado, enviar_texto
    from app.models import Alert, AlertSubscriber

    with SessionLocal() as session:
        alerta = session.get(Alert, alert_id)
        if alerta is None:
            logger.warning("alerta %s ya no existe, no se difunde", alert_id)
            return {"enviados": 0, "fallidos": 0, "motivo": "alerta no encontrada"}

        distritos = sorted({z.distrito for z in alerta.zones if z.distrito})
        if not distritos:
            logger.warning("alerta %s no tiene distrito asociado, no se difunde", alert_id)
            return {"enviados": 0, "fallidos": 0, "motivo": "sin distrito"}

        suscriptores = list(
            session.scalars(
                select(AlertSubscriber).where(
                    AlertSubscriber.activo.is_(True),
                    AlertSubscriber.distrito.in_(distritos),
                )
            )
        )

        if not suscriptores:
            return {"enviados": 0, "fallidos": 0, "motivo": "sin suscriptores en el distrito"}

        mensaje = _mensaje_alerta(alerta, distritos[0])

        enviados = 0
        fallidos = 0
        for suscriptor in suscriptores:
            try:
                enviar_texto(suscriptor.telefono, mensaje)
                enviados += 1
            except WhatsAppNoConfigurado as exc:
                logger.warning(
                    "WhatsApp no configurado; no se difunde la alerta %s: %s", alert_id, exc
                )
                return {"enviados": 0, "fallidos": 0, "motivo": "whatsapp no configurado"}
            except WhatsAppError as exc:
                logger.warning(
                    "no se pudo entregar la alerta %s a un suscriptor: %s", alert_id, exc
                )
                fallidos += 1

        logger.info(
            "alerta %s difundida: %d enviados, %d fallidos de %d suscriptores",
            alert_id, enviados, fallidos, len(suscriptores),
        )
        return {"enviados": enviados, "fallidos": fallidos}
