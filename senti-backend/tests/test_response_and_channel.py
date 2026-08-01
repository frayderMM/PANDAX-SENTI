"""§24 (orden y lenguaje), §7.4 (modo ligero) y §13.5 (retención)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain import OperationLevel
from app.rules import light_mode as lm
from app.rules import phones, retention
from app.rules.response import (
    FORMULA_RUTA,
    LanguageViolation,
    Respuesta,
    SourceCitation,
    exigir_lenguaje_admisible,
    revisar_lenguaje,
)

AHORA = datetime(2026, 7, 29, 20, 35, tzinfo=UTC)


class TestLenguajeProhibido:
    """§20.5 y §25: lo que el sistema nunca dice."""

    @pytest.mark.parametrize(
        "texto",
        [
            "Esta ruta es completamente segura.",
            "La vía está segura, puedes ir tranquilo.",
            "No hay ningún peligro en tu zona.",
            "La carretera está libre por el lado izquierdo.",
            "Va a haber un sismo mañana.",
        ],
    )
    def test_rechaza(self, texto: str) -> None:
        assert revisar_lenguaje(texto)
        with pytest.raises(LanguageViolation):
            exigir_lenguaje_admisible(texto)

    @pytest.mark.parametrize(
        "texto",
        [
            FORMULA_RUTA,
            "Se observa material sobre parte de la vía.",
            "Encontré una ruta alternativa que evita el tramo reportado.",
            "No pude verificar una ruta transitable.",
        ],
    )
    def test_acepta(self, texto: str) -> None:
        assert revisar_lenguaje(texto) == []
        assert exigir_lenguaje_admisible(texto) == texto

    def test_la_formula_correcta_del_documento_pasa(self) -> None:
        """§20.5: «Usar: Esta es la ruta de menor riesgo según la información
        disponible y su última actualización.»"""
        assert revisar_lenguaje(FORMULA_RUTA) == []


class TestOrdenFijo:
    """§24.1: 1 nivel · 2 acción · 3 resultado oficial · 4 ruta · 5 fuente ·
    6 hora · 7 limitación."""

    def test_orden_del_ejemplo_del_documento(self) -> None:
        r = Respuesta(
            nivel_o_advertencia="⚠️ Posible bloqueo por huaico.",
            accion_inmediata="No intentes cruzar el material.",
            ruta_o_instruccion="Encontré una ruta alternativa que evita el tramo reportado.",
            fuentes=[SourceCitation("SUTRAN y validación municipal")],
            hora_actualizacion=AHORA,
            limitacion="Las condiciones pueden cambiar.",
        )
        lineas = r.render().splitlines()
        assert lineas[0].startswith("⚠️")
        assert lineas[1] == "No intentes cruzar el material."
        assert "ruta alternativa" in lineas[2]
        assert lineas[3].startswith("Fuente:")
        assert lineas[4].startswith("Actualización:")
        assert lineas[5] == "Las condiciones pueden cambiar."

    def test_omite_vacios_sin_alterar_el_orden(self) -> None:
        r = Respuesta(
            nivel_o_advertencia="Aviso.",
            fuentes=[SourceCitation("SENAMHI")],
            hora_actualizacion=AHORA,
        )
        lineas = r.render().splitlines()
        assert lineas == ["Aviso.", "Fuente: SENAMHI", "Actualización: 29/07 20:35."]

    def test_limitacion_automatica_cuando_hay_ruta(self) -> None:
        """§24.2: el mensaje de seguridad no es opcional."""
        r = Respuesta(ruta_o_instruccion="Sigue por la avenida secundaria.")
        assert "Las condiciones pueden cambiar." in r.render()

    def test_resultado_oficial_sin_fuente_es_invalido(self) -> None:
        """§32.2: 0 % de respuestas con afirmación no respaldada por fuente."""
        with pytest.raises(ValueError, match="debe citar su fuente"):
            Respuesta(resultado_oficial="Alerta naranja vigente.").validar()

    def test_fuente_sin_hora_es_invalida(self) -> None:
        """§32.2: 100 % de respuestas que citan fuente y hora verificables."""
        with pytest.raises(ValueError, match="hora de actualización"):
            Respuesta(
                resultado_oficial="Alerta naranja vigente.",
                fuentes=[SourceCitation("SENAMHI")],
            ).validar()

    def test_respuesta_completa_valida(self) -> None:
        Respuesta(
            nivel_o_advertencia="⚠️ Alerta naranja por lluvias.",
            resultado_oficial="La alerta incluye tu zona.",
            fuentes=[SourceCitation("SENAMHI", url="https://www.senamhi.gob.pe")],
            hora_actualizacion=AHORA,
        ).validar()

    def test_fuente_no_vigente_se_declara(self) -> None:
        """§11.4: sin vigencia se usa como orientación general y así se declara."""
        c = SourceCitation("COEN", vigente=False)
        assert "referencia histórica" in c.render()


class TestModoLigero:
    """§7.4."""

    def test_activacion_por_dos_fallos_de_media(self) -> None:
        a = lm.debe_activar_modo_ligero(fallos_media_consecutivos=2)
        assert a.activo and "dos veces seguidas" in a.motivo

    def test_un_solo_fallo_no_activa(self) -> None:
        assert lm.debe_activar_modo_ligero(fallos_media_consecutivos=1).activo is False

    def test_activacion_por_latencia(self) -> None:
        assert lm.debe_activar_modo_ligero(latencia_ms=9000.0).activo is True

    def test_activacion_por_peticion_del_usuario(self) -> None:
        assert lm.debe_activar_modo_ligero(solicitado_por_usuario=True).activo is True

    def test_activacion_por_falta_de_senal_d2c(self) -> None:
        assert lm.debe_activar_modo_ligero(reporta_falta_senal_d2c=True).activo is True

    def test_n2_recorta_a_600_caracteres(self) -> None:
        texto = "\n".join(f"Instrucción número {i} del plan." for i in range(60))
        r = lm.adaptar(texto, OperationLevel.N2_SATELITE)
        assert len(r.texto) <= lm.MAX_CARACTERES_N2
        assert r.truncado is True

    def test_n2_no_parte_una_instruccion_por_la_mitad(self) -> None:
        texto = "\n".join(f"Instrucción número {i} del plan familiar." for i in range(60))
        r = lm.adaptar(texto, OperationLevel.N2_SATELITE)
        assert not r.texto.endswith("Instrucción número")
        assert r.texto.splitlines()[-1].endswith(".")

    def test_n2_quita_enlaces(self) -> None:
        """§7.3: ninguna instrucción crítica depende de abrir un enlace."""
        r = lm.adaptar(
            "Sigue por la avenida. Mapa: https://senti.pe/m/abc", OperationLevel.N2_SATELITE
        )
        assert "http" not in r.texto
        assert "Sigue por la avenida." in r.texto

    def test_n2_maximo_seis_pasos(self) -> None:
        pasos = [f"Paso {i}" for i in range(12)]
        r = lm.adaptar("Ruta", OperationLevel.N2_SATELITE, pasos_ruta=pasos)
        assert len(r.pasos_ruta) == lm.MAX_PASOS_RUTA_N2

    def test_n2_sin_botones(self) -> None:
        assert lm.adaptar("x", OperationLevel.N2_SATELITE).incluir_botones is False

    def test_n2_omite_mapa_grande(self) -> None:
        r = lm.adaptar(
            "Ruta", OperationLevel.N2_SATELITE, tiene_mapa=True, bytes_mapa=150 * 1024
        )
        assert r.incluir_mapa is False

    def test_n2_admite_mapa_de_30kb(self) -> None:
        r = lm.adaptar("Ruta", OperationLevel.N2_SATELITE, tiene_mapa=True, bytes_mapa=28 * 1024)
        assert r.incluir_mapa is True

    def test_n0_conserva_todo(self) -> None:
        r = lm.adaptar(
            "Ruta con enlace https://senti.pe/m/abc",
            OperationLevel.N0_NORMAL,
            tiene_mapa=True,
            bytes_mapa=140 * 1024,
        )
        assert r.incluir_mapa is True
        assert r.incluir_botones is True
        assert "https" in r.texto

    def test_n3_sin_red_no_ofrece_enlaces(self) -> None:
        r = lm.adaptar("Plan guardado https://senti.pe/x", OperationLevel.N3_SIN_RED)
        assert "http" not in r.texto


class TestTelefonos:
    """§24.3."""

    def test_tabla_nacional_completa(self) -> None:
        numeros = {c.numero for c in phones.NACIONALES}
        assert numeros == {"110", "0800-12345", "115", "105", "116", "106", "117"}

    def test_911_solo_en_lima_y_callao_y_declarado_en_pruebas(self) -> None:
        lima = phones.para_region(phones.REGION_LIMA_CALLAO)
        assert lima[0].numero == "911"
        assert "pruebas" in lima[0].situacion
        assert "911" not in {c.numero for c in phones.para_region(phones.REGION_NACIONAL)}

    def test_region_desconocida_cae_a_nacional(self) -> None:
        assert phones.para_region("PE-XYZ") == phones.NACIONALES

    def test_region_nula_cae_a_nacional(self) -> None:
        assert phones.para_region(None) == phones.NACIONALES


class TestRetencion:
    """§13.5."""

    def test_plazos_del_documento(self) -> None:
        P = retention.RetentionPolicy
        assert retention.PLAZOS[P.UBICACION_EXACTA] == timedelta(hours=72)
        assert retention.PLAZOS[P.UBICACION_DISTRITO] == timedelta(days=365)
        assert retention.PLAZOS[P.FOTOGRAFIA_REPORTE] == timedelta(days=30)
        assert retention.PLAZOS[P.MENSAJES] == timedelta(days=365)
        assert retention.PLAZOS[P.AUDITORIA] == timedelta(days=730)
        assert retention.PLAZOS[P.PERFIL_HOGAR] is None

    def test_ubicacion_exacta_expira_en_72h(self) -> None:
        assert retention.expira_en(
            retention.RetentionPolicy.UBICACION_EXACTA, AHORA
        ) == AHORA + timedelta(hours=72)

    def test_foto_se_borra_al_resolverse_si_es_antes(self) -> None:
        resuelto = AHORA + timedelta(days=3)
        assert retention.expira_foto(AHORA, resuelto) == resuelto

    def test_foto_no_pasa_de_30_dias_aunque_siga_abierto(self) -> None:
        assert retention.expira_foto(AHORA, None) == AHORA + timedelta(days=30)

    def test_resolucion_tardia_no_alarga_el_plazo(self) -> None:
        tarde = AHORA + timedelta(days=40)
        assert retention.expira_foto(AHORA, tarde) == AHORA + timedelta(days=30)

    def test_plazo_anpd_es_48h(self) -> None:
        """§13.1 y §13.6: notificación de brechas en 48 horas."""
        assert retention.PLAZO_NOTIFICACION_ANPD == timedelta(hours=48)

    def test_aviso_mis_datos_declara_todos_los_plazos(self) -> None:
        texto = retention.AvisoRetencion.completo().render()
        assert "72 horas" in texto
        assert "30 días" in texto
        # §13.5, literal: «Ninguna imagen ni conversación se usa para entrenar modelos».
        assert "Ninguna imagen ni conversación se usa para entrenar modelos" in texto


class TestFuentesFueraDelCuerpo:
    """Las fuentes salen del texto solo donde hay interfaz para mostrarlas."""

    def test_con_interfaz_el_cuerpo_no_las_lleva(self) -> None:
        r = Respuesta(
            resultado_oficial="Alerta naranja por lluvias.",
            fuentes=[SourceCitation("SENAMHI")],
            hora_actualizacion=AHORA,
        )
        texto = r.render(incluir_fuentes=False)
        assert "SENAMHI" not in texto
        assert "Actualización" not in texto
        assert "Alerta naranja por lluvias." in texto

    def test_sin_interfaz_siguen_dentro(self) -> None:
        """§7.3: en WhatsApp y modo ligero no hay dónde pulsar."""
        r = Respuesta(
            resultado_oficial="Alerta naranja por lluvias.",
            fuentes=[SourceCitation("SENAMHI")],
            hora_actualizacion=AHORA,
        )
        texto = r.render(incluir_fuentes=True)
        assert "SENAMHI" in texto
        assert "Actualización" in texto

    def test_la_validacion_del_322_sigue_exigiendolas(self) -> None:
        """Sacarlas del cuerpo no las hace opcionales: solo cambia dónde se ven."""
        with pytest.raises(ValueError, match="hora de actualización"):
            Respuesta(
                resultado_oficial="Alerta naranja.",
                fuentes=[SourceCitation("SENAMHI")],
            ).validar()


class TestEnlaceAlMapa:
    """§7.3: en WhatsApp no hay botón, así que el enlace va en el texto."""

    LIMA = (-12.043180123, -77.028240987)

    def test_lleva_ruta_a_pie_y_recorta_decimales(self) -> None:
        from app.rules.light_mode import enlace_mapa

        u = enlace_mapa(*self.LIMA)
        assert u.startswith("https://www.google.com/maps/dir/?api=1")
        assert "travelmode=walking" in u
        # Cinco decimales: un metro basta y sobran veinte caracteres que en N2
        # cuentan contra el límite de 600.
        assert "destination=-12.04318,-77.02824" in u

    def test_a_pie_y_no_en_coche(self) -> None:
        """Casi toda evacuación de este sistema es caminando; una ruta en coche
        por una avenida inundada es peor que ninguna."""
        from app.rules.light_mode import enlace_mapa

        assert "driving" not in enlace_mapa(*self.LIMA)

    def test_solo_whatsapp(self) -> None:
        """La app recibe `lugar` y dibuja su propio botón: mandarle además la
        URL en el texto sería la misma acción dos veces."""
        import inspect

        from app.orchestrator import pipeline

        fuente = inspect.getsource(pipeline.Orchestrator._respuesta_con_modelo)
        assert "entrada.canal is Channel.WHATSAPP and lugar_encontrado" in fuente

    def test_en_n2_no_se_compone(self) -> None:
        """§7.4: sin enlaces. Y sin la etiqueta huérfana tampoco.

        `adaptar` borraría la URL pero dejaría un "Cómo llegar:" apuntando a
        nada, que es peor que no ofrecerlo: sugiere que hay algo detrás.
        """
        from app.domain import OperationLevel
        from app.orchestrator.pipeline import _enlace_de_lugar

        lugar = {"lat": self.LIMA[0], "lon": self.LIMA[1]}
        assert _enlace_de_lugar(lugar, OperationLevel.N2_SATELITE) == ""
        assert "Cómo llegar" in _enlace_de_lugar(lugar, OperationLevel.N0_NORMAL)

    def test_sin_coordenadas_no_inventa_enlace(self) -> None:
        from app.domain import OperationLevel
        from app.orchestrator.pipeline import _enlace_de_lugar

        assert _enlace_de_lugar({"nombre": "Posta"}, OperationLevel.N0_NORMAL) == ""

    def test_declara_la_ubicacion_referencial(self) -> None:
        """OSM acredita que existe y dónde, no que el municipio lo designara.
        La app lo dice bajo el botón; aquí no hay botón bajo el que decirlo."""
        from app.domain import OperationLevel
        from app.orchestrator.pipeline import _enlace_de_lugar

        lugar = {"lat": self.LIMA[0], "lon": self.LIMA[1], "ubicacion_referencial": True}
        assert "no está confirmada por el municipio" in _enlace_de_lugar(
            lugar, OperationLevel.N0_NORMAL
        )

    def test_el_enlace_no_sustituye_a_la_direccion(self) -> None:
        """§7.3, la regla que gobierna esto: ninguna instrucción crítica
        depende de abrir un enlace. El enlace se añade detrás del texto, nunca
        en su lugar."""
        import inspect

        from app.orchestrator import pipeline

        fuente = inspect.getsource(pipeline.Orchestrator._respuesta_con_modelo)
        assert "texto_final += _enlace_de_lugar" in fuente
