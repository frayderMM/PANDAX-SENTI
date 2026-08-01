"""Respuestas que existen con el modelo apagado (§18, §24.2, §29, RF-22).

"Las respuestas de nivel rojo deben ser correctas con el modelo apagado" (§29).
Este módulo es esa garantía: texto fijo, sin llamadas de red, sin plantillas
dinámicas, sin nada que pueda fallar. Si Gemma, la base de datos y las fuentes
oficiales caen a la vez, esto sigue respondiendo.

Los textos marcados como literales del documento no se editan por estilo. El
§24.2 los llama "mensajes de seguridad obligatorios" y el §7.5 exige que la
instrucción de falta de señal vaya "sin intervención del modelo".
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from app.domain import UrgencyLevel

# ── §7.5, literal. Texto fijo, sin intervención del modelo. ────────────────
SIN_SENAL = (
    "Si no tienes señal: sal a un espacio abierto con vista al cielo, activa "
    "roaming y VoLTE, y espera. Si tu equipo y plan lo permiten, el celular "
    "puede conectarse por satélite y aparecerá el nombre del operador con un "
    "ícono de satélite. Entonces envía tu mensaje por WhatsApp: texto corto "
    "primero, foto después."
)

# ── §24.2, literales. ──────────────────────────────────────────────────────
RUTA_CONDICIONES_CAMBIAN = (
    "La ruta se calcula con la información disponible. Las condiciones pueden cambiar."
)
REPORTE_NO_VALIDADO = "Este reporte es ciudadano y todavía no ha sido validado."
SIN_INFORMACION_TRANSITABLE = (
    "No existe información suficiente para confirmar que esa vía sea transitable."
)
SEGUIR_AUTORIDADES = "Sigue las indicaciones de las autoridades."
MODO_SIN_CONEXION = (
    "Modo sin conexión. La información fue actualizada por última vez a las {hora}."
)

# ── §25. Lo que SENTI no puede responder. ─────────────────────────────────
#
# Se contesta con texto fijo y sin pasar por el modelo. Dejar que el modelo
# improvise sobre aquello que tiene prohibido decir es exactamente la forma de
# que acabe diciéndolo: basta que redacte "no puedo predecir sismos, pero
# normalmente…" para que la frase siguiente sea una predicción.
#
# No se limita a negarse: redirige. Alguien que pregunta qué medicamento dar es
# alguien con un problema real delante, y dejarlo con un "no puedo" es dejarlo
# igual de solo.
NEGRO_FUERA_DE_ALCANCE = (
    "Eso no lo puedo responder: no predigo fenómenos naturales, no receto "
    "medicamentos y no declaro segura ninguna vía. Decirte que sí sería "
    "inventármelo.\n"
    "Para salud: 106 SAMU. Para emergencias: 115 Defensa Civil o 116 Bomberos.\n"
    "Sí puedo ayudarte con alertas oficiales de tu zona, rutas y preparación."
)

# ── §19, literal. ──────────────────────────────────────────────────────────
SIN_EVIDENCIA = "No pude verificar información oficial suficiente para responder."

# ── §13.4. El modo invitado no consulta datos de zona. ─────────────────────
#
# Sin sesión no hay rol, y sin rol no se ofrece ninguna herramienta (§6). El
# modelo, sin dato, pedía la ubicación una y otra vez —incluso cuando ya se le
# había dado—, prometiendo una respuesta que no iba a llegar. Lo dice el
# backend, con la misma fórmula del §11.3: la falta de dato no es ausencia de
# peligro.
SIN_SESION_PARA_ZONA = (
    "Sin sesión iniciada no puedo consultar alertas, rutas ni reportes de tu "
    "zona. Eso no significa que no haya peligro: significa que no tengo el "
    "dato. Inicia sesión en la app, o llama a Defensa Civil 115."
)

# ── §20.5, literal. Cuando no hay ruta. ────────────────────────────────────
SIN_RUTA_VERIFICABLE = (
    "No pude verificar una ruta transitable. No intentes cruzar el bloqueo. "
    "Aléjate del borde de la vía y comunícate con Policía de Carreteras 110, "
    "Aló SUTRAN 0800-12345 o Defensa Civil 115."
)

# ── §13.4, primer contacto por WhatsApp. Literal. ──────────────────────────
CONSENTIMIENTO_WHATSAPP = (
    "Soy SENTI. Para orientarte necesito guardar tu mensaje.\n"
    "Si me compartes tu UBICACIÓN la uso para buscar rutas y la borro en 72 h.\n"
    "Si me envías una FOTO la uso solo para este caso y la borro en 30 días.\n"
    "Puedes decir NO y aun así te doy protocolos y teléfonos de emergencia.\n"
    "Responde ACEPTO para continuar."
)
CONSENTIMIENTO_VERSION = "1.0"

# ── §12, cuando no se puede verificar el origen de una alerta circulante. ──
ALERTA_NO_VERIFICABLE = (
    "No puedo confirmar el origen de esa alerta. No la reenvíes. "
    "Verifica en el canal oficial: INDECI (115) o www.gob.pe/indeci."
)

SALUDO_SIMPLE = (
    "Hola. Soy SENTI. Puedo orientarte ante lluvias, inundaciones, huaicos, "
    "rutas y reportes ciudadanos. Si hay peligro inmediato, dime qué pasó y "
    "en qué zona estás."
)

AGRADECIMIENTO_SIMPLE = (
    "De nada. Si la situación cambia o necesitas reportar un incidente, "
    "escríbeme qué ocurrió y tu ubicación aproximada."
)

AYUDA_SIMPLE = (
    "Puedo ayudarte con orientación ante lluvia, inundación, huaico, rutas de "
    "menor riesgo y reportes. En emergencia llama 115 Defensa Civil, 116 "
    "Bomberos o 105 Policía."
)

MOCHILA_EMERGENCIA = (
    "Prepara agua, linterna, radio o celular cargado, batería externa, botiquín, "
    "medicinas, documentos en bolsa, efectivo, mascarilla, manta ligera y comida "
    "no perecible. Guárdala cerca de la salida."
)

AMARILLO_INMEDIATA = (
    "Precaución: hay señales de riesgo. Evita cruzar zonas inundadas, quebradas "
    "o pendientes inestables. Revisa avisos oficiales, prepara documentos y "
    "medicinas, mantén cargado el celular y acuerda un punto de encuentro con "
    "tu familia. Si el riesgo aumenta, llama 115 Defensa Civil o 116 Bomberos."
)

# §29: acuse del nivel verde.
#
# No afirma nada sobre el peligro —no lo sabe todavía— y no promete seguridad.
# Solo dice que la respuesta viene, que es lo único cierto en ese instante.
# Sin esto, una consulta verde bloqueaba al ciudadano medio minuto mirando una
# pantalla quieta: medido en el servidor, 30 y 74 segundos.
VERDE_INMEDIATA = (
    "Estoy consultando las fuentes oficiales para responderte. "
    "En un momento te escribo con lo que encuentre."
)


@dataclass(frozen=True)
class FixedResponse:
    """Respuesta de nivel rojo: acciones, teléfono, ubicación, escalamiento (§18)."""

    disparador: str
    acciones: tuple[str, ...]
    telefono: str
    entidad: str
    pide_ubicacion: bool = True
    escalamiento: str = "Se registra como prioridad y se avisa al operador municipal."

    def render(self) -> str:
        """§24.1, orden fijo: advertencia → acción → ruta/instrucción → limitación.

        No hay "resultado oficial" ni "fuente/hora" porque una respuesta roja no
        consulta nada: existe precisamente para el caso en que no hay nada que
        consultar.
        """
        lineas = [f"EMERGENCIA: {self.disparador}."]
        lineas.extend(f"{i}. {a}" for i, a in enumerate(self.acciones, start=1))
        lineas.append(f"Llama ahora: {self.telefono} ({self.entidad}).")
        if self.pide_ubicacion:
            lineas.append("Envíame tu ubicación para dirigir la ayuda.")
        lineas.append(SEGUIR_AUTORIDADES)
        return "\n".join(lineas)


# Un disparador rojo del §18 → una respuesta. Las claves son exactamente las
# etiquetas que devuelve `app.rules.urgency`, para que no haya traducción
# intermedia donde se pueda perder un caso.
RESPUESTAS_ROJAS: dict[str, FixedResponse] = {
    "personas atrapadas": FixedResponse(
        disparador="personas atrapadas",
        acciones=(
            "No intentes remover escombros por tu cuenta.",
            "Si la persona responde, mantén contacto de voz y no la muevas.",
            "Aleja a los demás de la estructura afectada.",
        ),
        telefono="116",
        entidad="Bomberos y rescate",
    ),
    "heridos graves": FixedResponse(
        disparador="heridos graves",
        acciones=(
            "No muevas a la persona salvo peligro inmediato.",
            "Si hay sangrado, presiona la herida con un paño limpio.",
            "Cúbrela para que no pierda calor y quédate con ella.",
        ),
        telefono="106",
        entidad="SAMU, emergencia médica",
    ),
    "agua subiendo rápido": FixedResponse(
        disparador="el agua sube rápido",
        acciones=(
            "Sube al punto más alto que tengas cerca, ahora.",
            "No cruces el agua en movimiento, ni a pie ni en vehículo.",
            "Lleva solo documentos y medicinas.",
        ),
        telefono="115",
        entidad="Defensa Civil",
    ),
    "cables eléctricos en agua": FixedResponse(
        disparador="cables eléctricos en contacto con agua",
        acciones=(
            "No toques el agua ni te acerques: puede estar electrificada.",
            "Aleja a todos al menos 10 metros.",
            "No intentes mover el cable con nada, ni con madera.",
        ),
        telefono="116",
        entidad="Bomberos",
    ),
    "colapso estructural": FixedResponse(
        disparador="colapso estructural",
        acciones=(
            "Sal de la edificación y no vuelvas a entrar.",
            "Aléjate de muros, techos y balcones dañados.",
            "Reúne a tu familia en un espacio abierto.",
        ),
        telefono="116",
        entidad="Bomberos y rescate",
    ),
    "caída de puente": FixedResponse(
        disparador="caída de puente",
        acciones=(
            "No te acerques al borde ni intentes cruzar por los restos.",
            "Retrocede y aléjate del cauce.",
            "Advierte a quien venga detrás.",
        ),
        telefono="110",
        entidad="Policía de Carreteras",
    ),
    "orden oficial de evacuación": FixedResponse(
        disparador="orden oficial de evacuación en tu zona",
        acciones=(
            "Evacúa ahora por la ruta que indicó la autoridad.",
            "Lleva documentos, medicinas y agua. Nada más.",
            "No regreses hasta que la autoridad lo autorice.",
        ),
        telefono="115",
        entidad="Defensa Civil",
        escalamiento="Orden oficial vigente. Prevalece sobre cualquier cálculo del sistema.",
    ),
}

# Respuesta roja por defecto si el disparador no está tabulado. Que un caso
# nuevo caiga aquí es aceptable; que no haya respuesta, no.
ROJA_GENERICA = FixedResponse(
    disparador="emergencia en curso",
    acciones=(
        "Ponte a salvo primero: aléjate del agua, de cables y de estructuras dañadas.",
        "No cruces zonas inundadas.",
        "Reúne a tu familia en un punto alto y despejado.",
    ),
    telefono="115",
    entidad="Defensa Civil",
)


def responder_rojo(disparadores: tuple[str, ...] | list[str]) -> FixedResponse:
    """Devuelve la respuesta fija para el primer disparador rojo reconocido."""
    for d in disparadores:
        if d in RESPUESTAS_ROJAS:
            return RESPUESTAS_ROJAS[d]
    return ROJA_GENERICA


def respuesta_conversacional_simple(texto: str) -> str | None:
    """Evita usar el LLM para mensajes que no necesitan interpretación.

    Un saludo no debe ocupar un slot de llama.cpp ni hacer esperar al usuario.
    La coincidencia es deliberadamente estricta para no atrapar mensajes como
    "hola, hay un huaico en mi calle", que sí deben pasar por el clasificador.
    """
    normalizado = _normalizar(texto)
    if normalizado in {"hola", "ola", "buenas", "buenos dias", "buenas tardes", "buenas noches"}:
        return SALUDO_SIMPLE
    if normalizado in {"gracias", "muchas gracias", "ok gracias", "listo gracias"}:
        return AGRADECIMIENTO_SIMPLE
    if normalizado in {"ayuda", "ayudame", "necesito ayuda", "que puedes hacer"}:
        return AYUDA_SIMPLE
    if "mochila" in normalizado or "kit de emergencia" in normalizado:
        return MOCHILA_EMERGENCIA
    return None


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9ñ ]+", " ", sin_tildes)).strip()


def requiere_plantilla_fija(nivel: UrgencyLevel, profundidad_cola: int, umbral: int) -> bool:
    """§29: comportamiento bajo carga.

    Dos niveles no pasan nunca por el modelo, y por motivos distintos:

    - `ROJO` porque su respuesta ya es la correcta y debe llegar con el modelo
      apagado (§18).
    - `NEGRO` porque es lo que el modelo tiene PROHIBIDO decir (§25), y la
      única forma segura de no decirlo es no preguntárselo.

    El amarillo pasa por el modelo en operación normal y cae a plantilla solo
    cuando la cola supera el umbral. El verde no cae por carga: si el sistema
    va lento, va lento, pero responde de verdad.
    """
    if nivel in (UrgencyLevel.ROJO, UrgencyLevel.NEGRO):
        return True
    if nivel is UrgencyLevel.AMARILLO and profundidad_cola > umbral:
        return True
    return False
