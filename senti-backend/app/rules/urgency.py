"""Detección de urgencia (§18).

Esto NO es una tarea del modelo. El nivel decide si la respuesta pasa por
Gemma o se responde con plantilla fija (§18, §29), y decide la prioridad en la
cola (§29). Una decisión así no puede depender de que un modelo de 7 B acierte.

**Sesgo deliberado hacia el nivel más alto.** El clasificador no interpreta
negaciones ("no hay personas atrapadas" se clasifica igual como rojo). Es una
decisión, no un descuido: un falso positivo de rojo cuesta una respuesta fija
con teléfonos de emergencia; un falso negativo cuesta una persona sin ayuda.
El §32.2 lo confirma al pedir ≥98 % de detección de rojo y 0 % de falsos
negativos de bloqueo, sin poner techo a los falsos positivos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.domain import UrgencyLevel


def normalize(texto: str) -> str:
    """Minúsculas sin tildes. 'Está atrapádo' y 'esta atrapado' deben coincidir."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


# Los disparadores del §18, tabulados. Cada patrón lleva la etiqueta con la
# que aparece en el documento, para que un fallo de clasificación se pueda
# rastrear hasta la fila exacta de la especificación.
_NEGRO: list[tuple[str, str]] = [
    (r"\bva a (haber|ocurrir|pasar) (un )?(sismo|terremoto|temblor)\b"
     r"|\bcuando (va a |habra |habrá )?(temblar|haber (un )?(sismo|terremoto))\b"
     r"|\bpredic(e|es|cion)\b.{0,20}\b(sismo|terremoto|lluvia|huaico)\b",
     "predicción de fenómeno natural"),
    (r"\bque (medicamento|medicina|pastilla)\b|\bque (me )?tomo para\b"
     r"|\bdosis\b|\bcuanto (ibuprofeno|paracetamol|amoxicilina)\b",
     "recomendación de medicamento"),
    (r"\b(es|esta) segur[oa] (la |el )?(via|ruta|calle|carretera|puente)\b"
     r"|\bpuedo pasar sin peligro\b|\bgaranti(za|zas|zame)\b",
     "declarar una vía segura"),
    (r"\bconfirma(me)? (el|este) reporte\b|\bvalida(me)? (el|este) reporte\b"
     r"|\bcambia(me)? (el )?nivel (de )?(la )?alerta\b|\bextiende (la )?vigencia\b",
     "cambiar un nivel oficial o confirmar un reporte"),
]

_ROJO: list[tuple[str, str]] = [
    (r"\batrapad[oa]s?\b|\bencerrad[oa]s?\b|\bsepultad[oa]s?\b|\bbajo (el )?escombros?\b",
     "personas atrapadas"),
    (r"\bherid[oa]s? graves?\b|\bdesangrand|\binconsciente\b|\bno respira\b|\bsin pulso\b",
     "heridos graves"),
    (r"\bagua (esta )?(subiendo|sube) (muy )?rapid|\bcrecida repentina\b|\bnos llega (el agua )?"
     r"(al pecho|al cuello)\b",
     "agua subiendo rápido"),
    (r"\bcables? (electricos?|de luz)\b.{0,30}\bagua\b|\bagua\b.{0,30}\bcables? (electricos?|de luz)\b"
     r"|\bcable caido\b.{0,30}\bagua\b",
     "cables eléctricos en agua"),
    (r"\bse (derrumbo|cayo|colapso) (la |el )?(casa|techo|muro|pared|edificio)\b"
     r"|\bcolapso estructural\b|\bderrumbe de (la )?vivienda\b",
     "colapso estructural"),
    (r"\bse cayo el puente\b|\bpuente colapsad|\bcaida del puente\b|\bpuente se derrumbo\b",
     "caída de puente"),
    (r"\borden de evacuacion\b|\bevacuacion (oficial|inmediata|obligatoria)\b"
     r"|\bnos mandan evacuar\b",
     "orden oficial de evacuación"),
]

