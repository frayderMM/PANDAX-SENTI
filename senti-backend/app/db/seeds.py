"""Datos de arranque y escenario de demostración (§34).

`sembrar_base` carga lo que el sistema necesita para funcionar: catálogo de
fuentes del §11.1, teléfonos del §24.3, protocolos del §17 y los parámetros de
riesgo del §20.3 como versión v1.

`sembrar_demo` carga el escenario del §34.1: Rosa vive en Lurigancho-Chosica
con su madre adulta mayor, con movilidad reducida, y una mascota. Hay alerta
por lluvias intensas y una avenida con reporte de inundación.

Los datos de demostración están geográficamente en Chosica de verdad: usar
coordenadas inventadas haría que Valhalla no encontrara ninguna vía y el
escenario no probaría nada.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import content_hash
from app.core.security import Role, hash_password
from app.domain import (
    ConfidenceLevel,
    ConsentPurpose,
    HazardType,
    ReportState,
    SourceStatus,
    TrustLevel,
)
from app.models import (
    Alert,
    AlertZone,
    CitizenReport,
    Consent,
    EmergencyPhone,
    Hazard,
    HouseholdProfile,
    OfficialSource,
    Protocol,
    Resource,
    RiskParameters,
    User,
)
from app.models.base import SRID
from app.rules import phones as phones_rules
from app.rules.scoring import PESOS
from app.sources.registry import CATALOGO

logger = logging.getLogger(__name__)

# Lurigancho-Chosica, distrito piloto del §34.
CHOSICA_LAT, CHOSICA_LON = -11.9404, -76.7006


def sembrar_base(session: Session) -> None:
    _sembrar_fuentes(session)
    _sembrar_telefonos(session)
    _sembrar_protocolos(session)
    _sembrar_parametros(session)
    _sembrar_rag(session)


def _sembrar_fuentes(session: Session) -> None:
    """§11.1, catálogo literal, con su estado real de verificación."""
    for definicion in CATALOGO:
        if session.scalar(select(OfficialSource).where(OfficialSource.slug == definicion.slug)):
            continue
        session.add(
            OfficialSource(
                slug=definicion.slug,
                institucion=definicion.institucion,
                descripcion=definicion.descripcion,
                url=definicion.url,
                healthcheck_url=definicion.healthcheck_url,
                kind=definicion.kind,
                ambito_geografico=definicion.ambito_geografico,
                tipo_informacion=definicion.tipo_informacion,
                verificada=definicion.verificada,
                activa=True,
                vigencia_horas=definicion.vigencia_horas,
                # Nunca se siembra como `ok`: eso lo decide el healthcheck del
                # §11.3, no el seed. Declarar `ok` sin haber consultado sería
                # exactamente la afirmación sin respaldo que el §32.2 prohíbe.
                ultimo_estado=SourceStatus.CAIDO,
            )
        )
    logger.info("Fuentes del catálogo: %d", len(CATALOGO))


def _sembrar_telefonos(session: Session) -> None:
    """§24.3: configurable por región, no texto fijo en el código."""
    for region, contactos in phones_rules.POR_REGION.items():
        for c in contactos:
            existe = session.scalar(
                select(EmergencyPhone).where(
                    EmergencyPhone.region == region, EmergencyPhone.numero == c.numero
                )
            )
            if existe:
                continue
            session.add(
                EmergencyPhone(
                    region=region,
                    situacion=c.situacion,
                    numero=c.numero,
                    entidad=c.entidad,
                    orden=c.orden,
                    activo=True,
                )
            )


def _sembrar_protocolos(session: Session) -> None:
    """§17: las acciones críticas provienen de protocolos del administrador.

    El checklist del §17 va aquí literal. Las acciones con `condicion_hogar`
    solo aparecen para los hogares que las necesitan (§14).
    """
    if session.scalar(select(Protocol).where(Protocol.codigo == "INUNDACION-2H")):
        return

    session.add(
        Protocol(
            codigo="INUNDACION-2H",
            titulo="Plan para las próximas dos horas ante lluvias e inundación",
            hazard_type=HazardType.INUNDACION.value,
            entidad="INDECI",
            version="1.0",
            activo=True,
            acciones=[
                {"texto": "Guardar documentos en una bolsa impermeable",
                 "prioridad": 1, "critica": True},
                {"texto": "Preparar medicamentos habituales", "prioridad": 2, "critica": True,
                 "condicion_hogar": {"medicamentos_habituales": True}},
                {"texto": "Cargar los celulares", "prioridad": 3, "critica": True},
                {"texto": "Confirmar el punto de reunión", "prioridad": 4, "critica": True},
                {"texto": "Preparar agua y alimento para la mascota",
                 "prioridad": 5, "critica": False, "condicion_hogar": {"mascotas": 1}},
                {"texto": "Descargar la ruta de menor riesgo", "prioridad": 6, "critica": True},
                {"texto": "Ubicar la silla de ruedas o el apoyo de marcha junto a la salida",
                 "prioridad": 2, "critica": True,
                 "condicion_hogar": {"movilidad_reducida": True}},
                {"texto": "Acordar quién acompaña a la persona adulta mayor",
                 "prioridad": 3, "critica": True, "condicion_hogar": {"adultos_mayores": 1}},
            ],
        )
    )

    session.add(
        Protocol(
            codigo="HUAICO-2H",
            titulo="Plan ante activación de quebrada o huaico",
            hazard_type=HazardType.HUAICO.value,
            entidad="INDECI",
            version="1.0",
            activo=True,
            acciones=[
                {"texto": "Aléjate del cauce de la quebrada, hacia terreno alto",
                 "prioridad": 1, "critica": True},
                {"texto": "No intentes cruzar el material del huaico",
                 "prioridad": 2, "critica": True},
                {"texto": "Guardar documentos y medicinas", "prioridad": 3, "critica": True},
                {"texto": "Confirmar el punto de reunión", "prioridad": 4, "critica": True},
            ],
        )
    )


def _sembrar_parametros(session: Session) -> None:
    """§20.3 y §23: los parámetros vigentes, versionados desde el primer día."""
    if session.scalar(select(RiskParameters).where(RiskParameters.version == "v1")):
        return
    session.add(
        RiskParameters(
            version="v1",
            activo=True,
            pesos=dict(PESOS),
            riesgos={
                "cierre_vigente": 1.00,
                "zona_peligro_alto": 0.70,
                "reporte_validado": 0.55,
                "reporte_probable": 0.40,
                "reporte_pendiente": 0.15,
                "sin_senal": 0.00,
            },
            vigencias_horas={
                "inundacion": 12, "huaico": 24, "deslizamiento": 48, "lluvia": 6,
                "sismo": 6, "tsunami": 6, "incendio": 12, "via_bloqueada": 24,
                "puente_afectado": 168, "acumulacion_agua": 8, "caida_poste": 24, "otro": 12,
            },
            # §20.4: medición por distrito. Estos valores son los del piloto y
            # deben re-medirse sobre la cartografía real antes de abrir a
            # público; un distrito sin entrada aquí se trata como cobertura
            # insuficiente, que es el lado seguro.
            umbrales_cobertura={
                "Lurigancho-Chosica": {
                    "densidad_vias_km2": 3.2,
                    "pct_vias_etiquetadas": 0.64,
                    "tiene_elevacion": True,
                }
            },
            nota="Parámetros de arranque, tomados literalmente del §20.3.",
        )
    )


# ── Escenario del §34 ──────────────────────────────────────────────────────
def sembrar_demo(session: Session) -> None:
    ahora = datetime.now(UTC)

    rosa = session.scalar(select(User).where(User.email == "rosa@demo.senti.pe"))
    if rosa is None:
        rosa = User(
            email="rosa@demo.senti.pe",
            password_hash=hash_password("demo-senti-2026"),
            display_name="Rosa",
            role=Role.CIUDADANO,
            municipality="Lurigancho-Chosica",
        )
        session.add(rosa)
        session.flush()

        # §13.4: el perfil sensible exige consentimiento por finalidad.
        for purpose in (ConsentPurpose.MENSAJES, ConsentPurpose.PERFIL_HOGAR,
                        ConsentPurpose.UBICACION_EXACTA):
            session.add(
                Consent(
                    user_id=rosa.id, purpose=purpose, granted=True, granted_at=ahora,
                    notice_version="1.0", notice_text="Consentimiento de demostración",
                )
            )

        # §34.1: madre adulta mayor con movilidad reducida y una mascota.
        session.add(
            HouseholdProfile(
                user_id=rosa.id,
                distrito="Lurigancho-Chosica",
                zona_aproximada="sector 4",
                integrantes=2,
                ninos=0,
                adultos_mayores=1,
                movilidad_reducida=True,
                mascotas=1,
                vehiculo=False,
                medicamentos_habituales=True,
                punto_reunion_configurado=False,
            )
        )

    validador = session.scalar(select(User).where(User.email == "validador@demo.senti.pe"))
    if validador is None:
        validador = User(
            email="validador@demo.senti.pe", password_hash=hash_password("demo-senti-2026"),
            display_name="Validador comunitario", role=Role.VALIDADOR,
            municipality="Lurigancho-Chosica",
        )
        session.add(validador)

    operador = session.scalar(select(User).where(User.email == "operador@demo.senti.pe"))
    if operador is None:
        operador = User(
            email="operador@demo.senti.pe", password_hash=hash_password("demo-senti-2026"),
            display_name="Operador municipal", role=Role.OPERADOR_MUNICIPAL,
            municipality="Lurigancho-Chosica",
        )
        session.add(operador)

    admin = session.scalar(select(User).where(User.email == "admin@demo.senti.pe"))
    if admin is None:
        session.add(
            User(email="admin@demo.senti.pe", password_hash=hash_password("demo-senti-2026"),
                 display_name="Administrador", role=Role.ADMINISTRADOR)
        )

    session.flush()

    # §34.2 paso 2: alerta por lluvias intensas que incluye su zona.
    if not session.scalar(select(Alert).where(Alert.titulo.contains("DEMOSTRACIÓN"))):
        cuerpo = b"Aviso meteorologico de demostracion - lluvias intensas Lurigancho-Chosica"
        alerta = Alert(
            tipo_evento=HazardType.LLUVIA,
            titulo="DEMOSTRACIÓN — Aviso por lluvias intensas en la cuenca del Rímac",
            nivel_oficial="Naranja",
            entidad_emisora="SENAMHI",
            confianza=ConfidenceLevel.OFICIAL,
            url_origen="https://www.senamhi.gob.pe/?p=aviso-meteorologico",
            sha256_origen=content_hash(cuerpo),
            vigencia_inicio=ahora - timedelta(hours=1),
            vigencia_fin=ahora + timedelta(hours=18),
            vigente=True,
            recomendaciones_oficiales=[
                "Evite transitar por quebradas y cauces secos.",
                "Asegure techos y elementos sueltos.",
                "Mantenga a mano documentos y medicinas.",
            ],
            actualizado_en_origen=ahora - timedelta(minutes=25),
        )
        session.add(alerta)
        session.flush()

        # Polígono aproximado del sector piloto, para que el cruce PostGIS del
        # §15 devuelva algo real.
        d = 0.03
        session.add(
            AlertZone(
                alert_id=alerta.id,
                nombre="Lurigancho-Chosica, sector 4",
                distrito="Lurigancho-Chosica",
                provincia="Lima",
                departamento="Lima",
                geom=from_shape(
                    Polygon([
                        (CHOSICA_LON - d, CHOSICA_LAT - d),
                        (CHOSICA_LON + d, CHOSICA_LAT - d),
                        (CHOSICA_LON + d, CHOSICA_LAT + d),
                        (CHOSICA_LON - d, CHOSICA_LAT + d),
                        (CHOSICA_LON - d, CHOSICA_LAT - d),
                    ]),
                    srid=SRID,
                ),
            )
        )

    # §34.3: dos destinos validados por el municipio.
    if not session.scalar(select(Resource).where(Resource.nombre.contains("DEMOSTRACIÓN"))):
        session.add_all([
            Resource(
                tipo="centro_salud",
                nombre="DEMOSTRACIÓN — Centro de Salud Chosica",
                geom=from_shape(Point(CHOSICA_LON + 0.008, CHOSICA_LAT + 0.006), srid=SRID),
                direccion="Av. Lima Sur, Chosica",
                distrito="Lurigancho-Chosica",
                telefono="01-3610000",
                disponible=True,
                accesible_movilidad_reducida=True,
                acepta_mascotas=False,
                validado=True,
                registrado_por_id=operador.id,
                actualizado_en_origen=ahora,
            ),
            Resource(
                tipo="refugio",
                nombre="DEMOSTRACIÓN — Refugio temporal I.E. Chosica",
                geom=from_shape(Point(CHOSICA_LON - 0.010, CHOSICA_LAT + 0.004), srid=SRID),
                direccion="Jr. Arequipa, Chosica",
                distrito="Lurigancho-Chosica",
                capacidad=120,
                disponible=True,
                accesible_movilidad_reducida=True,
                acepta_mascotas=True,
                validado=True,
                registrado_por_id=operador.id,
                actualizado_en_origen=ahora,
            ),
        ])

    # §34.2 paso 10: reporte ciudadano de inundación en la avenida principal.
    if not session.scalar(
        select(CitizenReport).where(CitizenReport.direccion_aproximada.contains("DEMOSTRACIÓN"))
    ):
        session.add(
            CitizenReport(
                reporter_id=rosa.id,
                tipo=HazardType.INUNDACION,
                estado=ReportState.PENDIENTE,
                # Nace pendiente: la escalera del §21.2 lo sube, no el seed.
                trust_level=TrustLevel.PENDIENTE,
                descripcion="El agua cubre la pista en la avenida principal, no se puede pasar.",
                geom=from_shape(Point(CHOSICA_LON + 0.003, CHOSICA_LAT + 0.002), srid=SRID),
                direccion_aproximada="DEMOSTRACIÓN — Av. Principal, cuadra 4",
                distrito="Lurigancho-Chosica",
                reportado_at=ahora - timedelta(minutes=20),
                vence_at=ahora + timedelta(hours=11, minutes=40),
                exif_eliminado=True,
            )
        )

    # Zona de peligro amplia (§20.1: se resuelve con filtro PostGIS, no con
    # exclude_polygons). Quebrada del sector.
    if not session.scalar(select(Hazard).where(Hazard.nombre.contains("DEMOSTRACIÓN"))):
        q = 0.004
        session.add(
            Hazard(
                tipo=HazardType.HUAICO,
                nombre="DEMOSTRACIÓN — Quebrada del sector 4",
                fuente="INGEMMET",
                nivel="alto",
                peligro_alto=True,
                geom=from_shape(
                    Polygon([
                        (CHOSICA_LON - 0.02, CHOSICA_LAT - q),
                        (CHOSICA_LON - 0.02 + 0.03, CHOSICA_LAT - q),
                        (CHOSICA_LON - 0.02 + 0.03, CHOSICA_LAT + q),
                        (CHOSICA_LON - 0.02, CHOSICA_LAT + q),
                        (CHOSICA_LON - 0.02, CHOSICA_LAT - q),
                    ]),
                    srid=SRID,
                ),
                activo=True,
            )
        )

    # Recursos de demostración en Lima Metropolitana.
    #
    # Los del §34 están solo en Chosica, así que cualquier prueba desde otro
    # distrito devolvía "sin ruta verificable" —correcto por el §20.2, pero
    # inútil para probar—. Estos permiten ejercitar el motor en la ciudad.
    #
    # ATENCIÓN: las coordenadas son APROXIMADAS y llevan el prefijo
    # DEMOSTRACIÓN a propósito. Antes del piloto deben sustituirse por el
    # registro de la municipalidad o de INDECI (§23, RF-17). Enviar a alguien a
    # una posta cuya ubicación no está verificada es exactamente lo que el
    # §20.2 quiere evitar.
    demo_lima = [
        ("centro_salud", "DEMOSTRACIÓN — Hospital Loayza (referencial)",
         -12.0500, -77.0430, "Cercado de Lima"),
        ("centro_salud", "DEMOSTRACIÓN — Hospital Dos de Mayo (referencial)",
         -12.0561, -77.0184, "Cercado de Lima"),
        ("refugio", "DEMOSTRACIÓN — Punto de reunión Campo de Marte",
         -12.0708, -77.0378, "Jesús María"),
        ("refugio", "DEMOSTRACIÓN — Punto de reunión Parque de la Reserva",
         -12.0692, -77.0345, "Cercado de Lima"),
        ("centro_salud", "DEMOSTRACIÓN — Centro de salud San Isidro (referencial)",
         -12.0977, -77.0365, "San Isidro"),
        ("refugio", "DEMOSTRACIÓN — Punto de reunión Parque Kennedy",
         -12.1219, -77.0297, "Miraflores"),
    ]
    for tipo, nombre, lat, lon, distrito in demo_lima:
        if session.scalar(select(Resource).where(Resource.nombre == nombre)):
            continue
        session.add(
            Resource(
                tipo=tipo,
                nombre=nombre,
                geom=from_shape(Point(lon, lat), srid=SRID),
                distrito=distrito,
                disponible=True,
                accesible_movilidad_reducida=True,
                acepta_mascotas=(tipo == "refugio"),
                validado=True,
                registrado_por_id=operador.id,
                actualizado_en_origen=ahora,
            )
        )

    logger.info(
        "Escenario §34 listo. Usuarios de demostración: rosa@ validador@ operador@ "
        "admin@demo.senti.pe · contraseña demo-senti-2026"
    )

# §19: los protocolos entran también al RAG. Sin esto, una pregunta general la
# respondería el modelo con lo que recuerde, y el §19 lo pone en el último
# lugar de la precedencia justamente para impedirlo.
DOCUMENTOS_RAG: tuple[dict, ...] = (
    {
        "titulo": "Qué hacer ante una inundación en vivienda",
        "coleccion": "inundacion",
        "hazard": HazardType.INUNDACION,
        "source_slug": "coen-indeci",
        "texto": """Antes de que el agua entre a la vivienda, corte la energía eléctrica
