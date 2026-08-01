"""Modo ligero y niveles de operación (§7.2, §7.3, §7.4).

La regla que gobierna el módulo es el §7.3:

    Ninguna instrucción crítica depende de abrir un enlace, cargar una imagen
    o usar la aplicación.

Por eso `adaptar` no "degrada" el mensaje: verifica que el texto por sí solo ya
era suficiente. Si al quitar enlaces e imagen el mensaje deja de ser
accionable, el mensaje estaba mal construido desde el principio.

El §33 avisa de que postergar esto ata todo el diseño de respuesta al mapa y
obliga a rehacerlo; por eso vive en el núcleo y no en la capa de WhatsApp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain import OperationLevel

# §7.4, tabla de límites.
MAX_CARACTERES_N2 = 600
MAX_BYTES_MAPA_N0 = 150 * 1024
MAX_BYTES_MAPA_N2 = 30 * 1024
MAX_PASOS_RUTA_N2 = 6

# §7.4, activación.
FALLOS_MEDIA_PARA_MODO_LIGERO = 2
UMBRAL_LATENCIA_MS = 8000.0

_URL = re.compile(r"https?://\S+|www\.\S+")


@dataclass(frozen=True)
class ChannelLimits:
    max_caracteres: int | None
    max_bytes_mapa: int | None
    max_pasos_ruta: int | None
    permite_botones: bool
    permite_enlaces: bool
    fuente_abreviada: bool


LIMITES: dict[OperationLevel, ChannelLimits] = {
    OperationLevel.N0_NORMAL: ChannelLimits(
        max_caracteres=None,
        max_bytes_mapa=MAX_BYTES_MAPA_N0,
        max_pasos_ruta=None,
        permite_botones=True,
        permite_enlaces=True,
        fuente_abreviada=False,
    ),
    OperationLevel.N1_ZERO_RATING: ChannelLimits(
        max_caracteres=None,
        max_bytes_mapa=MAX_BYTES_MAPA_N0,
        max_pasos_ruta=None,
        permite_botones=True,
        # §7.2 N1: "Ningún enlace es obligatorio". Se permiten, pero todo lo
        # esencial ya viaja dentro del mensaje.
        permite_enlaces=True,
        fuente_abreviada=False,
    ),
    OperationLevel.N2_SATELITE: ChannelLimits(
        max_caracteres=MAX_CARACTERES_N2,
        max_bytes_mapa=MAX_BYTES_MAPA_N2,
        max_pasos_ruta=MAX_PASOS_RUTA_N2,
        permite_botones=False,
        permite_enlaces=False,
        fuente_abreviada=True,
    ),
    OperationLevel.N3_SIN_RED: ChannelLimits(
        max_caracteres=None,
        max_bytes_mapa=None,
        max_pasos_ruta=None,
        permite_botones=True,
        permite_enlaces=False,
        fuente_abreviada=False,
    ),
    # §7.2 N4: fuera del alcance. El sistema no promete lo que no puede cumplir.
    OperationLevel.N4_SIN_DATOS: ChannelLimits(
        max_caracteres=0,
        max_bytes_mapa=0,
        max_pasos_ruta=0,
        permite_botones=False,
        permite_enlaces=False,
        fuente_abreviada=True,
    ),
}


@dataclass(frozen=True)
class ActivacionModoLigero:
    activo: bool
    motivo: str | None = None


def debe_activar_modo_ligero(
    *,
    fallos_media_consecutivos: int = 0,
    latencia_ms: float | None = None,
    solicitado_por_usuario: bool = False,
    reporta_falta_senal_d2c: bool = False,
) -> ActivacionModoLigero:
    """§7.4, las cuatro condiciones de activación, en el orden del documento."""
    if fallos_media_consecutivos >= FALLOS_MEDIA_PARA_MODO_LIGERO:
        return ActivacionModoLigero(True, "falló el envío de media dos veces seguidas")
    if latencia_ms is not None and latencia_ms > UMBRAL_LATENCIA_MS:
        return ActivacionModoLigero(True, f"latencia sobre el umbral ({latencia_ms:.0f} ms)")
    if solicitado_por_usuario:
        return ActivacionModoLigero(True, "solicitado por el usuario")
    if reporta_falta_senal_d2c:
        return ActivacionModoLigero(
            True, "el usuario reporta falta de señal en un operador compatible con D2C"
        )
    return ActivacionModoLigero(False)


@dataclass
class MensajeAdaptado:
    texto: str
    incluir_mapa: bool
    incluir_botones: bool
    pasos_ruta: list[str]
    truncado: bool = False
    advertencias: list[str] | None = None


def enlace_mapa(lat: float, lon: float) -> str:
    """Enlace a Google Maps con la ruta a pie hasta un punto.

    Para canales de solo texto. En la app hay un botón «Cómo llegar»; en
    WhatsApp no hay dónde ponerlo, así que la dirección viaja escrita y el
    enlace se añade **detrás**, nunca en su lugar (§7.3): quien no pueda o no
    quiera abrirlo tiene que poder llegar igual.

    A pie por la misma razón que el botón de la app: casi toda evacuación de
    este sistema es caminando, y una ruta en coche por una avenida inundada es
    peor que ninguna.

    Cinco decimales bastan —un metro— y recortan una veintena de caracteres
    que en N2 cuentan. No se acorta con un servicio externo: añadiría una
    llamada de red dentro de la respuesta, una dependencia más de un tercero
    en el canal por el que la gente pide ayuda, y sobre todo un enlace cuyo
    destino no se ve antes de tocarlo.
    """
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&destination={lat:.5f},{lon:.5f}&travelmode=walking"
    )


def quitar_enlaces(texto: str) -> str:
    """Elimina URLs del cuerpo (§7.3, §7.4).

    En N2 los enlaces no se acortan ni se abrevian: se quitan. Un enlace en un
    canal satelital de ancho de banda mínimo es peso muerto que además sugiere
    que hay algo importante detrás, y el §7.3 prohíbe exactamente eso.
    """
    return _URL.sub("", texto).replace("  ", " ").strip()


def adaptar(
    texto: str,
    nivel: OperationLevel,
    *,
    pasos_ruta: list[str] | None = None,
    tiene_mapa: bool = False,
    bytes_mapa: int | None = None,
) -> MensajeAdaptado:
    """Ajusta un mensaje a los límites del canal (§7.4)."""
    limites = LIMITES[nivel]
    advertencias: list[str] = []
    resultado = texto
    truncado = False

    if not limites.permite_enlaces and _URL.search(resultado):
        resultado = quitar_enlaces(resultado)
        advertencias.append("§7.3: se quitaron enlaces; la instrucción no depende de ellos")

    pasos = list(pasos_ruta or [])
    if limites.max_pasos_ruta is not None and len(pasos) > limites.max_pasos_ruta:
        pasos = pasos[: limites.max_pasos_ruta]
        advertencias.append(
            f"§7.4: ruta recortada a {limites.max_pasos_ruta} pasos giro a giro"
        )

    incluir_mapa = tiene_mapa
    if limites.max_bytes_mapa is None:
        incluir_mapa = False
    elif tiene_mapa and bytes_mapa is not None and bytes_mapa > limites.max_bytes_mapa:
        # §7.4: en N2 el mapa se omite si no cabe. El texto nunca espera al
        # mapa (§29) y nunca depende de él (§7.3).
        incluir_mapa = False
        advertencias.append("§7.4: mapa omitido por tamaño; el texto es autosuficiente")

    if limites.max_caracteres is not None and len(resultado) > limites.max_caracteres:
        corte = resultado[: limites.max_caracteres]
        # Se corta en el último salto de línea para no partir una instrucción
        # por la mitad: media instrucción es peor que una instrucción menos.
        ultimo_salto = corte.rfind("\n")
        resultado = corte[:ultimo_salto] if ultimo_salto > 0 else corte
        truncado = True
        advertencias.append(f"§7.4: texto recortado a {limites.max_caracteres} caracteres")

    return MensajeAdaptado(
        texto=resultado,
        incluir_mapa=incluir_mapa,
        incluir_botones=limites.permite_botones,
        pasos_ruta=pasos,
        truncado=truncado,
        advertencias=advertencias or None,
    )
