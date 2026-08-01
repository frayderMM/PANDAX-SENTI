"""Router de intención: cada mensaje va a una sola herramienta, sin modelo."""

from __future__ import annotations

import pytest

from app.orchestrator.router import (
    HERRAMIENTA,
    Intent,
    argumentos_por_defecto,
    rutear,
)
from app.orchestrator.tools import registry


class TestRuteo:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("¿Cómo llego al centro de salud?", Intent.RUTA),
            ("¿hay otra ruta para salir de acá?", Intent.RUTA),
            ("¿dónde hay un refugio cerca?", Intent.RECURSOS),
            ("¿qué llevo en la mochila?", Intent.PLAN),
            ("quiero armar mi plan familiar", Intent.PLAN),
            ("¿hay alerta en mi distrito?", Intent.ALERTA),
            ("¿la avenida principal está bloqueada?", Intent.REPORTE),
            ("¿de dónde sacas esa información?", Intent.FUENTES),
            ("¿qué sabes de mi hogar?", Intent.PERFIL),
            ("quiero guardar esto sin conexión", Intent.OFFLINE),
            ("necesito avisar a mi familiar", Intent.CONTACTO),
        ],
    )
    def test_intenciones(self, texto: str, esperado: Intent) -> None:
        assert rutear(texto).intent is esperado

    def test_sin_coincidencia_es_general(self) -> None:
        r = rutear("hola, buenas tardes")
        assert r.intent is Intent.GENERAL
        assert r.necesita_herramienta is False

    def test_texto_vacio_no_revienta(self) -> None:
        assert rutear("").intent is Intent.GENERAL

    def test_funciona_sin_tildes(self) -> None:
        assert rutear("como llego al hospital").intent is rutear(
            "¿cómo llego al hospital?"
        ).intent

    def test_la_imagen_gana_sobre_el_texto(self) -> None:
        """§25: con foto lo que toca es describir lo que se ve, no consultar."""
        r = rutear("¿hay alerta en mi zona?", tiene_imagen=True)
        assert r.intent is Intent.IMAGEN
        assert r.necesita_herramienta is False

    def test_ruta_gana_sobre_recursos(self) -> None:
        """«¿cómo llego al centro de salud?» es una ruta, no una búsqueda."""
        assert rutear("¿cómo llego al centro de salud más cercano?").intent is Intent.RUTA

    def test_el_motivo_explica_la_decision(self) -> None:
        assert "coincide" in rutear("¿hay alerta?").motivo


class TestContrato:
    def test_toda_herramienta_ruteada_existe_en_el_registro(self) -> None:
        """Un router que apunta a una herramienta inexistente falla en caliente."""
        for intent, nombre in HERRAMIENTA.items():
            if nombre is not None:
                assert nombre in registry, f"{intent.value} apunta a '{nombre}', que no existe"

    def test_todo_intent_esta_mapeado(self) -> None:
        for intent in Intent:
            assert intent in HERRAMIENTA


class TestArgumentos:
    def test_alerta_usa_el_distrito_del_perfil(self) -> None:
        a = argumentos_por_defecto(Intent.ALERTA, distrito="Lurigancho-Chosica")
        assert a == {"zona": "Lurigancho-Chosica"}

    def test_recursos_necesita_ubicacion(self) -> None:
        assert argumentos_por_defecto(Intent.RECURSOS) == {}
        a = argumentos_por_defecto(Intent.RECURSOS, lat=-11.94, lon=-76.70, texto="refugio")
        assert a["tipo"] == "refugio"

    def test_recursos_por_defecto_es_centro_de_salud(self) -> None:
        a = argumentos_por_defecto(Intent.RECURSOS, lat=-11.9, lon=-76.7, texto="donde hay ayuda")
        assert a["tipo"] == "centro_salud"

    @pytest.mark.parametrize(
        ("texto", "tipo"),
        [
            ("hospital público más cercano", "hospital_publico"),
            ("hospital privado más cercano", "hospital_privado"),
            ("bomberos más cercano", "bomberos"),
            ("hospital más cercano", "hospital_preguntar"),
        ],
    )
    def test_recursos_pide_o_aplica_tipo(self, texto: str, tipo: str) -> None:
        args = argumentos_por_defecto(Intent.RECURSOS, lat=-11.9, lon=-76.7, texto=texto)
        assert args["tipo"] == tipo

    def test_recursos_con_nombre_no_pregunta_publico_privado(self) -> None:
        args = argumentos_por_defecto(
            Intent.RECURSOS,
            lat=-11.9,
            lon=-76.7,
            texto="quiero ir al hospital Rebagliati",
        )
        assert args["tipo"] == "centro_salud"
        assert args["nombre"] == "rebagliati"

    def test_consulta_telefono_no_se_manda_al_rag(self) -> None:
        assert rutear("¿Cuál es el número de emergencia de los bomberos?").intent is Intent.TELEFONOS

    def test_consulta_telefono_acepta_plural_cotidiano(self) -> None:
        assert rutear("¿cuál es el número de bomberos?").intent is Intent.TELEFONOS

    def test_variantes_viales_y_sin_senal_se_rutean(self) -> None:
        assert rutear("la pista está bloqueada por un derrumbe").intent is Intent.REPORTE
        assert rutear("no tengo señal, ¿qué hago?").intent is Intent.OFFLINE

    def test_reporte_extrae_la_via(self) -> None:
        a = argumentos_por_defecto(Intent.REPORTE, texto="¿la avenida Central está bloqueada?")
        assert "central" in a["via"].lower()

    def test_reporte_sin_via_devuelve_el_texto(self) -> None:
        """Vacío no encontraría nada; el texto completo sí busca por coincidencia."""
        assert argumentos_por_defecto(Intent.REPORTE, texto="se puede pasar?")["via"]