desde el tablero principal. No toque interruptores ni aparatos con las manos mojadas
ni con los pies en el agua.

Suba al punto más alto de la vivienda llevando documentos en una bolsa impermeable,
medicinas y agua. No suba a un espacio sin salida al exterior, como un sótano o un
altillo cerrado.

No cruce agua en movimiento. Treinta centímetros de corriente bastan para derribar a
una persona adulta, y sesenta arrastran un vehículo. No se puede juzgar la
profundidad ni la fuerza a simple vista.

No consuma agua de la red hasta que la autoridad sanitaria lo autorice. El agua de
inundación arrastra desagües y combustible aunque parezca limpia.""",
    },
    {
        "titulo": "Qué hacer ante un huaico o activación de quebrada",
        "coleccion": "huaico",
        "hazard": HazardType.HUAICO,
        "source_slug": "coen-indeci",
        "texto": """Aléjese del cauce de la quebrada y suba a terreno alto y firme, en dirección
perpendicular al flujo. No corra en la misma dirección del material: avanza más rápido
que una persona.

No intente cruzar el material de un huaico, ni a pie ni en vehículo, aunque parezca
detenido. Bajo la superficie el lodo sigue moviéndose y no sostiene peso.

Un ruido sordo creciente que viene de la quebrada, o un aumento repentino de agua
turbia con ramas, indica que el flujo ya está en camino. Es momento de subir, no de
mirar.

