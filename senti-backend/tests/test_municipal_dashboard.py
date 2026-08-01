"""Indicadores derivados del panel municipal (§22)."""

from __future__ import annotations

from app.domain import HazardType, ReportState
from app.rules.municipal_dashboard import (
    color_alerta,
    es_alerta_critica,
    estado_incidencia,
    nivel_riesgo_municipal,
    texto_tipo_peligro,
)


class TestColorAlerta:
    def test_roja_es_critica(self) -> None:
        assert color_alerta("Roja") == "roja"
        assert es_alerta_critica("Roja") is True

    def test_naranja_se_trata_como_critica(self) -> None:
        assert color_alerta("Naranja") == "roja"
        assert es_alerta_critica("Naranja") is True

    def test_amarilla_es_moderada(self) -> None:
        assert color_alerta("Amarilla") == "amarilla"
        assert es_alerta_critica("Amarilla") is False

    def test_verde_no_es_critica(self) -> None:
        assert color_alerta("Verde") == "verde"
        assert es_alerta_critica("Verde") is False

    def test_sin_nivel_se_trata_como_lo_mas_grave(self) -> None:
        assert color_alerta(None) == "roja"
        assert color_alerta("") == "roja"

    def test_es_insensible_a_mayusculas_y_espacios(self) -> None:
        assert color_alerta("  ROJA  ") == "roja"
        assert color_alerta("amarilla") == "amarilla"


class TestEstadoIncidencia:
    def test_resuelto_es_atendida(self) -> None:
        assert estado_incidencia(ReportState.RESUELTO) == "Atendida"

    def test_pendiente_es_en_proceso(self) -> None:
        assert estado_incidencia(ReportState.PENDIENTE) == "En proceso"

    def test_confirmado_es_en_proceso(self) -> None:
        assert estado_incidencia(ReportState.CONFIRMADO) == "En proceso"

    def test_en_revision_es_en_proceso(self) -> None:
        assert estado_incidencia(ReportState.EN_REVISION) == "En proceso"


class TestTextoTipoPeligro:
    def test_tipos_conocidos_tienen_texto_en_espanol(self) -> None:
        assert texto_tipo_peligro(HazardType.INUNDACION) == "Inundación"
        assert texto_tipo_peligro(HazardType.VIA_BLOQUEADA) == "Vía bloqueada"

    def test_cubre_todos_los_tipos_del_dominio(self) -> None:
        for tipo in HazardType:
            assert texto_tipo_peligro(tipo)


class TestNivelRiesgo:
    def test_con_criticas_es_alto(self) -> None:
        riesgo = nivel_riesgo_municipal(alertas_criticas=1, alertas_activas=3)
        assert riesgo.etiqueta == "Alto"

    def test_sin_criticas_pero_con_activas_es_medio(self) -> None:
        riesgo = nivel_riesgo_municipal(alertas_criticas=0, alertas_activas=2)
        assert riesgo.etiqueta == "Medio"

    def test_sin_alertas_es_bajo(self) -> None:
        riesgo = nivel_riesgo_municipal(alertas_criticas=0, alertas_activas=0)
        assert riesgo.etiqueta == "Bajo"
