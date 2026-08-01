"""§29 — cola por prioridad y degradación bajo carga."""

from __future__ import annotations

import pytest

from app.domain import UrgencyLevel
from app.rules.fixed_responses import requiere_plantilla_fija


class TestPrioridad:
    def test_orden_del_documento(self) -> None:
        """§29: rojo > negro > amarillo > verde."""
        assert [n.value for n in sorted(UrgencyLevel, key=lambda n: n.priority)] == [
            "rojo",
            "negro",
            "amarillo",
            "verde",
        ]

    def test_las_colas_se_llaman_como_los_niveles(self) -> None:
        """Los nombres de cola de Celery son los valores del enum.

        Si dejan de coincidir, `apply_async(queue=...)` encola en una cola que
        ningún worker consume y la respuesta diferida no se calcula nunca, sin
        dar error.
        """
        from app.tasks.celery_app import celery_app

        colas_declaradas = {"rojo", "negro", "amarillo", "verde"}
        assert {n.value for n in UrgencyLevel} == colas_declaradas
        assert celery_app.conf.task_default_queue in colas_declaradas


class TestDegradacionBajoCarga:
    """§29: rojo y negro nunca pasan por el modelo; el amarillo solo bajo carga."""

    def test_rojo_siempre_plantilla(self) -> None:
        assert requiere_plantilla_fija(UrgencyLevel.ROJO, 0, 32) is True
        assert requiere_plantilla_fija(UrgencyLevel.ROJO, 500, 32) is True

    def test_negro_nunca_pasa_por_el_modelo(self) -> None:
        """§25: no depende de la carga. No se le pregunta al modelo lo que
        tiene prohibido decir, vaya el sistema vacío o saturado."""
        assert requiere_plantilla_fija(UrgencyLevel.NEGRO, 0, 32) is True
        assert requiere_plantilla_fija(UrgencyLevel.NEGRO, 500, 32) is True

    def test_amarillo_solo_bajo_carga(self) -> None:
        assert requiere_plantilla_fija(UrgencyLevel.AMARILLO, 10, 32) is False
        assert requiere_plantilla_fija(UrgencyLevel.AMARILLO, 33, 32) is True

    def test_justo_en_el_umbral_no_degrada(self) -> None:
        """El §29 dice «supera el umbral», no «lo alcanza»."""
        assert requiere_plantilla_fija(UrgencyLevel.AMARILLO, 32, 32) is False


class TestMedicionDeCola:
    """La medida tiene que fallar hacia «no degradar»."""

    def test_sin_valkey_devuelve_cero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Un contador roto no puede dejar a todos con plantillas fijas.

        Es la decisión de diseño del módulo: la degradación protege bajo carga
        real; activarla por un fallo del contador sería una avería silenciosa
        que empeora el servicio sin que nadie lo note.
        """
        import redis

        from app.core import queue

        def explota() -> None:
            raise redis.RedisError("valkey caído")

        monkeypatch.setattr(queue, "_redis", explota)
        assert queue.profundidad() == 0

    def test_en_vuelo_no_rompe_si_falla_valkey(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Medir la carga no puede impedir atender a alguien."""
        import redis

        from app.core import queue

        def explota() -> None:
            raise redis.RedisError("valkey caído")

        monkeypatch.setattr(queue, "_redis", explota)
        with queue.en_vuelo():
            pass  # no debe lanzar

    def test_ttl_mayor_que_el_timeout_del_modelo(self) -> None:
        """Una petición lenta pero viva tiene que seguir contando.

        Si el TTL fuera menor que el timeout del modelo, las peticiones largas
        —justo las que crean la carga— desaparecerían de la cuenta y la
        degradación no se activaría nunca.
        """
        from app.core.config import settings
        from app.core.queue import TTL_SEGUNDOS

        assert TTL_SEGUNDOS > settings.llm_timeout_seconds


class TestModoDiferido:
    """La diferida tiene que aportar algo distinto al acuse."""

    def test_solo_se_difiere_lo_que_quedo_incompleto(self) -> None:
        """La diferida completa una respuesta recortada, no repite una buena.

        Se difiere únicamente lo que el orquestador marca con
        `admite_diferida`, que hoy es solo la plantilla de cola llena. El rojo
        no (§18: su plantilla ya es la respuesta) y `sin ruta verificable`
        tampoco: recalcularla podría contradecir al §20.5, que fija el texto.

        Antes se difería cualquier plantilla fija, y eso descartaba respuestas
        correctas para recalcularlas peor: medido en el servidor, «¿qué llevo
        en la mochila?» perdía su respuesta instantánea y recibía, 80 s
        después, un texto sobre lluvias que nadie había preguntado.
        """
        import inspect

        from app.api.routers import chat

        fuente = inspect.getsource(chat.conversar)
        assert "salida.admite_diferida" in fuente
        assert "respuesta_plantilla_fija and" not in fuente

    def test_el_worker_lo_activa(self) -> None:
        import inspect

        from app.tasks import celery_app

        fuente = inspect.getsource(celery_app.responder_diferido)
        assert "modo_diferido=True" in fuente
