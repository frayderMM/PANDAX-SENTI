"""§29 y RF-22 — el nivel rojo responde con el modelo apagado."""

from __future__ import annotations

import pytest

from app.domain import UrgencyLevel
from app.rules import fixed_responses as fx
from app.rules.urgency import classify


class TestModeloApagado:
    """RF-22: «Responder nivel rojo con el modelo apagado»."""

    @pytest.mark.parametrize("disparador", sorted(fx.RESPUESTAS_ROJAS))
    def test_cada_disparador_rojo_tiene_respuesta_completa(self, disparador: str) -> None:
        r = fx.RESPUESTAS_ROJAS[disparador]
        texto = r.render()
        # §18: la respuesta roja lleva acciones, teléfono, ubicación y escalamiento.
        assert r.acciones
        assert r.telefono
        assert "Envíame tu ubicación" in texto
        assert fx.SEGUIR_AUTORIDADES in texto

    def test_todo_disparador_del_clasificador_tiene_respuesta(self) -> None:
        """Ningún disparador rojo del §18 puede quedarse sin plantilla."""
        casos = [
            "hay personas atrapadas",
            "está herido grave",
            "el agua está subiendo rápido",
            "hay cables eléctricos en el agua",
            "se derrumbó la casa",
            "se cayó el puente",
            "orden de evacuación",
        ]
        for texto in casos:
            r = classify(texto)
            assert r.nivel is UrgencyLevel.ROJO
            respuesta = fx.responder_rojo(r.disparadores)
            assert respuesta is not fx.ROJA_GENERICA, f"sin plantilla: {texto}"

    def test_disparador_desconocido_cae_a_generica(self) -> None:
        """Que un caso nuevo caiga en la genérica es aceptable; que no haya
        respuesta, no."""
        assert fx.responder_rojo(("algo que no existe",)) is fx.ROJA_GENERICA
        assert fx.ROJA_GENERICA.render()

    def test_no_hay_llamadas_de_red_ni_formato_dinamico(self) -> None:
        """El render de una respuesta roja no depende de nada externo."""
        r = fx.RESPUESTAS_ROJAS["personas atrapadas"]
        assert r.render() == r.render()


class TestCargaYCola:
    """§29: comportamiento bajo carga."""

    def test_rojo_siempre_usa_plantilla(self) -> None:
        assert fx.requiere_plantilla_fija(UrgencyLevel.ROJO, 0, 32) is True
        assert fx.requiere_plantilla_fija(UrgencyLevel.ROJO, 1000, 32) is True

    def test_amarillo_cae_a_plantilla_solo_bajo_carga(self) -> None:
        umbral = 32
        assert fx.requiere_plantilla_fija(UrgencyLevel.AMARILLO, umbral + 1, umbral) is True
        assert fx.requiere_plantilla_fija(UrgencyLevel.AMARILLO, umbral, umbral) is False

    def test_negro_nunca_pasa_por_el_modelo(self) -> None:
        """§25: no se le pregunta al modelo lo que tiene prohibido decir."""
        assert fx.requiere_plantilla_fija(UrgencyLevel.NEGRO, 0, 32) is True

    @pytest.mark.parametrize("nivel", [UrgencyLevel.VERDE])
    def test_el_verde_no_cae_a_plantilla_por_carga(self, nivel: UrgencyLevel) -> None:
        """§29: reciben acuse y respuesta diferida, que es otra cosa."""
        assert fx.requiere_plantilla_fija(nivel, 1000, 32) is False


class TestTextosLiterales:
    """Textos que el documento fija palabra por palabra."""

    def test_sin_senal_menciona_los_requisitos_del_enlace_satelital(self) -> None:
        # §7.5 y §7.1: espacio abierto, roaming y VoLTE.
        for fragmento in ("espacio abierto", "roaming", "VoLTE", "satélite", "WhatsApp"):
            assert fragmento in fx.SIN_SENAL

    def test_sin_ruta_verificable_lleva_los_tres_telefonos(self) -> None:
        # §20.5, literal.
        for numero in ("110", "0800-12345", "115"):
            assert numero in fx.SIN_RUTA_VERIFICABLE
        assert "No intentes cruzar el bloqueo" in fx.SIN_RUTA_VERIFICABLE

    def test_consentimiento_declara_plazos_y_permite_negarse(self) -> None:
        # §13.4.
        assert "72 h" in fx.CONSENTIMIENTO_WHATSAPP
        assert "30 días" in fx.CONSENTIMIENTO_WHATSAPP
        assert "Puedes decir NO" in fx.CONSENTIMIENTO_WHATSAPP
        assert "ACEPTO" in fx.CONSENTIMIENTO_WHATSAPP

    def test_alerta_no_verificable_remite_al_canal_oficial(self) -> None:
        # §12: ante una alerta cuyo origen no puede verificarse.
        assert "No puedo confirmar" in fx.ALERTA_NO_VERIFICABLE
        assert "gob.pe" in fx.ALERTA_NO_VERIFICABLE

    def test_sin_sesion_no_presenta_la_falta_de_dato_como_ausencia_de_peligro(self) -> None:
        """§13.4 y §11.3.

        Es la regla que el sistema no puede romper en ningún camino: no tener
        el dato no es lo mismo que no haya peligro. El invitado se queda sin
        herramientas, así que es justo donde resulta más fácil dejar entender
        que no pasa nada.
        """
        assert "no significa que no haya peligro" in fx.SIN_SESION_PARA_ZONA
        assert "115" in fx.SIN_SESION_PARA_ZONA
        # Y no puede afirmar lo contrario ni de refilón.
        for prohibido in ("no hay alerta", "está seguro", "es seguro", "sin peligro"):
            assert prohibido not in fx.SIN_SESION_PARA_ZONA.lower()


class TestRespuestasSimples:
    def test_saludo_no_usa_modelo(self) -> None:
        assert fx.respuesta_conversacional_simple("hola") == fx.SALUDO_SIMPLE
        assert fx.respuesta_conversacional_simple("Buenas tardes!") == fx.SALUDO_SIMPLE

    def test_no_atrapa_mensaje_con_incidente(self) -> None:
        assert fx.respuesta_conversacional_simple("hola hay huaico en mi calle") is None

    def test_ayuda_y_gracias(self) -> None:
        assert fx.respuesta_conversacional_simple("ayuda") == fx.AYUDA_SIMPLE
        assert fx.respuesta_conversacional_simple("muchas gracias") == fx.AGRADECIMIENTO_SIMPLE

    def test_mochila_de_emergencia_no_usa_modelo(self) -> None:
        assert (
            fx.respuesta_conversacional_simple("que debo preparar en mi mochila de emergencia")
            == fx.MOCHILA_EMERGENCIA
        )
