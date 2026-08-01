"""§18 y §32.1.2 / §32.2 — clasificación de urgencia."""

from __future__ import annotations

import pytest

from app.domain import UrgencyLevel
from app.rules.urgency import StructuralSignals, classify, normalize


class TestRojo:
    """§32.2 exige ≥98 % de detección correcta de nivel rojo."""

    @pytest.mark.parametrize(
        "texto,disparador",
        [
            ("Hay dos personas atrapadas en la casa que se cayó", "personas atrapadas"),
            ("mi vecino está sepultado bajo escombros", "personas atrapadas"),
            ("mi hermano está herido grave, no respira", "heridos graves"),
            ("el agua está subiendo muy rápido", "agua subiendo rápido"),
            ("hay cables eléctricos en el agua de la calle", "cables eléctricos en agua"),
            ("se derrumbó la casa del costado", "colapso estructural"),
            ("se cayó el puente sobre el río", "caída de puente"),
            ("nos dieron orden de evacuación", "orden oficial de evacuación"),
        ],
    )
    def test_disparadores_del_documento(self, texto: str, disparador: str) -> None:
        r = classify(texto)
        assert r.nivel is UrgencyLevel.ROJO
        assert disparador in r.disparadores

    def test_rojo_no_pasa_por_el_modelo(self) -> None:
        """§18: «Sin redacción libre del modelo»."""
        assert classify("hay personas atrapadas").usa_plantilla_fija is True

    def test_orden_oficial_gana_sobre_el_texto(self) -> None:
        """§12: una orden oficial prevalece sobre cualquier cálculo propio."""
        r = classify(
            "solo quería saber qué llevar en la mochila",
            StructuralSignals(orden_evacuacion_oficial=True),
        )
        assert r.nivel is UrgencyLevel.ROJO
        assert r.por_senal_estructural is True

    def test_gana_el_nivel_mas_alto(self) -> None:
        r = classify("estoy preparando la mochila pero hay gente atrapada en la esquina")
        assert r.nivel is UrgencyLevel.ROJO

    def test_negacion_no_baja_el_nivel(self) -> None:
        """Sesgo deliberado: un falso positivo de rojo cuesta una plantilla;
        un falso negativo cuesta una persona."""
        assert classify("no hay personas atrapadas").nivel is UrgencyLevel.ROJO


class TestNegro:
    """§25: lo que SENTI no puede responder.

    No es una urgencia, es una frontera. Y se resuelve sin modelo a propósito:
    dejar que redacte sobre lo que tiene prohibido decir es la forma más
    directa de que acabe diciéndolo — basta un «no puedo predecir sismos,
    pero normalmente…» para que la frase siguiente sea una predicción.
    """

    @pytest.mark.parametrize(
        ("texto", "disparador"),
        [
            ("cuando va a haber un sismo en Lima", "predicción de fenómeno natural"),
            ("va a ocurrir un terremoto esta semana", "predicción de fenómeno natural"),
            ("que medicamento le doy a mi hijo", "recomendación de medicamento"),
            ("que dosis de paracetamol", "recomendación de medicamento"),
            ("es segura la via a Chosica", "declarar una vía segura"),
            ("garantizame que puedo pasar sin peligro", "declarar una vía segura"),
            ("confirma este reporte", "cambiar un nivel oficial o confirmar un reporte"),
            ("cambia el nivel de la alerta", "cambiar un nivel oficial o confirmar un reporte"),
        ],
    )
    def test_disparadores(self, texto: str, disparador: str) -> None:
        r = classify(texto)
        assert r.nivel is UrgencyLevel.NEGRO
        assert disparador in r.disparadores

    def test_el_rojo_gana_sobre_el_negro(self) -> None:
        """Primero hay un herido; lo del medicamento se atiende después.

        La plantilla roja no receta nada, así que atender la emergencia no
        supone responder lo prohibido. Al revés sí sería grave: contestar
        «eso no lo puedo responder» a quien avisa de un atrapado.
        """
        r = classify("hay personas atrapadas, que medicamento les doy")
        assert r.nivel is UrgencyLevel.ROJO


class TestAmarilloYVerde:
    def test_lluvia_fuerte_es_amarillo(self) -> None:
        assert classify("está lloviendo muy fuerte desde ayer").nivel is UrgencyLevel.AMARILLO

    def test_imagen_ambigua_es_amarillo(self) -> None:
        r = classify("te mando esta foto", StructuralSignals(imagen_ambigua=True, tiene_imagen=True))
        assert r.nivel is UrgencyLevel.AMARILLO

    def test_reporte_no_confirmado_es_amarillo(self) -> None:
        assert classify("dicen que la vía está mala").nivel is UrgencyLevel.AMARILLO

    @pytest.mark.parametrize(
        "texto",
        [
            "¿qué debo llevar en la mochila de emergencia?",
            "quiero armar mi plan familiar",
            "¿qué significa alerta naranja?",
        ],
    )
    def test_verde(self, texto: str) -> None:
        assert classify(texto).nivel is UrgencyLevel.VERDE

    def test_texto_vacio_es_verde(self) -> None:
        assert classify("").nivel is UrgencyLevel.VERDE


class TestNormalizacion:
    def test_quita_tildes_y_baja_a_minusculas(self) -> None:
        assert normalize("Está ATRAPÁDO") == "esta atrapado"

    def test_clasifica_igual_con_y_sin_tildes(self) -> None:
        assert (
            classify("el agua esta subiendo rapido").nivel
            is classify("el agua está subiendo rápido").nivel
        )


def test_prioridad_de_cola_del_documento() -> None:
    """§29: rojo > negro > amarillo > verde.

    El negro va segundo aunque no consulte nada: si el sistema está saturado,
    contestar «esto no lo puedo responder» cuesta cero y libera al ciudadano
    para que llame a quien sí puede.
    """
    niveles = sorted(UrgencyLevel, key=lambda n: n.priority)
    assert niveles == [
        UrgencyLevel.ROJO,
        UrgencyLevel.NEGRO,
        UrgencyLevel.AMARILLO,
        UrgencyLevel.VERDE,
    ]