Después del paso del huaico no regrese a la vivienda hasta que el municipio o Defensa
Civil lo autoricen: son frecuentes los flujos sucesivos.""",
    },
    {
        "titulo": "Mochila de emergencia para 72 horas",
        "coleccion": "mochila",
        "hazard": None,
        "source_slug": "coen-indeci",
        "texto": """La mochila de emergencia debe alcanzar para 72 horas y poder cargarse
caminando. Colóquela cerca de la salida, no en un armario al fondo.

Contenido básico: agua envasada, alimentos que no necesiten cocción, linterna con pilas
de repuesto, radio a pilas, botiquín, jabón, papel higiénico, una manta ligera, silbato
y dinero en efectivo en billetes pequeños.

Documentos: copias del DNI de cada integrante en bolsa hermética, y una lista con los
teléfonos de la familia escrita a mano. No dependa del celular para recordarlos.

Si en el hogar hay medicamentos habituales, prepare una reserva para varios días junto
con la receta. Si hay bebés, añada fórmula, pañales y agua adicional. Si hay mascota,
añada su comida, correa y un recipiente.""",
    },
    {
        "titulo": "Cómo actuar ante una alerta por lluvias intensas",
        "coleccion": "lluvia",
        "hazard": HazardType.LLUVIA,
        "source_slug": "senamhi-avisos",
        "texto": """Un aviso por lluvias intensas indica probabilidad alta de precipitación
