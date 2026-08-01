"""Teléfonos de emergencia (§24.3).

"La tabla es configurable por región, no texto fijo en el código." Estos son
los valores de arranque que se siembran en `emergency_phones`; la consulta en
caliente va contra la tabla, no contra este módulo.

El módulo existe igual porque el §26 exige que los teléfonos por región estén
disponibles sin conexión y el §29 exige que el nivel rojo responda con el
modelo apagado — y, en el peor caso, también con la base de datos caída. La
numeración nacional se verificó en el directorio oficial de la PCM y en las
páginas de PNP, Minsa, Bomberos y EsSalud: https://www.gob.pe/547-telefonos-de-emergencia.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

REGION_NACIONAL = "PE"
REGION_LIMA_CALLAO = "PE-LIM"

CODIGO_PAIS_PE = "51"


def canonizar_telefono(phone: str) -> str:
    """Deja un número en una sola forma: dígitos con código de país.

    **Los dos caminos por los que llega un teléfono lo traen escrito distinto**,
    y de ahí salen dos averías que no dan error:

    - El seudónimo del §13.5. Evolution entrega `51987654321@s.whatsapp.net` y
      en el registro la gente teclea nueve dígitos; dos textos distintos dan dos
      HMAC distintos, así que el titular de una cuenta entraba por WhatsApp como
      invitado y recibía menos de lo que le corresponde, en silencio.
    - El envío. Evolution no enruta un número sin código de país: responde
      `exists: false` y el mensaje no sale. Las alertas por distrito se mandan a
      números capturados en el registro —nueve dígitos— así que fallarían todas
      sin que nadie se enterara.

    Un móvil peruano son nueve dígitos que empiezan por 9; a esos se les
    antepone el 51. Lo que ya trae código de país o no encaja en ese patrón se
    deja como está: inventarle un prefijo a un número extranjero lo convertiría
    en otro número, que es peor que no reconocerlo.
    """
    digitos = "".join(ch for ch in phone if ch.isdigit())
    if len(digitos) == 9 and digitos.startswith("9"):
        return CODIGO_PAIS_PE + digitos
    return digitos


@dataclass(frozen=True)
class EmergencyContact:
    situacion: str
    numero: str
    entidad: str
    orden: int = 100


# §24.3, tabla literal.
NACIONALES: tuple[EmergencyContact, ...] = (
    EmergencyContact("Emergencia en carretera", "110", "Policía de Carreteras", 10),
    EmergencyContact("Bloqueo, vía inundada, socorro vial", "0800-12345", "Aló SUTRAN", 20),
    EmergencyContact("Defensa Civil", "115", "INDECI", 30),
    EmergencyContact("Policía", "105", "PNP", 40),
    EmergencyContact(
        "Bomberos, rescate, materiales peligrosos", "116", "Cuerpo General de Bomberos", 50
    ),
    EmergencyContact("Emergencia médica", "106", "SAMU", 60),
    EmergencyContact("Asegurados EsSalud", "117", "EsSalud", 70),
)

# §24.3: "El 911 opera en fase de pruebas como número único en Lima
# Metropolitana y Callao". Se ofrece solo en esa región y se declara que está
# en pruebas: presentarlo como número único nacional sería falso.
LIMA_CALLAO: tuple[EmergencyContact, ...] = (
    EmergencyContact(
        "Número único (en fase de pruebas en Lima Metropolitana y Callao)",
        "911",
        "Central 911",
        5,
    ),
    *NACIONALES,
)

POR_REGION: dict[str, tuple[EmergencyContact, ...]] = {
    REGION_NACIONAL: NACIONALES,
    REGION_LIMA_CALLAO: LIMA_CALLAO,
}


def para_region(region: str | None) -> tuple[EmergencyContact, ...]:
    """Devuelve los teléfonos de la región, con caída a los nacionales.

    Una región desconocida nunca deja al usuario sin números.
    """
    if region and region in POR_REGION:
        return tuple(sorted(POR_REGION[region], key=lambda c: c.orden))
    return NACIONALES


def render(region: str | None = None, *, abreviado: bool = False) -> str:
    contactos = para_region(region)
    if abreviado:
        return " · ".join(f"{c.numero} {c.entidad}" for c in contactos[:4])
    return "\n".join(f"{c.situacion}: {c.numero} ({c.entidad})" for c in contactos)


def render_consulta(texto: str, region: str | None = None) -> str:
    """Responde una consulta telefónica con la tabla verificada.

    Estas preguntas no deben pasar por embeddings: un documento sobre mochila
    puede mencionar "teléfonos" y ganar semánticamente aunque no responda qué
    número pidió la persona. La tabla de teléfonos es la fuente determinista.
    """
    normalizado = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    contactos = para_region(region)
    patrones = {
        "bomberos": r"\bbomber[oa]s?\b",
        "policia": r"\bpolicia\b|\bpnp\b",
        "samu": r"\bsamu\b|\bmedic[ao]\b|\bsalud\b",
        "defensa civil": r"\bdefensa civil\b|\bindeci\b",
        "sutran": r"\bsutran\b|\bcarretera\b|\bsocorro vial\b",
        "essalud": r"\bessalud\b|\basegurad[oa]s?\b",
    }
    seleccionados = [
        contacto
        for contacto in contactos
        if any(
            re.search(patron, normalizado)
            and (clave in contacto.entidad.lower() or clave in contacto.situacion.lower())
            for clave, patron in patrones.items()
        )
    ]
    if not seleccionados:
        return "Teléfonos oficiales de emergencia:\n" + render(region)
    return "\n".join(
        f"{contacto.situacion}: {contacto.numero} ({contacto.entidad})"
        for contacto in seleccionados
    )
