"""Router de intención: decide QUÉ herramienta hace falta, sin usar el modelo.

El coste real en un servidor de 2 vCPU no está en generar tokens: está en el
prompt fijo. Mandar los esquemas de las diez herramientas en cada petición son
~1118 tokens que el modelo reprocesa para, casi siempre, pedir una sola. Este
módulo elige esa herramienta con expresiones regulares y deja el prompt del
modelo reducido a redactar.

**Por qué el router no es un modelo pequeño.** La primera idea razonable es
poner un modelo diminuto a clasificar. En esta máquina sale peor:

- un segundo GGUF compite por RAM y por los mismos 2 vCPU;
- una llamada al modelo son cientos de milisegundos en el mejor caso, frente a
  microsegundos de una regex;
- y sobre todo, un clasificador estadístico no se puede probar caso por caso.
  Todo el diseño de SENTI descansa en que las decisiones sean deterministas y
  medibles (§32); meter un modelo en la ruta de decisión rompe justo eso.

El modelo entra donde aporta —redactar en lenguaje natural— y no donde una
tabla lo hace mejor.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from app.rules.urgency import normalize


class Intent(str, enum.Enum):
    """Qué necesita el mensaje. Cada valor mapea a una herramienta del §16."""

    ALERTA = "alerta"
    RUTA = "ruta"
    RECURSOS = "recursos"
    PLAN = "plan"
    REPORTE = "reporte"
    FUENTES = "fuentes"
    PERFIL = "perfil"
    OFFLINE = "offline"
    CONTACTO = "contacto"
    WEB = "web"
    IMAGEN = "imagen"
    GENERAL = "general"


# Intent → herramienta del registro. `GENERAL` e `IMAGEN` no llaman a ninguna:
# se responden con el conocimiento ya presente en el contexto.
HERRAMIENTA: dict[Intent, str | None] = {
    Intent.ALERTA: "consultar_alerta_actual",
    Intent.RUTA: "calcular_ruta",
    Intent.RECURSOS: "buscar_recursos_cercanos",
    Intent.PLAN: "crear_plan_familiar",
    Intent.REPORTE: "consultar_reporte",
    Intent.FUENTES: "consultar_estado_fuentes",
    Intent.PERFIL: "consultar_perfil_hogar",
    Intent.OFFLINE: "guardar_informacion_offline",
    Intent.CONTACTO: "preparar_mensaje_contacto",
    Intent.WEB: "consultar_web_oficial",
    Intent.IMAGEN: None,
    Intent.GENERAL: None,
}


# El orden importa: gana el primero que coincide. Están ordenados de más
# específico a más genérico, porque "¿cómo llego al centro de salud?" es una
# ruta y no una consulta de recursos, aunque mencione ambos.
_PATRONES: list[tuple[Intent, str]] = [
    (
        Intent.GENERAL,
        # Estar atascado abre el mapa para que la persona señale el bloqueo;
        # no es una orden para calcular una ruta automática desde su GPS.
        r"\batascad[oa]s?\b|\bno puedo salir\b|\bcalle bloqueada donde estoy\b",
    ),
    (
        Intent.RUTA,
        # Pedir el mapa de un hospital o de su ubicación es una solicitud de
        # ruta hacia ese recurso, no solo una lista de establecimientos.
        r"\bdame .*\bmapa\b|\bmapa\b.{0,45}\b(hospital|clinica|clínica|centro de salud|posta)\b"
        r"|\b(hospital|clinica|clínica|centro de salud|posta)\b.{0,45}\b(map|ubicacion|ubicación)\b",
    ),
    (
        Intent.RUTA,
        # `\bruta\b` a secas cubre "ruta de escape", "ruta de salida", "dame
        # una ruta"... Enumerar preposiciones dejaba fuera justo las formas que
        # alguien usa con prisa.
        r"\bruta\b|\bcomo (llego|voy|salgo|llegamos|vamos|escapo|escapamos)\b"
        r"|\bcamino (hacia|para|a)\b|\bpor donde (paso|voy|salgo|escapo)\b"
        r"|\bescapar\b|\bevacuar\b|\bsacame de\b|\bsalir de (aqui|aca)\b"
        r"|\bcomo me voy\b|\bhacia donde\b",
    ),
    (
        Intent.RECURSOS,
        r"\bdonde (hay|esta|queda|encuentro)\b|\brefugio\b|\balbergue\b"
        r"|\bcentro de salud\b|\bposta\b|\bhospital\b|\bcentro de apoyo\b"
        r"|\bmas cercano\b|\bcerca de mi\b",
    ),
    (
        Intent.PLAN,
        r"\bplan familiar\b|\bque (debo|tengo que|hay que) (preparar|hacer|alistar)\b"
        r"|\bmochila\b|\bkit de emergencia\b|\bchecklist\b|\bque llevo\b|\bque guardo\b"
        r"|\bpunto de reunion\b",
    ),
    (
        Intent.ALERTA,
        r"\balerta\b|\baviso\b|\bhay peligro\b|\bnivel (naranja|rojo|amarillo)\b"
        r"|\bafecta mi zona\b|\bmi distrito\b|\bemergencia en mi\b|\bsenamhi\b"
        r"|\bque significa\b.{0,20}\b(alerta|nivel|aviso)\b",
    ),
    (
        Intent.REPORTE,
        # Sin `\b` final tras los verbos: son raíces, y "bloqueada" o
        # "cerradas" continúan con más letras. Un `\b` ahí no casa nunca.
        r"\bcomo esta (la|el)\b.{0,25}\b(via|avenida|calle|carretera|puente|pista)\b"
        r"|\b(via|avenida|calle|carretera|puente)\b.{0,20}\b(bloquead|cerrad|inundad|transitable)"
        r"|\bse puede pasar\b|\bhay reportes?\b|\besta abierta\b",
    ),
    (
        Intent.FUENTES,
        r"\bde donde (sacas|viene|obtienes)\b|\bque fuentes?\b|\bes oficial\b"
        r"|\bquien lo dice\b|\bcomo lo sabes\b|\besta verificad",
    ),
    (
        Intent.PERFIL,
        r"\bmi perfil\b|\bmi hogar\b|\bmis datos\b|\bque sabes de mi\b"
        r"|\bcuantos somos\b|\bmi familia\b",
    ),
    (
        Intent.OFFLINE,
        r"\bsin (conexion|internet|señal|senal|datos)\b|\bdescargar\b|\bguardar para\b"
        r"|\boffline\b|\bme quedo sin\b",
    ),
    (
        Intent.CONTACTO,
        r"\bavisar a\b|\bcontacto de confianza\b|\bmandar un mensaje a\b"
        r"|\bescribirle a\b|\bmi familiar\b",
    ),
    (
        Intent.WEB,
        r"\bultima hora\b|\bnoticias?\b|\bque paso (hoy|ayer|anoche)\b"
        r"|\bbusca(me)?\b|\bcomunicado (de|del)\b"
        # Pronóstico: son datos de hoy o mañana, no están en el RAG ni en la
        # base, y el §11.2 dice que para lluvia se consulta SENAMHI.
        r"|\bpronostico\b|\bva a llover\b|\bhabra lluvia\b|\bllovera\b"
        r"|\bque tiempo (hara|va a hacer)\b|\bclima\b",
    ),
]

_COMPILADOS: list[tuple[Intent, re.Pattern[str]]] = [
    (intent, re.compile(patron)) for intent, patron in _PATRONES
]


@dataclass(frozen=True)
class Ruteo:
    intent: Intent
    herramienta: str | None
    motivo: str

    @property
    def necesita_herramienta(self) -> bool:
        return self.herramienta is not None


def rutear(texto: str, *, tiene_imagen: bool = False) -> Ruteo:
    """Decide la intención del mensaje.

    Con imagen gana siempre `IMAGEN`: si alguien manda una foto de una vía
    inundada, lo que necesita es que se describa lo que se ve (§25), no que se
    consulte una tabla. Y es el único caso que justifica cargar el proyector de
    visión.
    """
    if tiene_imagen:
        return Ruteo(Intent.IMAGEN, None, "el mensaje trae una imagen")

    normalizado = normalize(texto or "")
    for intent, patron in _COMPILADOS:
        m = patron.search(normalizado)
        if m:
            return Ruteo(intent, HERRAMIENTA[intent], f"coincide «{m.group(0)}»")

    return Ruteo(Intent.GENERAL, None, "sin coincidencia; se responde sin herramienta")


def argumentos_por_defecto(
    intent: Intent,
    *,
    distrito: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    texto: str = "",
    contexto_previo: str | None = None,
) -> dict:
    """Argumentos que el backend rellena solo, sin preguntarle al modelo.

    Es la otra mitad del ahorro: si el backend ya sabe el distrito del perfil y
    la ubicación del mensaje, no hace falta que el modelo los deduzca ni que se
    le enseñe el esquema para que los escriba.
    """
    if intent is Intent.ALERTA:
        return {"zona": distrito or ""}
    if intent is Intent.RECURSOS and lat is not None and lon is not None:
        return {"lat": lat, "lon": lon, "tipo": _tipo_recurso(texto)}
    if intent is Intent.RUTA and lat is not None and lon is not None:
        # "Dame una ruta de salida" no nombra un destino. Con la ubicación
        # basta: el destino es el recurso seguro validado más cercano, que es
        # el flujo del §34.2. Pedirle al modelo que invente unas coordenadas de
        # destino sería justo lo que el §25 prohíbe.
        destino = normalize(f"{contexto_previo or ''} {texto}")
        tipo = "centro_salud" if re.search(
            r"\bhospital\b|\bclinica\b|\bclínica\b|\bcentro de salud\b|\bposta\b",
            destino,
        ) else "refugio"
        return {
            "origen_lat": lat,
            "origen_lon": lon,
            "hacia_refugio": True,
            "tipo_destino": tipo,
        }
    if intent is Intent.REPORTE:
        return {"via": _via_mencionada(texto)}
    if intent is Intent.WEB:
        return {"url": _url_oficial_para(texto)}
    return {}


def _tipo_recurso(texto: str) -> str:
    n = normalize(texto)
    if re.search(r"\brefugio\b|\balbergue\b", n):
        return "refugio"
    return "centro_salud"


def _via_mencionada(texto: str) -> str:
    """Extrae el nombre de la vía del mensaje.

    Devuelve el texto completo si no encuentra un nombre: la herramienta hace
    una búsqueda por coincidencia parcial, así que un texto de más es
    preferible a una cadena vacía que no encontraría nada.
    """
    m = re.search(
        r"\b(?:av\.?|avenida|calle|jiron|jr\.?|carretera|puente|pista)\s+([\w\s]{2,40})",
        normalize(texto),
    )
    return m.group(1).strip() if m else texto[:120]


# §11.2, selección por tema. Que la URL la elija una tabla y no el modelo es lo
# que impide que se invente un dominio: el §12 prohíbe enviar enlaces fuera de
# `gob.pe` o del dominio propio.
_URL_POR_TEMA: list[tuple[str, str]] = [
    (r"\blluvia|pronostico|llover|clima|tiempo\b",
     "https://www.senamhi.gob.pe/?p=aviso-meteorologico"),
    (r"\bvia|carretera|sutran|bloqueo|transito\b",
     "https://www.gob.pe/sutran"),
    (r"\bsismo|temblor|terremoto|igp\b",
     "https://www.gob.pe/igp"),
    (r"\bhuaico|deslizamiento|quebrada\b",
     "https://www.gob.pe/indeci"),
]
URL_OFICIAL_POR_DEFECTO = "https://www.gob.pe/indeci"


def _url_oficial_para(texto: str) -> str:
    n = normalize(texto)
    for patron, url in _URL_POR_TEMA:
        if re.search(patron, n):
            return url
    return URL_OFICIAL_POR_DEFECTO
