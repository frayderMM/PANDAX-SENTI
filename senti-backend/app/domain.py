"""Vocabulario del dominio, sin dependencias.

Este módulo no importa nada de SQLAlchemy, FastAPI ni httpx a propósito: los
mismos tipos los usan las reglas duras (`app.rules`), que deben poder probarse
sin base de datos ni red, y las tablas (`app.models`).
"""

from __future__ import annotations

import enum
from datetime import timedelta


class ConfidenceLevel(str, enum.Enum):
    """§12: la interfaz distingue en texto y en color cuatro niveles.

    El orden importa: es la precedencia con la que se resuelve un conflicto
    entre dos informaciones sobre el mismo hecho.
    """

    OFICIAL = "OFICIAL"
    MUNICIPAL = "MUNICIPAL"
    VALIDADO = "VALIDADO"
    SIN_CONFIRMAR = "SIN_CONFIRMAR"

    @property
    def rank(self) -> int:
        return _CONFIDENCE_RANK[self]


_CONFIDENCE_RANK = {
    ConfidenceLevel.OFICIAL: 0,
    ConfidenceLevel.MUNICIPAL: 1,
    ConfidenceLevel.VALIDADO: 2,
    ConfidenceLevel.SIN_CONFIRMAR: 3,
}


class UrgencyLevel(str, enum.Enum):
    """§18, cuatro niveles por lo que hay que HACER, no por gravedad abstracta.

    - `NEGRO`   lo que SENTI no puede responder (§25). No es una urgencia: es
                una frontera. Se contesta con texto fijo y sin modelo, porque
                dejar que el modelo improvise sobre lo que tiene prohibido
                decir es exactamente la forma de que acabe diciéndolo.
    - `ROJO`    vida o muerte. Texto fijo, sin modelo, en microsegundos.
    - `AMARILLO` moverse: atascos, cierres, llegar a un sitio de emergencia.
    - `VERDE`   preparación y consultas del día a día.

    Antes había un `NARANJA` entre rojo y amarillo. Se quitó porque nadie sabía
    decir dónde acababa uno y empezaba el otro: los dos terminaban en la misma
    respuesta y la frontera solo servía para discutirla.
    """

    NEGRO = "negro"
    VERDE = "verde"
    AMARILLO = "amarillo"
    ROJO = "rojo"

    @property
    def priority(self) -> int:
        """§29: cola por prioridad rojo > amarillo > verde.

        El negro no compite por la cola: no consulta nada y no llama al
        modelo, así que se responde en el acto y no llega a encolarse.
        """
        return _URGENCY_PRIORITY[self]


_URGENCY_PRIORITY = {
    UrgencyLevel.ROJO: 0,
    UrgencyLevel.NEGRO: 1,
    UrgencyLevel.AMARILLO: 2,
    UrgencyLevel.VERDE: 3,
}


class SourceStatus(str, enum.Enum):
    """§11.3. `CAIDO` no significa "sin peligro": significa que no se cita."""

    OK = "ok"
    DEGRADADO = "degradado"
    CAIDO = "caido"
    OBSOLETO = "obsoleto"


class SourceKind(str, enum.Enum):
    """§19: precedencia de fuentes. Gemma siempre ocupa el último lugar."""

    API_OFICIAL = "api_oficial"
    SERVICIO_GEOGRAFICO_OFICIAL = "servicio_geografico_oficial"
    BOLETIN_OFICIAL = "boletin_oficial"
    DOCUMENTO_OFICIAL = "documento_oficial"
    COMUNICADO_MUNICIPAL = "comunicado_municipal"
    REPORTE_VALIDADO = "reporte_validado"
    REPORTE_PROBABLE = "reporte_probable"
    REPORTE_PENDIENTE = "reporte_pendiente"
    BUSQUEDA_WEB_OFICIAL = "busqueda_web_oficial"
    MODELO = "modelo"

    @property
    def precedence(self) -> int:
        return _SOURCE_PRECEDENCE[self]


# §19, literal y en orden. El índice es la precedencia: menor gana.
_SOURCE_PRECEDENCE = {
    SourceKind.API_OFICIAL: 1,
    SourceKind.SERVICIO_GEOGRAFICO_OFICIAL: 2,
    SourceKind.BOLETIN_OFICIAL: 3,
    SourceKind.DOCUMENTO_OFICIAL: 4,
    SourceKind.COMUNICADO_MUNICIPAL: 5,
    SourceKind.REPORTE_VALIDADO: 6,
    SourceKind.REPORTE_PROBABLE: 7,
    SourceKind.REPORTE_PENDIENTE: 8,
    SourceKind.BUSQUEDA_WEB_OFICIAL: 9,
    SourceKind.MODELO: 10,
}


