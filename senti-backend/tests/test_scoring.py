"""§20.2 y §20.3 — descarte duro y puntaje de rutas.

El test que más importa de todo el repositorio es
`TestFalsosNegativos::test_cierre_oficial_nunca_produce_ruta`: el §32.2 fija
los falsos negativos de bloqueo en 0 % y dice que un solo caso bloquea el
lanzamiento.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain import HazardType, TrustLevel
from app.rules.scoring import (
    PESOS,
    RIESGO_REPORTE_VALIDADO,
    HouseholdFacts,
    ReportRisk,
    RouteFacts,
    SegmentFacts,
    motivo_descarte,
    peso_temporal,
    puntuar,
    rankear,
    riesgo_segmento,
    s_accesible,
    s_fuente,
)

AHORA = datetime(2026, 7, 29, 20, 35, tzinfo=UTC)


def ruta(id_: str, **kw) -> RouteFacts:
    base = {
        "segmentos": (SegmentFacts(),),
        "distancia_m": 2100.0,
        "duracion_s": 1680.0,
    }
    base.update(kw)
    return RouteFacts(id=id_, **base)  # type: ignore[arg-type]


class TestDescarteDuro:
    """§20.2, las seis condiciones, literales."""

    @pytest.mark.parametrize(
        "kw,esperado",
        [
            ({"segmentos": (SegmentFacts(cruza_cierre_vigente=True),)},
             "cruza un cierre oficial o municipal vigente"),
            ({"atraviesa_puente_afectado": True},
             "atraviesa un puente reportado como afectado"),
            ({"entra_quebrada_activada": True},
             "entra a una quebrada con activación reportada"),
            ({"requiere_cruzar_agua": True}, "requiere cruzar agua"),
            ({"contradice_orden_evacuacion": True},
             "contradice una orden oficial de evacuación"),
            ({"destino_validado": False}, "conduce a un destino no validado"),
        ],
    )
    def test_cada_condicion_descarta(self, kw: dict, esperado: str) -> None:
        assert motivo_descarte(ruta("r", **kw)) == esperado

    def test_ruta_limpia_sobrevive(self) -> None:
        assert motivo_descarte(ruta("r")) is None

    def test_orden_oficial_tiene_precedencia_en_el_motivo(self) -> None:
        """§12: la orden oficial prevalece, así que es el motivo que se reporta."""
        r = ruta("r", contradice_orden_evacuacion=True, requiere_cruzar_agua=True)
        assert motivo_descarte(r) == "contradice una orden oficial de evacuación"


class TestFalsosNegativos:
    """§32.2: 0 % de falsos negativos de bloqueo. Un solo caso bloquea el lanzamiento."""

    def test_cierre_oficial_nunca_produce_ruta(self) -> None:
        rutas = [
            ruta("bloqueada", segmentos=(SegmentFacts(cruza_cierre_vigente=True),)),
            ruta("tambien-bloqueada", segmentos=(SegmentFacts(), SegmentFacts(cruza_cierre_vigente=True))),
        ]
        r = rankear(rutas, HouseholdFacts(), AHORA)
        assert r.sin_ruta_verificable is True
        assert r.recomendada is None
        assert len(r.descartadas) == 2

    def test_un_cierre_en_cualquier_tramo_descarta_la_ruta_entera(self) -> None:
        r = ruta("r", segmentos=(SegmentFacts(), SegmentFacts(), SegmentFacts(cruza_cierre_vigente=True)))
        assert motivo_descarte(r) is not None

    def test_no_se_degrada_a_la_menos_mala(self) -> None:
        """§20.2: «sin excepción». No hay ruta "aceptable" si todas se descartan."""
        r = rankear([ruta("x", requiere_cruzar_agua=True)], HouseholdFacts(), AHORA)
        assert r.recomendada is None
        assert r.alternativa is None


class TestRiesgoPorTramo:
    """§20.3, tabla de riesgo por tramo."""

    def test_sin_senal(self) -> None:
        riesgo, motivo = riesgo_segmento(SegmentFacts(), AHORA)
        assert riesgo == 0.0
        assert motivo == "sin señal de riesgo"

    def test_zona_peligro_alto(self) -> None:
        riesgo, _ = riesgo_segmento(SegmentFacts(intersecta_zona_peligro_alto=True), AHORA)
        assert riesgo == pytest.approx(0.70)

    @pytest.mark.parametrize(
        "nivel,esperado",
        [
            (TrustLevel.VALIDADO, 0.55),
            (TrustLevel.PROBABLE, 0.40),
            (TrustLevel.PENDIENTE, 0.15),
        ],
    )
    def test_reportes_a_menos_de_200m(self, nivel: TrustLevel, esperado: float) -> None:
        seg = SegmentFacts(
            reportes_cercanos=(
                ReportRisk(nivel, HazardType.INUNDACION, AHORA, distancia_m=150.0),
            )
        )
        riesgo, _ = riesgo_segmento(seg, AHORA)
        assert riesgo == pytest.approx(esperado)

    def test_reporte_a_mas_de_200m_no_cuenta(self) -> None:
        seg = SegmentFacts(
            reportes_cercanos=(
                ReportRisk(TrustLevel.VALIDADO, HazardType.INUNDACION, AHORA, distancia_m=250.0),
            )
        )
        assert riesgo_segmento(seg, AHORA)[0] == 0.0

    def test_gana_el_maximo_no_la_suma(self) -> None:
        """§20.3 define S_seguridad sobre el máximo: dos señales medias no
        equivalen a una grave."""
        seg = SegmentFacts(
            reportes_cercanos=(
                ReportRisk(TrustLevel.PENDIENTE, HazardType.INUNDACION, AHORA, 50.0),
                ReportRisk(TrustLevel.PROBABLE, HazardType.INUNDACION, AHORA, 50.0),
            )
        )
        assert riesgo_segmento(seg, AHORA)[0] == pytest.approx(0.40)


class TestDecaimientoTemporal:
    """§20.3: «Un reporte vencido no penaliza ni tranquiliza»."""

    def test_reporte_nuevo_pesa_uno(self) -> None:
        assert peso_temporal(AHORA, AHORA, HazardType.INUNDACION) == 1.0

    def test_decae_linealmente(self) -> None:
        # Inundación vence a las 12 h; a las 6 h queda la mitad.
        p = peso_temporal(AHORA - timedelta(hours=6), AHORA, HazardType.INUNDACION)
        assert p == pytest.approx(0.5)

    def test_vencido_pesa_cero(self) -> None:
        p = peso_temporal(AHORA - timedelta(hours=13), AHORA, HazardType.INUNDACION)
        assert p == 0.0

    def test_vencido_no_penaliza(self) -> None:
        seg = SegmentFacts(
            reportes_cercanos=(
                ReportRisk(
                    TrustLevel.VALIDADO,
                    HazardType.INUNDACION,
                    AHORA - timedelta(hours=20),
                    distancia_m=50.0,
                ),
            )
        )
        assert riesgo_segmento(seg, AHORA)[0] == 0.0

    def test_vencido_tampoco_tranquiliza(self) -> None:
        """No se vuelve negativo ni marca la zona como comprobada."""
        seg = SegmentFacts(
            reportes_cercanos=(
                ReportRisk(
                    TrustLevel.VALIDADO, HazardType.INUNDACION,
                    AHORA - timedelta(hours=20), 50.0,
                ),
            )
        )
        riesgo, _ = riesgo_segmento(seg, AHORA)
        assert riesgo >= 0.0

    def test_media_vida_reduce_el_riesgo_a_la_mitad(self) -> None:
        seg = SegmentFacts(
            reportes_cercanos=(
                ReportRisk(
                    TrustLevel.VALIDADO, HazardType.INUNDACION,
                    AHORA - timedelta(hours=6), 50.0,
                ),
            )
        )
        assert riesgo_segmento(seg, AHORA)[0] == pytest.approx(RIESGO_REPORTE_VALIDADO * 0.5)


class TestSFuente:
    def test_todo_oficial(self) -> None:
        assert s_fuente(ruta("r", bloqueos_de_fuente_oficial=2)) == 1.0

    def test_mixto(self) -> None:
        assert s_fuente(
            ruta("r", bloqueos_de_fuente_oficial=1, bloqueos_de_fuente_comunitaria=1)
        ) == pytest.approx(0.6)

    def test_solo_comunitario(self) -> None:
        assert s_fuente(ruta("r", bloqueos_de_fuente_comunitaria=3)) == pytest.approx(0.3)

    def test_sin_informacion_reciente(self) -> None:
        assert s_fuente(ruta("r", hay_informacion_reciente_zona=False)) == 0.0


class TestSAccesible:
    def test_sin_condiciones_especiales_es_uno(self) -> None:
        """§20.3: «Sin condiciones especiales, S_accesible = 1»."""
        r = ruta("r", segmentos=(SegmentFacts(pendiente_max_pct=18.0, tiene_escaleras=True),))
        assert s_accesible(r, HouseholdFacts(vehiculo=True)) == 1.0

    def test_movilidad_reducida_penaliza_escaleras(self) -> None:
        r = ruta("r", segmentos=(SegmentFacts(tiene_escaleras=True),))
        assert s_accesible(r, HouseholdFacts(movilidad_reducida=True)) < 1.0

    def test_movilidad_reducida_penaliza_pendiente(self) -> None:
        suave = ruta("a", segmentos=(SegmentFacts(pendiente_max_pct=3.0),))
        fuerte = ruta("b", segmentos=(SegmentFacts(pendiente_max_pct=15.0),))
        hogar = HouseholdFacts(movilidad_reducida=True)
        assert s_accesible(fuerte, hogar) < s_accesible(suave, hogar)

    def test_adulto_mayor_penaliza_menos_que_movilidad_reducida(self) -> None:
        r = ruta("r", segmentos=(SegmentFacts(pendiente_max_pct=15.0, tiene_escaleras=True),))
        assert s_accesible(r, HouseholdFacts(adultos_mayores=1)) > s_accesible(
            r, HouseholdFacts(movilidad_reducida=True)
        )


class TestPuntaje:
    def test_pesos_del_documento(self) -> None:
        assert PESOS == {
            "seguridad": 0.50,
            "fuente": 0.20,
            "accesible": 0.15,
            "duracion": 0.10,
            "distancia": 0.05,
        }
        assert sum(PESOS.values()) == pytest.approx(1.0)

    def test_ruta_perfecta_puntua_uno(self) -> None:
        s = puntuar(
            ruta("r", bloqueos_de_fuente_oficial=1),
            HouseholdFacts(vehiculo=True),
            AHORA,
            duracion_minima_s=1680.0,
            distancia_minima_m=2100.0,
        )
        assert s.puntaje == pytest.approx(1.0)

    def test_la_mas_rapida_no_gana_si_es_mas_riesgosa(self) -> None:
        """§20.3: «La ruta más rápida no se selecciona cuando tiene mayor riesgo»."""
        rapida_riesgosa = ruta(
            "rapida",
            duracion_s=600.0,
            distancia_m=1000.0,
            segmentos=(SegmentFacts(intersecta_zona_peligro_alto=True),),
            bloqueos_de_fuente_oficial=1,
        )
        lenta_segura = ruta(
            "lenta", duracion_s=900.0, distancia_m=1500.0, bloqueos_de_fuente_oficial=1
        )
        r = rankear([rapida_riesgosa, lenta_segura], HouseholdFacts(vehiculo=True), AHORA)
        assert r.recomendada is not None
        assert r.recomendada.ruta_id == "lenta"

    def test_la_mas_corta_no_gana_si_el_hogar_no_puede_recorrerla(self) -> None:
        """§20.3: «La ruta más corta no se selecciona cuando el hogar no puede
        recorrerla»."""
        corta_con_escaleras = ruta(
            "corta",
            duracion_s=600.0,
            distancia_m=800.0,
            segmentos=(SegmentFacts(tiene_escaleras=True, pendiente_max_pct=16.0),),
        )
        larga_plana = ruta("larga", duracion_s=660.0, distancia_m=880.0)
        r = rankear(
            [corta_con_escaleras, larga_plana],
            HouseholdFacts(movilidad_reducida=True, vehiculo=False),
            AHORA,
        )
        assert r.recomendada is not None
        assert r.recomendada.ruta_id == "larga"

    def test_devuelve_recomendada_y_alternativa(self) -> None:
        """§20.1: «Puntaje → ruta recomendada + alternativa»."""
        r = rankear(
            [ruta("a", duracion_s=600.0), ruta("b", duracion_s=700.0), ruta("c", duracion_s=800.0)],
            HouseholdFacts(vehiculo=True),
            AHORA,
        )
        assert r.recomendada is not None
        assert r.alternativa is not None
        assert r.recomendada.puntaje >= r.alternativa.puntaje

    def test_minimos_se_calculan_sobre_supervivientes(self) -> None:
        """Comparar contra una ruta descartada falsearía S_duracion."""
        r = rankear(
            [
                ruta("descartada", duracion_s=100.0, distancia_m=100.0, requiere_cruzar_agua=True),
                ruta("viva", duracion_s=600.0, distancia_m=1000.0, bloqueos_de_fuente_oficial=1),
            ],
            HouseholdFacts(vehiculo=True),
            AHORA,
        )
        assert r.recomendada is not None
        assert r.recomendada.s_duracion == pytest.approx(1.0)


class TestCostingAccesible:
    """§14 y §20.2: la accesibilidad penaliza, no excluye."""

    def test_movilidad_reducida_no_usa_filtro_wheelchair(self) -> None:
        """`type: wheelchair` es un filtro duro en Valhalla.

        Medido en Chosica: descarta toda vía sin etiqueta de accesibilidad y
        devuelve 442 en calles donde el costing peatonal normal sí encuentra
        ruta. Dejaba sin servicio justo al usuario del §14.
        """
        from app.routing.valhalla import costing_para_perfil

        _, opciones = costing_para_perfil(
            vehiculo=False, movilidad_reducida=True, adultos_mayores=0
        )
        assert opciones["pedestrian"].get("type") != "wheelchair"

    def test_movilidad_reducida_penaliza_escalones(self) -> None:
        from app.routing.valhalla import costing_para_perfil

        _, con = costing_para_perfil(vehiculo=False, movilidad_reducida=True, adultos_mayores=0)
        _, sin = costing_para_perfil(vehiculo=False, movilidad_reducida=False, adultos_mayores=0)
        assert con["pedestrian"]["step_penalty"] > sin["pedestrian"]["step_penalty"]