_AMARILLO_MOVERSE: list[tuple[str, str]] = [
    (r"\bvarad[oa]s?\b|\baislad[oa]s?\b|\bincomunicad[oa]s?\b|\bno puedo salir\b"
     r"|\bestamos atrapados por el agua\b",
     "persona varada"),
    (r"\bvia restringida\b|\bpaso restringido\b|\bsolo un carril\b|\bcarretera restringida\b",
     "vía restringida"),
    (r"\bagua (esta )?(entrando|entro)\b.{0,25}\b(casa|vivienda|cuarto|sala)\b"
     r"|\bse (inundo|esta inundando) (mi |la )?(casa|vivienda)\b",
     "agua entrando a vivienda"),
    (r"\bdeslizamiento\b|\bhuaico\b|\bderrumbe\b|\bse vino el cerro\b",
     "deslizamiento cercano"),
    (r"\b(mi |la )?ruta (habitual |de siempre )?(esta )?bloquead|\bcamino bloqueado\b"
     r"|\bavenida (principal )?(esta )?(inundada|bloqueada)\b|\bno se puede pasar\b",
     "ruta habitual bloqueada"),
]

# Lo que ya era amarillo: señales de riesgo sin urgencia inmediata.
_AMARILLO_RIESGO: list[tuple[str, str]] = [
    # "lluvia fuerte" y "está lloviendo muy fuerte" son el mismo disparador; la
    # forma verbal es al menos tan común como la nominal en el habla real.
    (r"\blluvia (muy |bien )?(fuerte|intensa)\b|\bllueve much"
     r"|\bllov(iendo|io)\b[^.]{0,15}\bfuerte\b|\btormenta\b|\bgranizo\b",
     "lluvia fuerte"),
    (r"\bvia lenta\b|\btrafico lento\b|\bavanza lento\b|\bcongestion\b",
     "vía lenta sin cierre oficial"),
    (r"\bcreo que\b|\bparece que\b|\bme dijeron que\b|\bdicen que\b|\bescuche que\b",
     "reporte no confirmado"),
    (r"\bes peligroso\b|\bhay riesgo\b|\bpuede pasar algo\b|\besta feo\b",
     "riesgo posible"),
]

_VERDE: list[tuple[str, str]] = [
    (r"\bmochila\b|\bque (debo |tengo que )?(preparar|llevar|guardar)\b|\bkit de emergencia\b",
     "preparación / mochila"),
    (r"\bplan familiar\b|\bplan de emergencia\b|\bpunto de reunion\b",
     "plan familiar"),
    (r"\bque significa\b|\bque es\b|\bcomo funciona\b|\bme explicas\b",
     "información general"),
]


def _compilar(patrones: list[tuple[str, str]]) -> list[tuple[re.Pattern[str], str]]:
    return [(re.compile(p), etiqueta) for p, etiqueta in patrones]


_COMPILADOS: dict[UrgencyLevel, list[tuple[re.Pattern[str], str]]] = {
    UrgencyLevel.NEGRO: _compilar(_NEGRO),
    UrgencyLevel.ROJO: _compilar(_ROJO),
    # Moverse y riesgo caen en el mismo nivel: los dos acaban en la misma
    # respuesta —consultar y orientar— y separarlos solo daba una frontera que
    # discutir.
    UrgencyLevel.AMARILLO: _compilar(_AMARILLO_MOVERSE + _AMARILLO_RIESGO),
    UrgencyLevel.VERDE: _compilar(_VERDE),
}


