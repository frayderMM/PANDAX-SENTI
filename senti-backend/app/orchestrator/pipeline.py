"""Orquestador: las cinco capas del §8.

    1. Entrada del usuario (texto, imagen, ubicación, perfil)
    2. Detección de urgencia
    3. Consulta de fuentes y RAG
    4. Validación geográfica y de seguridad
    5. Redacción con Gemma sobre un resultado ya verificado

Y el flujo de seguridad del §8:

    Pregunta → Gemma identifica intención → Orquestador valida la solicitud
    → Herramienta autorizada consulta datos → Backend valida el resultado
    → Gemma explica → Interfaz muestra fuente, hora y limitaciones

Hay tres salidas y solo una pasa por el modelo:

- **Nivel rojo** → plantilla fija, siempre, sin excepción (§18, §29).
- **Naranja bajo carga** → plantilla fija (§29).
- **El resto** → modelo, con caída a plantilla si falla, tarda o dice algo
  prohibido.

Que la caída exista no es defensivo por costumbre: el §29 dice que las
respuestas de nivel rojo deben ser correctas con el modelo apagado, y un
modelo de 7 B en una 4060 se apaga solo cada vez que hay que cargarlo.
"""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.queue import en_vuelo
from app.core.security import has_permission
from app.domain import Channel, OperationLevel, UrgencyLevel
from app.llm import LLMUnavailable, get_deep_llm, get_llm, imagen_a_data_uri
from app.llm.prompts import system_para
from app.orchestrator import handlers  # noqa: F401  (registra las herramientas)
from app.orchestrator import router
from app.rag import Retriever, como_contexto
from app.orchestrator.tools import (
    ToolArgumentsInvalid,
    ToolContext,
    ToolDenied,
    ToolNotFound,
    registry,
)
from app.rules import fixed_responses as fx
from app.rules import light_mode
from app.rules import phones
from app.rules.response import (
    LanguageViolation,
    Respuesta,
    SourceCitation,
    exigir_lenguaje_admisible,
    limitar_salida_modelo,
)
from app.rules.urgency import StructuralSignals, UrgencyAssessment, classify, normalize

logger = logging.getLogger(__name__)

# Cuántas veces se le deja al modelo pedir herramientas antes de cortar. Con
# Gemma 4 E4B, más de tres vueltas casi siempre significa que se atascó
# pidiendo la misma herramienta, y cada vuelta gasta contexto de los 32k.
MAX_VUELTAS_HERRAMIENTAS = 3

_WEB_CALL_AS_TEXT = re.compile(
    r'^\s*consultar_web_oficial\s*\(\s*url\s*=\s*["\']([^"\']+)["\']\s*\)\s*$',
)


def _sin_argumentos_del_backend(esquema: dict[str, Any], verificados: dict[str, Any]) -> dict[str, Any]:
    """Quita del esquema los argumentos que va a poner el backend.

    Se le decía al modelo "el usuario ya compartió su ubicación" pero no se le
    daban los números, así que veía una herramienta que exige `lat` y `lon`, no
    los tenía, y hacía lo único sensato: pedirlos. Medido en el servidor,
    elegía **cero** herramientas de tres intentos y respondía "necesito tu
    ubicación" a alguien que acababa de darla.

    La solución no es enseñarle las coordenadas —no tiene por qué manejarlas,
    y el §25 le prohíbe inventarlas—, sino que no vea el campo. Lo repone
    `_completar_argumentos` justo antes de ejecutar.

    Efecto secundario que también importa: menos campos son menos tokens en un
    prompt que se paga en cada petición.
    """
    if not verificados:
        return esquema

    parametros = esquema["function"].get("parameters", {})
    propiedades = parametros.get("properties", {})
    sobrantes = verificados.keys() & propiedades.keys()
    if not sobrantes:
        return esquema

    recortado = deepcopy(esquema)
    parametros = recortado["function"]["parameters"]
    for clave in sobrantes:
        parametros["properties"].pop(clave, None)
    if "required" in parametros:
        parametros["required"] = [c for c in parametros["required"] if c not in sobrantes]
    return recortado


def _primer_lugar(datos: dict[str, Any]) -> dict[str, Any] | None:
    """El recurso más cercano de los que devolvió la herramienta.

    Solo el primero: la herramienta ordena por distancia y el §7.3 pide una
    instrucción, no un listado que obligue a elegir con prisa.
    """
    recursos = datos.get("recursos")
    if not isinstance(recursos, list) or not recursos:
        return None
    r = recursos[0]
    if r.get("lat") is None or r.get("lon") is None:
        return None
    return {
        "nombre": r.get("nombre"),
        "direccion": r.get("direccion"),
        "distancia_m": r.get("distancia_m"),
        "lat": r.get("lat"),
        "lon": r.get("lon"),
        "tipo": r.get("tipo"),
        # §: OSM acredita que existe y dónde, no que el municipio lo haya
        # designado. El cliente debe poder decirlo.
        "ubicacion_referencial": bool(r.get("ubicacion_referencial")),
    }


