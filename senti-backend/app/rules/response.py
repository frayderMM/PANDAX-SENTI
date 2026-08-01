"""Composición de la respuesta (§24.1) y lenguaje prohibido (§20.5, §25).

Toda respuesta al ciudadano sale por aquí, venga del modelo o de una plantilla
fija. Dos funciones:

1. **Orden fijo del §24.1**, siempre el mismo, aunque falten piezas.
2. **Guardia de lenguaje**: el §20.5 prohíbe afirmar que una ruta es segura y
   el §25 prohíbe que el modelo saque conclusiones de una imagen. Esa
   prohibición no puede vivir solo en el prompt; un prompt no es un control.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.rules.fixed_responses import RUTA_CONDICIONES_CAMBIAN

# ── §20.5 y §25: lo que el sistema nunca dice. ─────────────────────────────
# Se comprueba sobre el texto normalizado, ya sin tildes.
_PROHIBIDO: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(ruta|via|camino|carretera)\b[^.]{0,40}\b(es|esta)\b[^.]{0,20}"
                   r"\b(complet(amente|o)|totalmente)?\s*segur[oa]\b"),
        "§20.5 prohíbe afirmar que una ruta es segura; se dice «de menor riesgo "
        "según la información disponible»",
    ),
    (
        re.compile(r"\bno hay (ningun )?peligro\b|\bya paso el peligro\b|\bestan a salvo\b"),
        "§1 prohíbe afirmar que la ausencia de alerta significa ausencia de peligro",
    ),
    (
        re.compile(r"\b(la )?(carretera|via|calle) esta libre\b|\bpuedes? (pasar|cruzar) sin problema\b"),
        "§25 prohíbe concluir transitabilidad a partir de una imagen",
    ),
    (
        re.compile(r"\bva a (haber|ocurrir) un (sismo|terremoto)\b|\bse predice un sismo\b"),
        "§25 prohíbe predecir sismos",
    ),
    (
        re.compile(r"\btoma\b[^.]{0,20}\b(mg|miligramos|pastillas?|tabletas?)\b"
                   r"|\bte recomiendo (tomar|usar)\b[^.]{0,20}\b(ibuprofeno|paracetamol|"
                   r"antibiotico)\b"),
        "§25 prohíbe recomendar medicamentos",
    ),
]

# §20.5, la forma correcta.
FORMULA_RUTA = (
    "Esta es la ruta de menor riesgo según la información disponible y su "
    "última actualización."
)
MAX_CARACTERES_MODELO = 320


class LanguageViolation(ValueError):
    """El texto generado dice algo que el sistema tiene prohibido decir."""

    def __init__(self, motivo: str, fragmento: str) -> None:
        super().__init__(f"{motivo}. Fragmento: {fragmento!r}")
        self.motivo = motivo
        self.fragmento = fragmento


def _normalizar(texto: str) -> str:
    import unicodedata

    d = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def revisar_lenguaje(texto: str) -> list[str]:
    """Devuelve los motivos de violación encontrados. Vacío = texto admisible."""
    normalizado = _normalizar(texto)
    motivos = []
    for patron, motivo in _PROHIBIDO:
        m = patron.search(normalizado)
        if m:
            motivos.append(f"{motivo} — «{m.group(0)}»")
    return motivos


def exigir_lenguaje_admisible(texto: str) -> str:
    """Lanza si el texto viola el §20.5 o el §25. Devuelve el texto si pasa.

    Se llama sobre la salida del modelo antes de enviarla. Cuando salta, el
    orquestador cae a plantilla fija: es preferible una respuesta menos
    natural a una respuesta que promete seguridad.
    """
    motivos = revisar_lenguaje(texto)
    if motivos:
        raise LanguageViolation(motivos[0], texto[:120])
    return texto


def limitar_salida_modelo(texto: str, max_caracteres: int = MAX_CARACTERES_MODELO) -> str:
    """Reduce la redacción del modelo a un párrafo corto para móvil."""
    una_linea = " ".join(texto.split())
    if len(una_linea) <= max_caracteres:
        return una_linea
    corte = una_linea[:max_caracteres].rstrip()
    ultimo_punto = corte.rfind(".")
    if ultimo_punto >= max_caracteres // 2:
        return corte[: ultimo_punto + 1]
    ultimo_espacio = corte.rfind(" ")
    if ultimo_espacio > 0:
        corte = corte[:ultimo_espacio]
    return f"{corte.rstrip()}..."


@dataclass
class SourceCitation:
    """§11.4: institución, URL, fecha y hora de consulta.

    §12: para contenido oficial ingerido se cita además el hash de origen.
    """

    institucion: str
    url: str | None = None
    consultada_at: datetime | None = None
    sha256: str | None = None
    vigente: bool = True

    def render(self, abreviado: bool = False) -> str:
        if abreviado:
            return self.institucion
        partes = [self.institucion]
        if self.url:
            partes.append(self.url)
        if not self.vigente:
            partes.append("(fuente no vigente, referencia histórica)")
        return " · ".join(partes)


@dataclass
class Respuesta:
    """§24.1, orden fijo:

    1. Nivel o advertencia  2. Acción inmediata  3. Resultado oficial
    4. Ruta o instrucción   5. Fuente            6. Hora
    7. Limitación

    Los campos vacíos se omiten, pero el orden de los presentes nunca cambia.
    Es lo que hace que la respuesta sea legible en WhatsApp con el texto solo,
    como exige el §7.3.
    """

    nivel_o_advertencia: str | None = None
    accion_inmediata: str | None = None
    resultado_oficial: str | None = None
    ruta_o_instruccion: str | None = None
    fuentes: list[SourceCitation] = field(default_factory=list)
    hora_actualizacion: datetime | None = None
    limitacion: str | None = None

    def render(self, *, abreviado: bool = False, incluir_fuentes: bool = True) -> str:
        """Compone la respuesta en el orden del §24.1.

        `incluir_fuentes=False` saca la fuente y la hora del cuerpo para que el
        cliente las muestre aparte, en un desplegable. Solo vale donde hay
        interfaz: en WhatsApp y en modo ligero **no hay dónde pulsar**, y el
        §7.3 exige que todo se entienda leyendo solo el texto. Ahí van siempre
        dentro.
        """
        lineas: list[str] = []
        if self.nivel_o_advertencia:
            lineas.append(self.nivel_o_advertencia)
        if self.accion_inmediata:
            lineas.append(self.accion_inmediata)
        if self.resultado_oficial:
            lineas.append(self.resultado_oficial)
        if self.ruta_o_instruccion:
            lineas.append(self.ruta_o_instruccion)

        if self.fuentes and incluir_fuentes:
            etiqueta = "Fuente" if len(self.fuentes) == 1 else "Fuentes"
            lineas.append(
                f"{etiqueta}: " + "; ".join(f.render(abreviado) for f in self.fuentes)
            )
        if self.hora_actualizacion and incluir_fuentes:
            fmt = "%H:%M" if abreviado else "%d/%m %H:%M"
            lineas.append(f"Actualización: {self.hora_actualizacion.strftime(fmt)}.")

        # §24.2: la limitación no es opcional cuando hay una ruta o una
        # instrucción de por medio.
        limitacion = self.limitacion
        if limitacion is None and self.ruta_o_instruccion:
            limitacion = RUTA_CONDICIONES_CAMBIAN
        if limitacion:
            lineas.append(limitacion)

        return "\n".join(lineas)

    def validar(self) -> None:
        """Comprueba lo que el §32.2 mide al 100 %.

        - toda respuesta cita fuente y hora verificables;
        - ninguna afirmación va sin respaldo de fuente.
        """
        exigir_lenguaje_admisible(self.render())
        if self.resultado_oficial and not self.fuentes:
            raise ValueError(
                "§24.1 y §32.2: una respuesta con resultado oficial debe citar su fuente."
            )
        if self.fuentes and self.hora_actualizacion is None:
            raise ValueError("§24.1 y §32.2: toda fuente citada va con su hora de actualización.")