fuerte en una zona y un periodo determinados. No es una orden de evacuación: es tiempo
para prepararse.

Revise techos, canaletas y desagües. Retire objetos sueltos que el viento o el agua
puedan arrastrar. Asegure puertas y ventanas.

Evite transitar por quebradas, cauces secos y zonas bajas mientras dure el aviso,
aunque no esté lloviendo en ese momento: la lluvia en la parte alta de la cuenca llega
después a la parte baja.

Mantenga el celular cargado y tenga a mano documentos y medicinas. Si vive en zona de
ladera o cerca de una quebrada, acuerde con su familia a dónde ir si hay que salir
rápido.""",
    },
    {
        "titulo": "Qué hacer ante un incendio en vivienda",
        "coleccion": "incendio",
        "hazard": HazardType.INCENDIO,
        "source_slug": "coen-indeci",
        "texto": """Salga de inmediato y llame a los Bomberos al 116. No vuelva a entrar a
buscar objetos ni documentos: el humo incapacita en segundos y la mayoria de las
victimas de un incendio mueren por inhalacion, no por quemaduras.

Si hay humo, avance agachado o a gatas: el aire respirable queda en los primeros
centimetros sobre el suelo.

Antes de abrir una puerta, toquela con el dorso de la mano. Si esta caliente, no la
abra: el fuego esta al otro lado. Busque otra salida.