@dataclass(frozen=True)
class StructuralSignals:
    """Señales que NO salen del texto sino del estado verificado del sistema.

    Estas pesan más que cualquier palabra: `orden_evacuacion_oficial` viene de
    una alerta oficial ya ingerida, no de que el usuario escriba "evacuación".
    El §12 exige que una orden oficial prevalezca sobre cualquier cálculo
    propio, y aquí es donde entra.
    """

    orden_evacuacion_oficial: bool = False
    alerta_incluye_zona: bool = False
    ruta_habitual_bloqueada: bool = False
    reporte_no_confirmado: bool = False
    imagen_ambigua: bool = False
    tiene_imagen: bool = False


@dataclass(frozen=True)
class UrgencyAssessment:
    nivel: UrgencyLevel
    disparadores: tuple[str, ...] = field(default=())
    # True cuando el nivel lo fijó una señal verificada y no el texto libre.
    por_senal_estructural: bool = False

    @property
    def usa_plantilla_fija(self) -> bool:
        """§18: el nivel rojo se responde SIN redacción libre del modelo."""
        return self.nivel is UrgencyLevel.ROJO


def classify(texto: str, senales: StructuralSignals | None = None) -> UrgencyAssessment:
    """Clasifica el mensaje en uno de los cuatro niveles del §18.

    Orden de resolución:

    1. Una orden oficial de evacuación es ROJO antes de leer una palabra.
    2. ROJO por texto: gana sobre todo lo demás.
    3. NEGRO: lo que SENTI tiene prohibido responder (§25).
    4. AMARILLO: moverse, o señales de riesgo.
    5. VERDE: el resto.

    El rojo va ANTES que el negro a propósito. «Hay un herido, qué medicamento
    le doy» pide algo prohibido, pero primero hay un herido: se atiende la
    emergencia y la plantilla roja no receta nada.
    """
    senales = senales or StructuralSignals()
    normalizado = normalize(texto or "")

    # 1. Señales estructurales primero: son hechos verificados, no lenguaje.
    if senales.orden_evacuacion_oficial:
        return UrgencyAssessment(
            UrgencyLevel.ROJO,
            ("orden oficial de evacuación",),
            por_senal_estructural=True,
        )

    # 2. Rojo por texto: vida o muerte, gana sobre todo.
    encontrados = tuple(
        etiqueta
        for patron, etiqueta in _COMPILADOS[UrgencyLevel.ROJO]
        if patron.search(normalizado)
    )
    if encontrados:
        return UrgencyAssessment(UrgencyLevel.ROJO, encontrados)

    # 3. Negro: lo que no se puede responder. Después del rojo, nunca antes.
    encontrados = tuple(
        etiqueta
        for patron, etiqueta in _COMPILADOS[UrgencyLevel.NEGRO]
        if patron.search(normalizado)
    )
    if encontrados:
        return UrgencyAssessment(UrgencyLevel.NEGRO, encontrados)

    # 4. Amarillo por señal verificada: la alerta cubre su zona, o su ruta
    #    habitual está cortada. Son hechos del sistema, no lenguaje.
    estructural_amarillo = []
    if senales.alerta_incluye_zona:
        estructural_amarillo.append("alerta aplicable a su zona")
    if senales.ruta_habitual_bloqueada:
        estructural_amarillo.append("ruta habitual bloqueada")
    if senales.imagen_ambigua:
        estructural_amarillo.append("imagen ambigua")
    if senales.reporte_no_confirmado:
        estructural_amarillo.append("reporte no confirmado")

    encontrados = tuple(
        etiqueta
        for patron, etiqueta in _COMPILADOS[UrgencyLevel.AMARILLO]
        if patron.search(normalizado)
    )
    if encontrados or estructural_amarillo:
        return UrgencyAssessment(
            UrgencyLevel.AMARILLO,
            encontrados + tuple(estructural_amarillo),
            por_senal_estructural=bool(estructural_amarillo) and not encontrados,
        )

    encontrados = tuple(
        etiqueta
        for patron, etiqueta in _COMPILADOS[UrgencyLevel.VERDE]
        if patron.search(normalizado)
    )
    return UrgencyAssessment(UrgencyLevel.VERDE, encontrados)
