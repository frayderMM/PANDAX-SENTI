"""Reglas del canal de WhatsApp (§10.1, §13.4).

Lo que se prueba aquí no es que Evolution funcione —eso es de ellos— sino que
SENTI no haga las cuatro cosas que convierten un canal de emergencia en un
problema: contestarse a sí mismo, repetir mensajes, aceptar peticiones de
cualquiera y tratar datos de un grupo entero.
"""

from __future__ import annotations

import pytest

from app.api.routers import whatsapp as wa
from app.channels.whatsapp import normalizar_numero


class TestNumero:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("51987654321", "51987654321"),
            ("+51 987-654-321", "51987654321"),
            ("  51 987 654 321  ", "51987654321"),
        ],
    )
    def test_un_numero_suelto_se_limpia(self, entrada: str, esperado: str) -> None:
        assert normalizar_numero(entrada) == esperado

    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("925650163", "51925650163"),
            ("925297709", "51925297709"),
            ("973791546", "51973791546"),
        ],
    )
    def test_un_celular_peruano_sin_codigo_de_pais_lo_recibe(
        self, entrada: str, esperado: str
    ) -> None:
        """`AlertSubscriber.telefono` se guarda tal como lo escribe la persona
        al registrarse: "925650163", no "51925650163". Sin este paso, Evolution
        recibe 9 dígitos que no resuelven a ningún JID y el mensaje no llega —
        sin que el envío lance ningún error que lo delate."""
        assert normalizar_numero(entrada) == esperado

    def test_un_numero_de_9_digitos_que_no_empieza_en_9_no_se_toca(self) -> None:
        # Todo celular peruano empieza en 9; esto no es uno, así que no se
        # inventa un país que nadie pidió.
        assert normalizar_numero("812345678") == "812345678"

    @pytest.mark.parametrize(
        "jid",
        [
            "51925650163@s.whatsapp.net",
            "140368842588179@lid",
        ],
    )
    def test_un_jid_se_devuelve_intacto(self, jid: str) -> None:
        """WhatsApp ya no siempre identifica por teléfono.

        Un LID no es un número y no se puede convertir en uno. Recortarle el
        sufijo daba quince dígitos que Evolution rechaza con `exists: false`:
        el bot redactaba la respuesta, la guardaba y **no la entregaba**. Es el
        peor fallo posible en este canal, porque desde dentro parece que todo
        fue bien.
        """
        assert normalizar_numero(jid) == jid

    @pytest.mark.parametrize("basura", ["", "hola", "12", "5" * 20, "@lid"])
    def test_lo_que_no_puede_ser_un_destinatario_se_rechaza_antes_de_salir(
        self, basura: str
    ) -> None:
        # Mandarlo a Evolution devuelve un 400 que nadie mira, y el mensaje se
        # pierde en silencio.
        with pytest.raises(ValueError):
            normalizar_numero(basura)


class TestExtraccionDelEvento:
    def test_texto_plano(self) -> None:
        assert wa._texto_del_mensaje({"conversation": "hay un huaico"}) == "hay un huaico"

    def test_texto_citando_otro_mensaje(self) -> None:
        mensaje = {"extendedTextMessage": {"text": "¿por dónde salgo?"}}
        assert wa._texto_del_mensaje(mensaje) == "¿por dónde salgo?"

    def test_pie_de_foto(self) -> None:
        # §25: la imagen se observa, y el pie suele ser la pregunta de verdad.
        mensaje = {"imageMessage": {"caption": "¿esto se puede cruzar?"}}
        assert wa._texto_del_mensaje(mensaje) == "¿esto se puede cruzar?"

    def test_sin_texto_utilizable(self) -> None:
        assert wa._texto_del_mensaje({"audioMessage": {}}) is None
        assert wa._texto_del_mensaje({"conversation": "   "}) is None

    def test_la_ubicacion_llega_como_coordenadas(self) -> None:
        # La ubicación siempre son lat/lon del teléfono, nunca una dirección
        # escrita: por eso no hay geocodificación en todo el sistema.
        mensaje = {"locationMessage": {"degreesLatitude": -11.94, "degreesLongitude": -76.70}}
        assert wa._ubicacion_del_mensaje(mensaje) == (-11.94, -76.70)

    def test_ubicacion_en_vivo_tambien(self) -> None:
        mensaje = {"liveLocationMessage": {"degreesLatitude": -12.1, "degreesLongitude": -77.0}}
        assert wa._ubicacion_del_mensaje(mensaje) == (-12.1, -77.0)

    def test_sin_ubicacion(self) -> None:
        assert wa._ubicacion_del_mensaje({"conversation": "hola"}) is None


class TestLaUbicacionSeRecuerda:
    """En WhatsApp la ubicación y la pregunta son mensajes distintos.

    Se comparte el punto y a continuación se escribe «¿por dónde salgo?». Si no
    se recuerda, la pregunta llega sin coordenadas y el sistema vuelve a pedir
    lo que le acaban de dar — que es exactamente lo que pasó en la primera
    prueba real.
    """

    def test_el_plazo_de_reutilizacion_es_el_de_la_retencion(self) -> None:
        from datetime import timedelta

        from app.rules.retention import PLAZOS, RetentionPolicy

        # Reutilizar más allá del plazo del §13.5 sería guardar una ubicación
        # exacta más tiempo del permitido. Y además sería peligroso: dónde
        # estaba alguien hace tres días no dice dónde está en una emergencia.
        assert PLAZOS[RetentionPolicy.UBICACION_EXACTA] == timedelta(hours=72)

    def test_la_conversacion_tiene_donde_guardarla(self) -> None:
        from app.models import Conversation

        for columna in ("ultima_lat", "ultima_lon", "ubicacion_at"):
            assert columna in Conversation.__table__.columns

    def test_el_borrado_de_las_72h_esta_en_las_migraciones(self) -> None:
        # `create_all` no altera tablas existentes: sin la migración, un
        # despliegue con datos se queda sin las columnas y revienta al recibir
        # la primera ubicación.
        from app.db.bootstrap import MIGRACIONES

        texto = " ".join(MIGRACIONES)
        for columna in ("ultima_lat", "ultima_lon", "ubicacion_at"):
            assert columna in texto


class TestLaTareaEsImportable:
    """La tarea del worker importa dentro de la función, y eso se le escapa a
    `ruff`: un módulo equivocado en un import diferido no rompe nada hasta que
    llega el primer mensaje de un ciudadano.

    Ya pasó: `RetentionPolicy` se importaba de `app.domain`, donde no está. El
    webhook encolaba bien, el worker reventaba, y nadie recibía respuesta.
    """

    def test_los_imports_diferidos_resuelven(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.tasks import celery_app as tareas

        class Corta(RuntimeError):
            """Marca que se llegó más allá del bloque de imports."""

        def _explota() -> None:
            raise Corta

        # SessionLocal es lo primero que se usa tras los imports. Si el bloque
        # de imports estuviera roto, saltaría ImportError antes que esto.
        monkeypatch.setattr(tareas, "SessionLocal", _explota)

        with pytest.raises(Corta):
            tareas.atender_whatsapp.run(remitente="51925650163", texto="hola")