def test_ahorro_de_prompt() -> None:
    """El router existe para no mandar los esquemas de las diez herramientas.

    Se comprueba el orden de magnitud, no un número exacto: el test debe seguir
    valiendo si se añade una herramienta más.
    """
    import json

    from app.core.security import Role

    todas = len(json.dumps(registry.esquemas_para(Role.CIUDADANO), ensure_ascii=False))
    una = len(json.dumps(registry.get("consultar_alerta_actual").openai_schema(), ensure_ascii=False))
    assert una < todas / 3


def test_numeros_emergencia_verificados_y_no_intercambiados() -> None:
    from app.rules.phones import NACIONALES

    contactos = {c.entidad: c.numero for c in NACIONALES}
    assert contactos["PNP"] == "105"
    assert contactos["SAMU"] == "106"
    assert contactos["Cuerpo General de Bomberos"] == "116"
    assert contactos["INDECI"] == "115"


class TestBusquedaWeb:
    """§11.2: la fuente la elige una tabla por tema, nunca el modelo."""

    def test_pronostico_va_a_senamhi(self) -> None:
        """El §11.2 asigna lluvia y avisos meteorológicos a SENAMHI."""
        for m in ["¿va a llover mañana?", "búscame el pronóstico de Lima",
                  "¿habrá lluvia el 31 de julio?"]:
            r = rutear(m)
            assert r.intent is Intent.WEB, m
            assert "senamhi" in argumentos_por_defecto(r.intent, texto=m)["url"]

    def test_sismo_va_a_igp(self) -> None:
        mensaje = "noticias del sismo de hoy"
        r = rutear(mensaje)
        assert "igp" in argumentos_por_defecto(r.intent, texto=mensaje)["url"]

    def test_la_url_siempre_es_gob_pe(self) -> None:
        """§12: nunca se envían dominios ajenos a gob.pe o al propio."""
        from app.orchestrator.router import URL_OFICIAL_POR_DEFECTO, _URL_POR_TEMA

        for _, url in _URL_POR_TEMA:
            assert ".gob.pe" in url, url
        assert ".gob.pe" in URL_OFICIAL_POR_DEFECTO

    def test_los_argumentos_encajan_con_la_herramienta(self) -> None:
        """Enviaba `consulta` y la herramienta esperaba `url`.

        Los argumentos no validaban, la búsqueda no se ejecutaba nunca y el
        usuario recibía "no pude verificar información oficial" ante una
        pregunta de pronóstico que sí se podía consultar.
        """
        args = argumentos_por_defecto(Intent.WEB, texto="¿va a llover?")
        spec = registry.get("consultar_web_oficial")
        spec.args_model.model_validate(args)


class TestFormasDePedirRuta:
    """Formas reales de pedir una ruta, no solo la de manual.

    "dame una ruta de escape" caía en intención general porque el patrón solo
    contemplaba "ruta hacia/para/a". Quien huye de un incendio no construye la
    frase con la preposición correcta.
    """

    @pytest.mark.parametrize(
        "texto",
        [
            "dame una ruta de escape",
            "dame una ruta de salida",
            "sácame de aquí",
            "por dónde escapo",
            "cómo salgo de acá",
            "necesito evacuar",
            "hacia dónde voy",
            "¿qué ruta tomo?",
        ],
    )
    def test_todas_rutean_a_ruta(self, texto: str) -> None:
        assert rutear(texto).intent is Intent.RUTA, texto

    def test_con_ubicacion_no_hace_falta_destino(self) -> None:
        """§34.2: sin destino explícito se va al recurso validado más cercano."""
        a = argumentos_por_defecto(Intent.RUTA, lat=-11.94, lon=-76.70, texto="ruta de escape")
        assert a["hacia_refugio"] is True
        assert a["origen_lat"] == -11.94

    def test_sin_ubicacion_no_inventa_origen(self) -> None:
        assert argumentos_por_defecto(Intent.RUTA, texto="ruta de escape") == {}