def _lugar_sugerido(datos: dict[str, Any]) -> dict[str, Any] | None:
    """Segundo resultado: el recurso más cercano cuando se pidió uno concreto."""
    r = datos.get("recurso_sugerido")
    if not isinstance(r, dict) or r.get("lat") is None or r.get("lon") is None:
        return None
    return {
        "nombre": r.get("nombre"),
        "direccion": r.get("direccion"),
        "distancia_m": r.get("distancia_m"),
        "lat": r.get("lat"),
        "lon": r.get("lon"),
        "tipo": r.get("tipo"),
        "ubicacion_referencial": bool(r.get("ubicacion_referencial")),
        "sugerido": True,
    }


def _enlace_de_lugar(lugar: dict[str, Any], nivel: OperationLevel) -> str:
    """Las líneas que se añaden en WhatsApp para abrir el sitio en el mapa.

    Si el punto salió de OpenStreetMap y no del registro municipal, se dice
    aquí igual que lo dice el botón de la app: OSM acredita que existe y dónde,
    no que esté designado ni abierto. Callarlo en el canal donde no hay
    interfaz que lo matice sería decir menos justo donde se lee más deprisa.
    """
    lat, lon = lugar.get("lat"), lugar.get("lon")
    if lat is None or lon is None:
        return ""
    if not light_mode.LIMITES[nivel].permite_enlaces:
        # `adaptar` lo quitaría de todas formas, pero quitaría solo la URL y
        # dejaría un "Cómo llegar:" sin nada detrás. No se compone lo que se
        # sabe que se va a borrar.
        return ""
    lineas = ["", f"Cómo llegar: {light_mode.enlace_mapa(float(lat), float(lon))}"]
    if lugar.get("ubicacion_referencial"):
        lineas.append("Ubicación referencial: no está confirmada por el municipio.")
    return "\n".join(lineas)


def _llamada_web_emitida_como_texto(contenido: str | None) -> dict[str, Any] | None:
    """Adapta el formato que Gemma emite cuando no activa tool calling.

    llama.cpp puede devolver la llamada como texto cuando el modelo no respeta
    el protocolo de herramientas. Solo se acepta la firma exacta de la
    herramienta web; la ejecución sigue pasando por el registro y sus permisos.
    """
    if not contenido:
        return None
    coincidencia = _WEB_CALL_AS_TEXT.fullmatch(contenido)
    return {"url": coincidencia.group(1)} if coincidencia else None


@dataclass
class EntradaUsuario:
    """Capa 1 del §8."""

    texto: str
    canal: Channel = Channel.PWA
    imagen: bytes | None = None
    imagen_mime: str = "image/jpeg"
    lat: float | None = None
    lon: float | None = None
    nivel_operacion: OperationLevel = OperationLevel.N0_NORMAL
    senales: StructuralSignals = field(default_factory=StructuralSignals)
    contexto_previo: str | None = None
    # Turnos anteriores de ESTE hilo, en orden, como (rol, texto). Es lo que
    # convierte respuestas sueltas en una conversación: sin esto el modelo
    # contesta cada mensaje como si fuera el primero.
    historial: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class SalidaOrquestador:
    texto: str
    urgencia: UrgencyLevel
    respuesta_plantilla_fija: bool
    herramientas_invocadas: list[dict[str, Any]] = field(default_factory=list)
    fuentes_citadas: list[dict[str, Any]] = field(default_factory=list)
    latencia_ms: float = 0.0
    modelo_usado: str | None = None
    motivo_plantilla: str | None = None
    advertencias: list[str] = field(default_factory=list)
    # §7.3: los pasos son la instrucción y bastan por sí solos. Esto es lo que
    # permite al cliente ofrecer además un mapa, que es una mejora y nunca el
    # portador de la instrucción.
    ruta: dict[str, Any] | None = None
    # El lugar encontrado, para que el cliente ofrezca abrirlo en el mapa.
    # Igual que la ruta: es una mejora sobre un texto que ya está completo.
    lugar: dict[str, Any] | None = None
    lugar_sugerido: dict[str, Any] | None = None
    # §7.4: de las cuatro condiciones de activación del modo ligero, la latencia
    # es la única que el backend puede medir; las otras tres —fallos de envío de
    # media, petición del usuario y falta de señal D2C— solo las conoce el
    # cliente. Se le devuelve medida para que decida, en vez de que la estime.
    sugerir_modo_ligero: bool = False
    motivo_modo_ligero: str | None = None
    # §29: esta respuesta está incompleta y admite que llegue una mejor detrás.
    # Solo lo está la plantilla que se devuelve cuando la cola supera el
    # umbral. El rojo NO: su plantilla ya es la respuesta correcta (§18), y
    # `sin ruta verificable` tampoco: recalcularla podría contradecir al §20.5.
    admite_diferida: bool = False


