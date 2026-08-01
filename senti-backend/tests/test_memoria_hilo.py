"""Memoria de la conversación (§13.5, §29).

Lo que se prueba no es que el modelo recuerde —eso es suyo— sino que se le
manden los turnos correctos: los recientes enteros, los viejos resumidos, y
nunca los de otra conversación.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.api.routers.chat import (
    MAX_CARACTERES_RESUMIDO,
    TURNOS_LITERALES,
    _comprimir,
)


class _Msg:
    """Lo mínimo que `_comprimir` mira de un mensaje."""

    def __init__(self, rol: str, contenido: str) -> None:
        self.rol = rol
        self.contenido = contenido
        self.enviado_at = datetime.now(UTC) + timedelta(seconds=1)


def _hilo(n: int, largo: int = 400) -> list[_Msg]:
    return [
        _Msg("user" if i % 2 == 0 else "assistant", f"m{i} " + "x" * largo)
        for i in range(n)
    ]


class TestCompresion:
    def test_un_hilo_corto_va_entero_y_sin_tocar(self) -> None:
        """Con pocos turnos no hay nada que ahorrar y sí mucho que perder."""
        hilo = _hilo(TURNOS_LITERALES)
        assert _comprimir(hilo) == [(m.rol, m.contenido) for m in hilo]

    def test_los_ultimos_turnos_van_literales(self) -> None:
        """Ahí viven los pronombres.

        «¿y por ahí se puede pasar?» no significa nada sin la frase anterior
        entera, así que los últimos intercambios no se tocan.
        """
        hilo = _hilo(10)
        salida = _comprimir(hilo)
        for original, (_, texto) in zip(hilo[-TURNOS_LITERALES:], salida[-TURNOS_LITERALES:]):
            assert texto == original.contenido

    def test_los_viejos_se_resumen(self) -> None:
        hilo = _hilo(10)
        salida = _comprimir(hilo)
        viejos = salida[: -TURNOS_LITERALES]
        assert viejos, "debería quedar algo de los turnos viejos"
        for _, texto in viejos:
            assert len(texto) <= MAX_CARACTERES_RESUMIDO + 1

    def test_resumir_no_pierde_de_que_iba_el_turno(self) -> None:
        """El resumen conserva el principio, que es donde está el tema."""
        hilo = _hilo(10)
        salida = _comprimir(hilo)
        assert salida[0][1].startswith("m0")

    def test_ahorra_de_verdad(self) -> None:
        """Si comprimir no ahorrara, sobraría el código.

        El ahorro tiene un techo por diseño: los cuatro turnos recientes van
        enteros y son los que más pesan. Con doce mensajes de 400 caracteres
        el prompt baja casi a la mitad, y eso en CPU son segundos de espera
        que el ciudadano no hace.
        """
        hilo = _hilo(12)
        entero = sum(len(m.contenido) for m in hilo)
        comprimido = sum(len(texto) for _, texto in _comprimir(hilo))
        assert comprimido < entero * 0.6, f"{comprimido} de {entero}"

    def test_no_se_cuela_un_turno_vacio(self) -> None:
        """Un mensaje vacío en el prompt es una ficha gastada en nada."""
        hilo = _hilo(10)
        hilo[0].contenido = "   "
        assert all(texto.strip() for _, texto in _comprimir(hilo))
