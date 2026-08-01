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

REGION_NACIONAL = "PE"
REGION_LIMA_CALLAO = "PE-LIM"


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