class Orchestrator:
    def __init__(
        self,
        ctx: ToolContext,
        profundidad_cola: int = 0,
        *,
        modo_diferido: bool = False,
    ) -> None:
        self.ctx = ctx
        self.profundidad_cola = profundidad_cola
        # `modo_diferido` lo activa el worker que calcula la segunda mitad del
        # §29. Sin él, el worker vuelve a tomar los atajos de acuse inmediato y
        # devuelve exactamente el mismo texto que ya recibió el usuario: la
        # respuesta diferida existiría pero no aportaría nada.
        #
        # El nivel rojo NO se ve afectado: su plantilla fija se decide antes,
        # en `requiere_plantilla_fija`, y sigue siendo obligatoria (§18).
        self.modo_diferido = modo_diferido

    def responder(self, entrada: EntradaUsuario) -> SalidaOrquestador:
        inicio = datetime.now()

        # ── Capa 2: detección de urgencia ─────────────────────────────────
        senales = entrada.senales
        if entrada.imagen is not None and not senales.tiene_imagen:
            senales = StructuralSignals(
                orden_evacuacion_oficial=senales.orden_evacuacion_oficial,
                alerta_incluye_zona=senales.alerta_incluye_zona,
                ruta_habitual_bloqueada=senales.ruta_habitual_bloqueada,
                reporte_no_confirmado=senales.reporte_no_confirmado,
                imagen_ambigua=senales.imagen_ambigua,
                tiene_imagen=True,
            )
        evaluacion = classify(entrada.texto, senales)

        # ── Salida sin modelo (§18, §29) ──────────────────────────────────
        if fx.requiere_plantilla_fija(
            evaluacion.nivel, self.profundidad_cola, settings.llm_queue_max_depth
        ):
            return self._respuesta_fija(
                evaluacion,
                entrada,
                motivo=(
                    "nivel rojo: respuesta fija por diseño (§18)"
                    if evaluacion.nivel is UrgencyLevel.ROJO
                    else "nivel negro: fuera de lo que SENTI puede responder (§25)"
                    if evaluacion.nivel is UrgencyLevel.NEGRO
                    else f"cola sobre el umbral ({self.profundidad_cola}) (§29)"
                ),
                inicio=inicio,
            )

        # ── Capas 3 y 4: herramientas, fuentes y validación ───────────────
        try:
            return self._respuesta_con_modelo(evaluacion, entrada)
        except LLMUnavailable as exc:
            logger.warning("Modelo no disponible, se cae a plantilla fija: %s", exc)
            return self._respuesta_fija(
                evaluacion, entrada, motivo=f"modelo no disponible: {exc}", inicio=inicio
            )
        except LanguageViolation as exc:
            # §20.5 / §25: preferimos una respuesta menos natural a una que
            # promete seguridad.
            logger.warning("Salida del modelo rechazada por lenguaje: %s", exc.motivo)
            return self._respuesta_fija(
                evaluacion, entrada, motivo=f"lenguaje prohibido: {exc.motivo}", inicio=inicio
            )

    # ── Camino sin modelo ─────────────────────────────────────────────────
    def _respuesta_fija(
        self,
        evaluacion: UrgencyAssessment,
        entrada: EntradaUsuario,
        *,
        motivo: str,
        inicio: datetime,
    ) -> SalidaOrquestador:
        if evaluacion.nivel is UrgencyLevel.NEGRO:
            # §25: no se le pregunta al modelo por aquello que tiene prohibido
            # decir. Basta que empiece "no puedo predecir sismos, pero
            # normalmente…" para que la frase siguiente sea una predicción.
            texto = fx.NEGRO_FUERA_DE_ALCANCE
        elif evaluacion.nivel is UrgencyLevel.ROJO:
            texto = fx.responder_rojo(evaluacion.disparadores).render()
        else:
            texto = "\n".join(
                [
                    "Recibí tu mensaje y lo estoy procesando con prioridad.",
                    "Mientras tanto, no cruces zonas inundadas ni te acerques a "
                    "cables caídos.",
                    fx.SEGUIR_AUTORIDADES,
                    "",
                    "Teléfonos de emergencia:",
                ]
            )
            from app.rules import phones

            texto += "\n" + phones.render(abreviado=entrada.nivel_operacion is OperationLevel.N2_SATELITE)

        adaptado = light_mode.adaptar(texto, entrada.nivel_operacion)
        return SalidaOrquestador(
            texto=adaptado.texto,
            urgencia=evaluacion.nivel,
            respuesta_plantilla_fija=True,
            admite_diferida=evaluacion.nivel
            not in (UrgencyLevel.ROJO, UrgencyLevel.NEGRO),
            motivo_plantilla=motivo,
            latencia_ms=(datetime.now() - inicio).total_seconds() * 1000,
            advertencias=adaptado.advertencias or [],
        )

    def _respuesta_telefonos(self, entrada: EntradaUsuario, inicio: datetime) -> SalidaOrquestador:
        """Responde teléfonos desde la tabla verificada, sin RAG ni modelo."""
        return SalidaOrquestador(
            texto=phones.render_consulta(entrada.texto),
            urgencia=UrgencyLevel.VERDE,
            respuesta_plantilla_fija=True,
            motivo_plantilla="consulta de teléfonos verificados (§24.3)",
            fuentes_citadas=[
                {
                    "institucion": "PCM — teléfonos de emergencia",
                    "url": "https://www.gob.pe/547-telefonos-de-emergencia",
                    "confianza": "OFICIAL",
                }
            ],
            latencia_ms=(datetime.now() - inicio).total_seconds() * 1000,
        )

    def _respuesta_sin_sesion(
        self, entrada: EntradaUsuario, evaluacion: UrgencyAssessment, inicio: datetime
    ) -> SalidaOrquestador:
        """No deja que una consulta sin permiso caiga accidentalmente al RAG."""
        adaptado = light_mode.adaptar(fx.SIN_SESION_PARA_ZONA, entrada.nivel_operacion)
        return SalidaOrquestador(
            texto=adaptado.texto,
            urgencia=evaluacion.nivel,
            respuesta_plantilla_fija=True,
            motivo_plantilla="herramienta requiere sesión; se omite RAG (§13.4)",
            latencia_ms=(datetime.now() - inicio).total_seconds() * 1000,
            advertencias=adaptado.advertencias or [],
        )

    @staticmethod
    def _coleccion_rag(texto: str) -> str | None:
        """Limita el RAG al protocolo del tema preguntado.

        La similitud semántica por sí sola puede considerar "teléfonos" de una
        mochila cercanos a una consulta de bomberos. La colección explícita
        mantiene juntos pregunta y protocolo, y evita mezclar inundación,
        huaico, incendio y preparación familiar.
        """
        n = normalize(texto)
        if re.search(r"\bmochila\b|\bkit de emergencia\b|\bque llevo\b", n):
            return "mochila"
        if re.search(r"\blluvia\b|\bllover\b|\bpronostico\b|\balerta amarilla\b", n):
            return "lluvia"
        if re.search(r"\bhuaico\b|\bquebrada\b|\bdeslizamiento\b", n):
            return "huaico"
        if re.search(r"\binundacion\b|\bagua entrando\b|\binundad[oa]\b", n):
            return "inundacion"
        if re.search(r"\bincendio\b|\bfuego\b|\bhumo\b", n):
            return "incendio"
        if re.search(r"\bplan familiar\b|\bpunto de reunion\b", n):
            return "primeros pasos"
        return None

    # ── Camino con modelo ─────────────────────────────────────────────────
    def _respuesta_con_modelo(
        self, evaluacion: UrgencyAssessment, entrada: EntradaUsuario
    ) -> SalidaOrquestador:
        # Con imagen manda el modelo profundo: es el único que carga el
        # proyector de visión, y describir lo observable (§25) tolera de sobra
        # su latencia extra porque no compite con una respuesta en curso.
        con_imagen = entrada.imagen is not None
        llm = get_deep_llm() if con_imagen else get_llm()
        max_tokens = settings.llm_deep_max_tokens if con_imagen else None
        modo_ligero = entrada.nivel_operacion in (
            OperationLevel.N2_SATELITE,
            OperationLevel.N3_SIN_RED,
        )

        contenido: Any = entrada.texto
        if entrada.imagen is not None:
            # Multimodal: el GGUF trae mmproj, así que la imagen va como parte
            # del contenido y no como un adjunto que el modelo ignoraría.
            contenido = [
                {"type": "text", "text": entrada.texto},
                {
                    "type": "image_url",
                    "image_url": {"url": imagen_a_data_uri(entrada.imagen, entrada.imagen_mime)},
                },
            ]

        # El modelo no puede saber por su cuenta si el usuario compartió la
        # ubicación, y estaba afirmando que no la tenía cuando sí. Un modelo no
        # debe opinar sobre el estado del sistema: se le dice.
        estado_sistema = []
        if entrada.lat is not None and entrada.lon is not None:
            estado_sistema.append(
                "El usuario YA compartió su ubicación. No se la pidas otra vez "
                "ni digas que no la tienes."
            )
        else:
            estado_sistema.append(
                "El usuario NO ha compartido su ubicación. Si hace falta para "
                "responder, pídesela."
            )

        # §13.4: sin sesión no hay rol, y sin rol no se ofrece ninguna
        # herramienta. Decírselo evita que prometa consultar la zona; que el
        # usuario se entere no se deja a esta línea, sino a la limitación que
        # añade el backend más abajo.
        if self.ctx.user is None:
            estado_sistema.append(
                "El usuario entra como invitado: no hay herramientas ni datos de "
                "su zona. No prometas consultarlos y no pidas la ubicación para "
                "ello. Responde solo con información general de preparación."
            )

        mensajes: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_para(modo_ligero) + "\n\nESTADO ACTUAL\n"
                + "\n".join(estado_sistema),
            },
            # El historial va ENTRE el sistema y el mensaje nuevo, que es su
            # sitio cronológico. Además deja el prefijo estable: llama.cpp
            # reutiliza de caché todo lo anterior y solo procesa lo que se
            # añade, así que acordarse sale casi gratis en fichas.
            *(
                {"role": rol, "content": texto}
                for rol, texto in entrada.historial
                if texto
            ),
            {"role": "user", "content": contenido},
        ]

        rol = self.ctx.user.role if self.ctx.user else None
        invocadas: list[dict[str, Any]] = []
        latencia_total = 0.0
        modelo_usado = None

        # ── Ruteo determinista: qué herramienta hace falta, sin modelo ─────
        #
        # Mandar los esquemas de las diez herramientas son ~1261 tokens que el
        # servidor de 2 vCPU reprocesa para, casi siempre, pedir una sola. El
        # router los reduce a la que toca (~105-214) o a ninguna.
        #
        # Cuando el backend puede rellenar los argumentos por su cuenta, la
        # herramienta se ejecuta AQUÍ y el modelo se salta la vuelta de
        # tool-calling entera: pasa de dos llamadas a una.
        ruta_calculada: dict[str, Any] | None = None
        lugar_encontrado: dict[str, Any] | None = None
        lugar_sugerido: dict[str, Any] | None = None
        ruteo = router.rutear(entrada.texto, tiene_imagen=entrada.imagen is not None)
        if ruteo.intent is router.Intent.TELEFONOS:
            return self._respuesta_telefonos(entrada, datetime.now())
        if ruteo.intent is router.Intent.OFFLINE and re.search(
            r"\bsin (senal|señal)\b", normalize(entrada.texto)
        ):
            adaptado = light_mode.adaptar(fx.SIN_SENAL, entrada.nivel_operacion)
            return SalidaOrquestador(
                texto=adaptado.texto,
                urgencia=evaluacion.nivel,
                respuesta_plantilla_fija=True,
                motivo_plantilla="consulta de falta de señal (§7.5)",
                latencia_ms=0.0,
                advertencias=adaptado.advertencias or [],
            )
        # Recursos y rutas son consultas geográficas: sin sesión no hay dato
        # que consultar. Otras intenciones (por ejemplo una explicación
        # general de una alerta) todavía pueden responderse con RAG.
        if self.ctx.user is None and ruteo.intent in (
            router.Intent.RECURSOS,
            router.Intent.RUTA,
            router.Intent.REPORTE,
            router.Intent.OFFLINE,
        ):
            return self._respuesta_sin_sesion(entrada, evaluacion, datetime.now())
        tools = None
        resultado_verificado: str | None = None

        if rol is not None and not con_imagen:
            # Elige el ROUTER cuando reconoce la intención, y solo entonces se
            # ejecuta la herramienta aquí mismo: una llamada al modelo en vez de
            # dos, sin catálogo en el prompt y sin razonamiento.
            #
            # Se probó dejando elegir al modelo y se midió en el servidor:
            # 18-80 s por mensaje, contra ~2 s con el router. En un sistema
            # donde alguien puede estar esperando, eso no es un matiz.
            if ruteo.necesita_herramienta:
                # El router deduce del mensaje lo que el backend no sabe solo:
                # si el destino es un refugio o un centro de salud, qué vía se
                # menciona, qué web oficial toca. La ubicación y el distrito los
                # repone `_completar_argumentos`, que manda sobre lo demás.
                argumentos = router.argumentos_por_defecto(
                    ruteo.intent,
                    distrito=self._distrito_usuario(),
                    lat=entrada.lat,
                    lon=entrada.lon,
                    texto=entrada.texto,
                    contexto_previo=entrada.contexto_previo,
                )
                argumentos = self._completar_argumentos(
                    ruteo.herramienta, argumentos, entrada
                )
                if argumentos:
                    salida = self._ejecutar(ruteo.herramienta, argumentos)
                    invocadas.append(
                        {
                            "herramienta": ruteo.herramienta,
                            "argumentos": argumentos,
                            "ruteo": ruteo.motivo,
                            **salida["meta"],
                        }
                    )
                    resultado_verificado = salida["contenido"]
                    if salida["meta"].get("ruta"):
                        ruta_calculada = salida["meta"]["ruta"]
                    if salida["meta"].get("lugar"):
                        lugar_encontrado = salida["meta"]["lugar"]
                    if salida["meta"].get("lugar_sugerido"):
                        lugar_sugerido = salida["meta"]["lugar_sugerido"]
                    if salida["meta"].get("sin_ruta"):
                        adaptado = light_mode.adaptar(
                            fx.SIN_RUTA_VERIFICABLE, entrada.nivel_operacion
                        )
                        return SalidaOrquestador(
                            texto=adaptado.texto,
                            urgencia=evaluacion.nivel,
                            respuesta_plantilla_fija=True,
                            motivo_plantilla="sin ruta verificable (§20.5)",
                            herramientas_invocadas=invocadas,
                            fuentes_citadas=list(self.ctx.fuentes),
                            latencia_ms=latencia_total,
                            advertencias=adaptado.advertencias or [],
                        )

            # El router reconoció la intención pero faltaban argumentos que solo
            # salen del mensaje —un destino, una vía—. Se le ofrece **esa** y
            # nada más.
            #
            # Ofrecerle las diez cuesta ~1300 fichas de esquemas y, sobre todo,
            # le da que pensar: medido aquí, razonaba hasta 512 fichas a 9
            # tok/s, casi un minuto antes de escribir la primera palabra. Con
            # una sola herramienta delante no hay nada que deliberar.
            #
            # Cuando el router no reconoce nada, la pregunta va al RAG (§19) y
            # no al catálogo: si ninguna intención encaja, lo que hace falta es
            # documentación, no una herramienta.
            if resultado_verificado is None and ruteo.necesita_herramienta:
                esquema = registry.get(ruteo.herramienta)
                if has_permission(rol, esquema.permiso):
                    tools = [
                        _sin_argumentos_del_backend(
                            esquema.openai_schema(), self._argumentos_del_backend(entrada)
                        )
                    ]

        # ── Sin herramienta: se busca en el RAG antes de responder ────────
        #
        # §19 pone a Gemma en el ÚLTIMO lugar de la precedencia de fuentes. Sin
        # esta búsqueda, una pregunta general la respondería el modelo con lo
        # que recuerde, que es exactamente lo que esa precedencia prohíbe.
        if resultado_verificado is None and not tools and not con_imagen:
            fragmentos = Retriever(self.ctx.session).buscar(
                entrada.texto,
                self.ctx.ahora,
                region=self._distrito_usuario(),
                coleccion=self._coleccion_rag(entrada.texto),
            )
            if fragmentos:
                resultado_verificado = como_contexto(fragmentos)
                # Tres fragmentos del mismo boletín son UNA fuente, no tres.
                # Sin deduplicar, la respuesta terminaba en
                # "Fuentes: COEN / INDECI; COEN / INDECI; COEN / INDECI".
                vistas = {tuple(sorted(f.items())) for f in self.ctx.fuentes}
                for cita in (f.cita() for f in fragmentos):
                    clave = tuple(sorted(cita.items()))
                    if clave not in vistas:
                        vistas.add(clave)
                        self.ctx.fuentes.append(cita)
                invocadas.append(
                    {"herramienta": "rag", "fragmentos": len(fragmentos), "ok": True}
                )

        if resultado_verificado is not None:
            mensajes.append(
                {
                    "role": "user",
                    "content": (
                        "Resultado verificado por el backend. Redacta la respuesta "
                        "solo con esto, sin pedir herramientas:\n" + resultado_verificado
                    ),
                }
            )

        for vuelta in range(MAX_VUELTAS_HERRAMIENTAS):
            with en_vuelo():
                # Elegir cuesta más fichas que redactar: hay que razonar y
                # emitir el JSON de la llamada. Con el presupuesto de la
                # respuesta corta, se trunca a medias y la herramienta se
                # pierde sin dar error.
                presupuesto = settings.llm_tool_max_tokens if tools else max_tokens
                resultado = llm.chat(mensajes, tools=tools or None, max_tokens=presupuesto)
            latencia_total += resultado.latencia_ms
            modelo_usado = resultado.modelo

            # Se le ofreció el catálogo, razonó, no pidió ninguna herramienta y
            # tampoco escribió nada: gastó el presupuesto pensando. Se le vuelve
            # a preguntar sin catálogo, que es una vuelta de redacción pura y
            # barata. Antes esto se tomaba por "modelo no disponible" y el
            # ciudadano recibía una plantilla genérica tras 75 s de espera.
            if tools and not resultado.pide_herramienta and not resultado.content:
                logger.info("El modelo razonó sin responder; se redacta sin catálogo")
                tools = None
                continue

            if not resultado.pide_herramienta:
                argumentos_web = _llamada_web_emitida_como_texto(resultado.content)
                if argumentos_web is not None:
                    salida = self._ejecutar("consultar_web_oficial", argumentos_web)
                    invocadas.append(
                        {
                            "herramienta": "consultar_web_oficial",
                            "argumentos": argumentos_web,
                            **salida["meta"],
                        }
                    )
                    mensajes.extend(
                        [
                            {"role": "assistant", "content": resultado.content or ""},
                            {
                                "role": "user",
                                "content": (
                                    "La herramienta devolvió este resultado verificado:\n"
                                    f"{salida['contenido']}\n"
                                    "Redacta ahora una sola respuesta breve, solo con ese "
                                    "resultado y sin pedir otra herramienta."
                                ),
                            },
                        ]
                    )
                    # La siguiente vuelta es exclusivamente de redacción: el
                    # modelo no debe volver a imprimir la llamada como texto.
                    tools = None
                    continue
                break

            mensajes.append(
                {
                    "role": "assistant",
                    "content": resultado.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            # `arguments_raw`, no `str(tc.arguments)`: hay que
                            # devolver el JSON literal que emitió el modelo.
                            "function": {"name": tc.name, "arguments": tc.arguments_raw},
                        }
                        for tc in resultado.tool_calls
                    ],
                }
            )

            for tc in resultado.tool_calls:
                argumentos = self._completar_argumentos(tc.name, tc.arguments, entrada)
                salida = self._ejecutar(tc.name, argumentos)
                invocadas.append({"herramienta": tc.name, "argumentos": argumentos, **salida["meta"]})

                if salida["meta"].get("ruta"):
                    ruta_calculada = salida["meta"]["ruta"]
                    if salida["meta"].get("lugar"):
                        lugar_encontrado = salida["meta"]["lugar"]
                    if salida["meta"].get("lugar_sugerido"):
                        lugar_sugerido = salida["meta"]["lugar_sugerido"]

                # §20.5: si no hay ruta verificable el texto es literal y lo
                # entrega el backend. Si se dejara que el modelo redactara
                # sobre el resultado, acabaría ofreciendo la menos mala o
                # soltando jerga interna a alguien que está huyendo.
                if salida["meta"].get("sin_ruta"):
                    adaptado = light_mode.adaptar(
                        fx.SIN_RUTA_VERIFICABLE, entrada.nivel_operacion
                    )
                    return SalidaOrquestador(
                        texto=adaptado.texto,
                        urgencia=evaluacion.nivel,
                        respuesta_plantilla_fija=True,
                        motivo_plantilla="sin ruta verificable (§20.5)",
                        herramientas_invocadas=invocadas,
                        fuentes_citadas=list(self.ctx.fuentes),
                        latencia_ms=latencia_total,
                        advertencias=adaptado.advertencias or [],
                    )

                mensajes.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": salida["contenido"],
                    }
                )

            # La herramienta ya devolvió el dato: lo que queda es redactar, y
            # redactar no necesita ni catálogo ni razonamiento. Dejarlos puestos
            # hacía que el modelo gastara las fichas pensando y devolviera texto
            # vacío; el orquestador lo tomaba por "modelo no disponible" y caía
            # a plantilla fija, tirando la consulta que acababa de hacer.
            tools = None
        else:
            logger.info("Se agotaron las %d vueltas de herramientas", MAX_VUELTAS_HERRAMIENTAS)

        # ── Capa 5: redacción sobre resultado verificado ──────────────────
        if not resultado.content:
            raise LLMUnavailable("el modelo no devolvió texto tras usar las herramientas")

        texto = limitar_salida_modelo(exigir_lenguaje_admisible(resultado.content.strip()))

        fuentes = [
            SourceCitation(
                institucion=f.get("institucion", "fuente sin identificar"),
                url=f.get("url"),
                sha256=f.get("sha256"),
                consultada_at=self.ctx.ahora,
            )
            for f in self.ctx.fuentes
        ]

        # El texto del modelo ocupa el bloque 1-4 del §24.1; el backend añade
        # 5 (fuente), 6 (hora) y 7 (limitación) con valores verificados.
        #
        # La limitación se pone solo si de verdad hubo cálculo de ruta: el
        # §24.2 la exige para rutas, y estamparla en una respuesta sobre la
        # mochila la convierte en ruido que el usuario aprende a saltarse —
        # que es justo lo que no puede pasar con un mensaje de seguridad.
        # Solo si la herramienta devolvió una ruta. Antes bastaba con haberla
        # invocado, así que una consulta sin resultado terminaba con "la ruta
        # se calcula con la información disponible" sin haber ninguna ruta.
        hubo_ruta = any(
            h.get("herramienta") == "calcular_ruta" and not h.get("sin_ruta")
            for h in invocadas
        )
        # §13.4: el invitado preguntó algo que necesitaba una herramienta y no
        # se ejecutó ninguna. La limitación la pone el backend; dejarla en manos
        # del modelo es cómo se acabó pidiendo una ubicación que no servía.
        requiere_sesion = (
            rol is None
            and ruteo.intent
            in (router.Intent.RECURSOS, router.Intent.RUTA, router.Intent.REPORTE, router.Intent.OFFLINE)
        )
        if hubo_ruta:
            limitacion = fx.RUTA_CONDICIONES_CAMBIAN
        elif requiere_sesion:
            limitacion = fx.SIN_SESION_PARA_ZONA
        else:
            limitacion = None
        respuesta = Respuesta(
            resultado_oficial=texto,
            fuentes=fuentes,
            hora_actualizacion=self.ctx.ahora if fuentes else None,
            limitacion=limitacion,
        )
        # §7.3: en WhatsApp y en modo ligero no hay interfaz donde desplegar
        # nada, así que la fuente y la hora viajan dentro del texto. En la app
        # se entregan aparte y el cliente las muestra bajo un control.
        fuentes_en_texto = (
            modo_ligero
            or entrada.canal is Channel.WHATSAPP
            or entrada.nivel_operacion is not OperationLevel.N0_NORMAL
        )
        texto_final = respuesta.render(abreviado=modo_ligero, incluir_fuentes=fuentes_en_texto)
        # §7.3: el enlace al mapa solo en canales sin interfaz. La app recibe
        # `lugar` y dibuja su botón «Cómo llegar»; mandarle además la URL en el
        # texto sería la misma acción dos veces. Va antes de `adaptar` a
        # propósito: así en N2 lo quita la propia regla de enlaces y el límite
        # de 600 caracteres lo cuenta, en vez de colarse por detrás.
        if entrada.canal is Channel.WHATSAPP and lugar_encontrado:
            texto_final += _enlace_de_lugar(lugar_encontrado, entrada.nivel_operacion)
        adaptado = light_mode.adaptar(texto_final, entrada.nivel_operacion)

        # §7.4: la latencia medida decide si conviene degradar el canal. Se
        # calcula aquí, con el dato real de esta petición, y no se estima.
        activacion = light_mode.debe_activar_modo_ligero(latencia_ms=latencia_total)

        return SalidaOrquestador(
            texto=adaptado.texto,
            urgencia=evaluacion.nivel,
            respuesta_plantilla_fija=False,
            herramientas_invocadas=invocadas,
            fuentes_citadas=list(self.ctx.fuentes),
            latencia_ms=latencia_total,
            modelo_usado=modelo_usado,
            sugerir_modo_ligero=activacion.activo,
            motivo_modo_ligero=activacion.motivo,
            lugar=lugar_encontrado,
            lugar_sugerido=lugar_sugerido,
            advertencias=adaptado.advertencias or [],
            ruta=ruta_calculada,
        )

    def _distrito_usuario(self) -> str | None:
        """Distrito del perfil del hogar, para rellenar argumentos sin modelo.

        Sale del perfil y nunca del mensaje: el §13.2 guarda la zona aproximada
        precisamente para no tener que deducirla del texto en cada consulta.
        """
        if self.ctx.user is None:
            return None
        from sqlalchemy import select

        from app.models import HouseholdProfile

        perfil = self.ctx.session.scalar(
            select(HouseholdProfile).where(HouseholdProfile.user_id == self.ctx.user.id)
        )
        return perfil.distrito if perfil else None

    def _argumentos_del_backend(self, entrada: EntradaUsuario) -> dict[str, Any]:
        """Lo que sale del estado verificado y **nunca** lo escribe el modelo.

        El distrito viene del perfil (§13.2) y las coordenadas del mensaje,
        igual que el usuario sale del token y nunca de los argumentos (§16).
        """
        verificados: dict[str, Any] = {}
        distrito = self._distrito_usuario()
        if distrito:
            verificados["zona"] = distrito
        if entrada.lat is not None and entrada.lon is not None:
            verificados["lat"] = entrada.lat
            verificados["lon"] = entrada.lon
            verificados["origen_lat"] = entrada.lat
            verificados["origen_lon"] = entrada.lon
        return verificados

    def _completar_argumentos(
        self, nombre: str, propuestos: dict[str, Any], entrada: EntradaUsuario
    ) -> dict[str, Any]:
        """Repone los argumentos que se le ocultaron al modelo.

        Son los mismos que `_sin_argumentos_del_backend` quitó del esquema: se
        le ocultan para que no los pida y se reponen aquí para ejecutar. Se
        sobrescriben siempre, aunque el modelo se los haya inventado.

        Solo se tocan las claves que la herramienta declara: añadir una que no
        acepta la haría fallar por validación en vez de ejecutarse.
        """
        verificados = self._argumentos_del_backend(entrada)
        if not verificados:
            return dict(propuestos)

        try:
            aceptados = registry.get(nombre).args_model.model_fields
        except KeyError:
            # Herramienta desconocida: que falle en `_ejecutar`, que es quien
            # sabe devolverle el error al modelo.
            return dict(propuestos)

        return {**propuestos, **{k: v for k, v in verificados.items() if k in aceptados}}

    def _ejecutar(self, nombre: str, argumentos: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta una herramienta y devuelve lo que el modelo puede ver.

        Los errores se le devuelven al modelo como texto en vez de propagarse:
        un permiso denegado o un argumento mal formado son cosas que el modelo
        puede corregir en la vuelta siguiente, y romper la conversación entera
        por eso dejaría al usuario sin respuesta.
        """
        try:
            r = registry.ejecutar(nombre, argumentos, self.ctx)
        except ToolNotFound as exc:
            return {"contenido": f"ERROR: {exc}", "meta": {"ok": False, "error": "no_existe"}}
        except ToolDenied as exc:
            return {"contenido": f"DENEGADO: {exc}", "meta": {"ok": False, "error": "denegado"}}
        except ToolArgumentsInvalid as exc:
            return {"contenido": f"ARGUMENTOS INVÁLIDOS: {exc}", "meta": {"ok": False, "error": "args"}}

        cuerpo: dict[str, Any] = {"ok": r.ok, **r.datos}
        if r.ausencia:
            cuerpo["ausencia"] = r.ausencia
        return {
            "contenido": json.dumps(cuerpo, ensure_ascii=False, default=str),
            "meta": {
                "ok": r.ok,
                "fuentes": len(r.fuentes),
                "sin_ruta": bool(r.datos.get("sin_ruta_verificable")),
                # El lugar más cercano que se encontró, para que el cliente
                # ofrezca abrirlo en el mapa. El §7.3 obliga a que el texto
                # baste por sí solo —la dirección y la distancia ya van en la
                # respuesta—, así que esto es una mejora y nunca el portador de
                # la instrucción: si el botón no aparece, no se pierde nada.
                "lugar": _primer_lugar(r.datos),
                "lugar_sugerido": _lugar_sugerido(r.datos),
                # Lo que el cliente necesita para dibujar la ruta. Se enumera
                # campo a campo y no se reenvía `r.datos` entero a propósito:
                # ahí dentro van los subpuntajes y los motivos de descarte, que
                # son traza de auditoría (§23) y no información para el usuario.
                "ruta": (
                    {
                        "pasos": r.datos.get("pasos", []),
                        "distancia_m": r.datos.get("distancia_m"),
                        "duracion_s": r.datos.get("duracion_s"),
                        "destino": r.datos.get("destino"),
                        "destino_lat": r.datos.get("destino_lat"),
                        "destino_lon": r.datos.get("destino_lon"),
                        "origen_lat": r.datos.get("origen_lat"),
                        "origen_lon": r.datos.get("origen_lon"),
                        "geometria": r.datos.get("geometria"),
                        "bloqueos": r.datos.get("bloqueos", []),
                    }
                    if r.datos.get("pasos")
                    else None
                ),
            },
        }
