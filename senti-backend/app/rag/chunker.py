"""Troceado de documentos oficiales (§19).

El chunker no es genérico a propósito. Los documentos que ingiere SENTI son
boletines de SENAMHI, protocolos de INDECI y comunicados municipales: texto
corto, muy estructurado, donde **partir un párrafo por la mitad destruye una
instrucción**. Un trozo que dice "no cruce el cauce" separado del que dice
"si el agua supera la rodilla" es peor que no tener ninguno.

Por eso se corta por párrafo y solo se parte dentro de uno cuando no queda más
remedio, buscando el final de frase más cercano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# nomic-embed-text-v1.5 tiene ventana de 2048 tokens, pero los trozos útiles
# para responder son mucho más cortos: un fragmento largo diluye la señal y
# hace que el vecino más cercano deje de ser el más relevante.
MAX_CARACTERES = 900
MIN_CARACTERES = 120
# Solapamiento entre trozos consecutivos: una instrucción que cae justo en el
# corte aparece entera en al menos uno de los dos.
SOLAPE = 120

_PARRAFO = re.compile(r"\n\s*\n")
_FIN_FRASE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Fragmento:
    orden: int
    texto: str


def _partir_largo(texto: str) -> list[str]:
    """Parte un párrafo demasiado largo por final de frase."""
    frases = _FIN_FRASE.split(texto)
    trozos: list[str] = []
    actual = ""
    for frase in frases:
        if actual and len(actual) + len(frase) + 1 > MAX_CARACTERES:
            trozos.append(actual.strip())
            # Se arrastra la cola del trozo anterior para no perder el hilo.
            actual = actual[-SOLAPE:] + " " + frase
        else:
            actual = f"{actual} {frase}".strip()
    if actual.strip():
        trozos.append(actual.strip())
    return trozos


def trocear(texto: str) -> list[Fragmento]:
    """Divide un documento en fragmentos indexables.

    Los párrafos cortos consecutivos se agrupan: un boletín con veinte líneas
    de una frase produciría veinte vectores casi idénticos, y eso satura la
    búsqueda sin añadir información.
    """
    if not texto or not texto.strip():
        return []

    parrafos = [p.strip() for p in _PARRAFO.split(texto) if p.strip()]
    if not parrafos:
        return []

    trozos: list[str] = []
    acumulado = ""

    for parrafo in parrafos:
        if len(parrafo) > MAX_CARACTERES:
            if acumulado:
                trozos.append(acumulado)
                acumulado = ""
            trozos.extend(_partir_largo(parrafo))
            continue

        candidato = f"{acumulado}\n\n{parrafo}".strip() if acumulado else parrafo
        if len(candidato) > MAX_CARACTERES:
            trozos.append(acumulado)
            acumulado = parrafo
        else:
            acumulado = candidato

    if acumulado:
        trozos.append(acumulado)

    # Un fragmento diminuto suelto (una firma, un número de página) no aporta
    # nada y sí ruido: se pega al anterior.
    fusionados: list[str] = []
    for t in trozos:
        if fusionados and len(t) < MIN_CARACTERES:
            fusionados[-1] = f"{fusionados[-1]}\n{t}"
        else:
            fusionados.append(t)

    return [Fragmento(i, t) for i, t in enumerate(fusionados)]
