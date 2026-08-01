"""§21.2 — escalera de confianza."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain import ConfidenceLevel, TrustLevel
from app.rules.trust import ReportSignal, distancia_m, evaluar

AHORA = datetime(2026, 7, 29, 20, 0, tzinfo=UTC)
BASE = ReportSignal(reporter_id="rosa", lat=-11.9404, lon=-76.7006, reportado_at=AHORA)


def cerca(reporter_id: str, metros: float = 100.0, minutos: int = 10) -> ReportSignal:
    # ~0.000009 grados de latitud por metro.
    return ReportSignal(
        reporter_id=reporter_id,
        lat=BASE.lat + metros * 9e-6,
        lon=BASE.lon,
        reportado_at=AHORA + timedelta(minutes=minutos),
    )


class TestEscalera:
    def test_reporte_individual_es_pendiente(self) -> None:
        d = evaluar(BASE)
        assert d.nivel is TrustLevel.PENDIENTE
        assert d.excluye_de_ruta is False

    def test_dos_independientes_cerca_y_a_tiempo_es_probable(self) -> None:
        d = evaluar(BASE, [cerca("juan")])
        assert d.nivel is TrustLevel.PROBABLE
        assert d.reportes_coincidentes == 2

    def test_validador_con_evidencia_es_validado(self) -> None:
        d = evaluar(BASE, validado_por_validador=True, tiene_evidencia=True)
        assert d.nivel is TrustLevel.VALIDADO

    def test_validador_sin_evidencia_no_sube(self) -> None:
        """§21.2 dice «decisión de un validador con evidencia», no «decisión de
        un validador»."""
        d = evaluar(BASE, validado_por_validador=True, tiene_evidencia=False)
        assert d.nivel is TrustLevel.PENDIENTE

    @pytest.mark.parametrize(
        "fuente", [ConfidenceLevel.OFICIAL, ConfidenceLevel.MUNICIPAL]
    )
    def test_municipio_o_estado_confirman(self, fuente: ConfidenceLevel) -> None:
        d = evaluar(BASE, confirmado_por=fuente)
        assert d.nivel is TrustLevel.CONFIRMADO
        assert d.excluye_de_ruta is True

    @pytest.mark.parametrize(
        "fuente", [ConfidenceLevel.VALIDADO, ConfidenceLevel.SIN_CONFIRMAR]
    )
    def test_solo_oficial_o_municipal_confirman(self, fuente: ConfidenceLevel) -> None:
        """§6: «Solo el operador municipal o una fuente oficial cierran una vía»."""
        assert evaluar(BASE, confirmado_por=fuente).nivel is not TrustLevel.CONFIRMADO

    def test_solo_confirmado_excluye(self) -> None:
        for d in (
            evaluar(BASE),
            evaluar(BASE, [cerca("juan")]),
            evaluar(BASE, validado_por_validador=True, tiene_evidencia=True),
        ):
            assert d.excluye_de_ruta is False


class TestIndependencia:
    """«dos reportes independientes» — de dos personas distintas."""

    def test_mismo_autor_no_cuenta(self) -> None:
        d = evaluar(BASE, [cerca("rosa")])
        assert d.nivel is TrustLevel.PENDIENTE

    def test_autor_anonimo_no_cuenta(self) -> None:
        anonimo = ReportSignal(None, BASE.lat, BASE.lon, AHORA)
        assert evaluar(BASE, [anonimo]).nivel is TrustLevel.PENDIENTE

    def test_el_mismo_tercero_dos_veces_cuenta_una(self) -> None:
        d = evaluar(BASE, [cerca("juan", minutos=5), cerca("juan", minutos=10)])
        assert d.reportes_coincidentes == 2


class TestVentanaYRadio:
    def test_mas_de_300m_no_cuenta(self) -> None:
        lejos = ReportSignal("juan", BASE.lat + 0.0045, BASE.lon, AHORA)  # ~500 m
        assert evaluar(BASE, [lejos]).nivel is TrustLevel.PENDIENTE

    def test_mas_de_60_minutos_no_cuenta(self) -> None:
        tarde = cerca("juan", metros=50.0, minutos=75)
        assert evaluar(BASE, [tarde]).nivel is TrustLevel.PENDIENTE

    def test_justo_dentro_del_radio_cuenta(self) -> None:
        assert evaluar(BASE, [cerca("juan", metros=290.0)]).nivel is TrustLevel.PROBABLE

    def test_ventana_es_simetrica(self) -> None:
        """Un reporte anterior al base también coincide."""
        antes = cerca("juan", metros=50.0, minutos=-30)
        assert evaluar(BASE, [antes]).nivel is TrustLevel.PROBABLE


class TestDistancia:
    def test_haversine_grado_de_latitud(self) -> None:
        d = distancia_m(0.0, 0.0, 1.0, 0.0)
        assert d == pytest.approx(111_195.0, rel=0.001)

    def test_mismo_punto_es_cero(self) -> None:
        assert distancia_m(-11.94, -76.70, -11.94, -76.70) == pytest.approx(0.0, abs=1e-6)


def test_una_fotografia_no_cierra_una_via() -> None:
    """§21.2, literal. Con foto y todo, un reporte individual es pendiente."""
    assert evaluar(BASE).excluye_de_ruta is False