Si no puede salir, quedese en una habitacion con ventana al exterior, tape las
rendijas de la puerta con ropa mojada y hagase visible desde la calle.

Si se le prende la ropa: detengase, tirese al suelo y ruede. Correr aviva las llamas.

No use agua sobre un fuego electrico ni sobre aceite. Corte la electricidad desde el
tablero solo si puede hacerlo sin acercarse al fuego.""",
    },
    {
        "titulo": "Punto de reunión familiar y plan de contacto",
        "coleccion": "primeros pasos",
        "hazard": None,
        "source_slug": "coen-indeci",
        "texto": """Acuerde con su familia dos puntos de reunión: uno cerca de la vivienda,
para salir de inmediato, y otro fuera del barrio, por si la zona queda incomunicada.
Deben ser lugares abiertos, conocidos por todos y alejados de muros, postes y cauces.

Designe a un familiar que viva en otra ciudad como contacto común. En una emergencia
suele ser más fácil comunicarse fuera de la zona afectada que dentro de ella.

Envíe mensajes de texto en lugar de llamar: ocupan menos red y llegan cuando una
llamada no entra.

Practique el plan al menos una vez. Un plan que nunca se ensayó no se recuerda cuando
hace falta.""",
    },
)


def _sembrar_rag(session: Session) -> None:
    from app.rag import ingerir

    for doc in DOCUMENTOS_RAG:
        resultado = ingerir(
            session,
            titulo=doc["titulo"],
            texto=doc["texto"],
            source_slug=doc.get("source_slug"),
            coleccion=doc.get("coleccion"),
            hazard=doc.get("hazard"),
        )
        if not resultado.ya_existia:
            logger.info("RAG: %s -> %d fragmentos", doc["titulo"][:40], resultado.fragmentos)