class HazardType(str, enum.Enum):
    """Tipos de peligro. Cada uno tiene su propia vigencia (§20.3, §23)."""

    INUNDACION = "inundacion"
    HUAICO = "huaico"
    DESLIZAMIENTO = "deslizamiento"
    LLUVIA = "lluvia"
    SISMO = "sismo"
    TSUNAMI = "tsunami"
    INCENDIO = "incendio"
    VIA_BLOQUEADA = "via_bloqueada"
    PUENTE_AFECTADO = "puente_afectado"
    ACUMULACION_AGUA = "acumulacion_agua"
    CAIDA_POSTE = "caida_poste"
    OTRO = "otro"


# §20.3: "el peso de un reporte comunitario decae linealmente hasta cero al
# cumplir su vigencia por tipo de peligro". Un reporte vencido no penaliza ni
# tranquiliza. Estos valores son el arranque; el §23 los hace configurables y
# versionados por el administrador.
HAZARD_VALIDITY: dict[HazardType, timedelta] = {
    HazardType.INUNDACION: timedelta(hours=12),
    HazardType.HUAICO: timedelta(hours=24),
    HazardType.DESLIZAMIENTO: timedelta(hours=48),
    HazardType.LLUVIA: timedelta(hours=6),
    HazardType.SISMO: timedelta(hours=6),
    HazardType.TSUNAMI: timedelta(hours=6),
    HazardType.INCENDIO: timedelta(hours=12),
    HazardType.VIA_BLOQUEADA: timedelta(hours=24),
    HazardType.PUENTE_AFECTADO: timedelta(days=7),
    HazardType.ACUMULACION_AGUA: timedelta(hours=8),
    HazardType.CAIDA_POSTE: timedelta(hours=24),
    HazardType.OTRO: timedelta(hours=12),
}


class ReportState(str, enum.Enum):
    """§21.1. `DESACTUALIZADO` se alcanza desde cualquier estado, por vencimiento."""

    BORRADOR = "borrador"
    PENDIENTE = "pendiente"
    EN_REVISION = "en_revision"
    CONFIRMADO = "confirmado"
    RECHAZADO = "rechazado"
    DUPLICADO = "duplicado"
    RESUELTO = "resuelto"
    DESACTUALIZADO = "desactualizado"


class TrustLevel(str, enum.Enum):
    """§21.2, escalera de confianza.

    Solo `CONFIRMADO` excluye una vía de la ruta. Una fotografía no cierra una
    vía; solo el municipio o el Estado cierran.
    """

    PENDIENTE = "pendiente"
    PROBABLE = "probable"
    VALIDADO = "validado"
    CONFIRMADO = "confirmado"


class OperationLevel(str, enum.Enum):
    """§7.2, niveles de operación por conectividad."""

    N0_NORMAL = "N0"
    N1_ZERO_RATING = "N1"
    N2_SATELITE = "N2"
    N3_SIN_RED = "N3"
    N4_SIN_DATOS = "N4"


class Channel(str, enum.Enum):
    PWA = "pwa"
    WHATSAPP = "whatsapp"
    ANDROID = "android"


class ConsentPurpose(str, enum.Enum):
    """§13.4: el consentimiento es granular POR FINALIDAD.

    Un checkbox global de términos y condiciones no satisface el requisito de
    consentimiento expreso del §13.2, por eso no existe un valor "todo".
    """

    MENSAJES = "mensajes"
    UBICACION_EXACTA = "ubicacion_exacta"
    FOTOGRAFIA = "fotografia"
    PERFIL_HOGAR = "perfil_hogar"
    CONTACTO_CONFIANZA = "contacto_confianza"
    # A diferencia de las demás, esta finalidad implica guardar el teléfono
    # en texto plano (AlertSubscriber): es la única forma de poder escribirle
    # a alguien por WhatsApp por iniciativa del sistema. Por eso exige
    # teléfono y distrito explícitos en el registro, no solo el checkbox.
    ALERTAS_WHATSAPP = "alertas_whatsapp"
