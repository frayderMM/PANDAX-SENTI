from __future__ import annotations

from datetime import UTC, datetime

from app.domain import UrgencyLevel
from app.orchestrator.pipeline import EntradaUsuario, Orchestrator
from app.orchestrator.tools import ToolContext


class _ResultadoVacio:
    """Lo que SQLAlchemy devuelve cuando no hay filas."""

    def all(self) -> list:
        return []

    def scalars(self) -> _ResultadoVacio:
        return self


class _SesionVacia:
    """Base sin filas. Basta para los caminos que no consultan nada.

    El rojo no llega a tocarla —responde antes de mirar la base—, y los demás
    niveles la usan para el RAG, que sin corpus devuelve vacío y deja seguir
    hasta el modelo, que es lo que estos tests quieren observar.
    """

    def execute(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        return _ResultadoVacio()

    def scalar(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        return None


def _orchestrator() -> Orchestrator:
    return Orchestrator(
        ToolContext(
            session=_SesionVacia(),  # type: ignore[arg-type]
            user=None,
            ahora=datetime(2026, 7, 30, tzinfo=UTC),
        )
    )


def test_amarillo_pasa_por_el_modelo() -> None:
    """Solo el rojo y la cola llena se saltan el modelo.

    Naranja y amarillo tenían plantilla propia y devolvían consejo genérico sin
    mirar el mensaje: a «agua entrando a mi casa» contestaba lo mismo que a
    cualquier otra cosa. Una respuesta instantánea que no responde no es una
    respuesta, y el §29 solo exige saltarse el modelo en rojo (§18) y bajo
    carga.

    El test no supone si hay modelo levantado o no —en local no lo hay y en el
    servidor sí—, así que comprueba lo único que debe cumplirse en los dos
    casos: si la respuesta salió por plantilla, fue porque el modelo falló o
    porque la cola estaba llena. Nunca porque el nivel tuviera atajo propio.
    """
    for texto, nivel in (
        ("Hay lluvia fuerte y agua entrando a mi casa en Chosica", UrgencyLevel.AMARILLO),
        ("explicame que significa una alerta amarilla por lluvia fuerte", UrgencyLevel.AMARILLO),
    ):
        salida = _orchestrator().responder(EntradaUsuario(texto=texto))
        assert salida.urgencia is nivel
        motivo = salida.motivo_plantilla or ""
        assert "nivel amarillo" not in motivo
        if salida.respuesta_plantilla_fija:
            assert "modelo no disponible" in motivo or "cola" in motivo


def test_invitado_no_recibe_rag_para_una_herramienta_restringida() -> None:
    salida = _orchestrator().responder(EntradaUsuario(texto="Quiero ir al hospital más cercano"))
    assert salida.respuesta_plantilla_fija is True
    assert "Sin sesión iniciada" in salida.texto
    assert "RAG" in (salida.motivo_plantilla or "")
