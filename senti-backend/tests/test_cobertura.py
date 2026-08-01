"""§20.4 — umbral de cobertura cartográfica."""

from __future__ import annotations

from app.routing.engine import (
    UMBRAL_DENSIDAD_VIAS_KM2,
    UMBRAL_PCT_VIAS_ETIQUETADAS,
    CoberturaCartografica,
    RouteEngine,
    _normalizar_distrito,
)


class _SesionFalsa:
    """Sesión mínima: devuelve unos parámetros de riesgo fijos."""

    def __init__(self, umbrales: dict | None) -> None:
        self._umbrales = umbrales

    def scalar(self, _stmt):
        if self._umbrales is None:
            return None

        class _Parametros:
            umbrales_cobertura = self._umbrales

        return _Parametros()


class TestFraseObligatoria:
    """§20.4: la frase cambia según la cobertura, y esa es toda su razón de ser."""

    def test_cobertura_suficiente_usa_la_formula_del_205(self) -> None:
        c = CoberturaCartografica(3.2, 0.64, True, suficiente=True)
        assert "menor riesgo según la información disponible" in c.frase
        assert "incompleta" not in c.frase

    def test_cobertura_insuficiente_lo_declara(self) -> None:
        c = CoberturaCartografica(0.0, 0.0, False, suficiente=False)
        assert "una ruta posible" in c.frase
        assert "cartografía de la zona es incompleta" in c.frase

    def test_ninguna_frase_promete_seguridad(self) -> None:
        """§20.5: nunca «esta ruta es segura», en ninguno de los dos casos."""
        from app.rules.response import revisar_lenguaje

        for suficiente in (True, False):
            c = CoberturaCartografica(3.2, 0.64, True, suficiente=suficiente)
            assert revisar_lenguaje(c.frase) == []


class TestUmbralRegistrado:
    def test_distrito_sin_registro_es_insuficiente(self) -> None:
        """Sin medición se asume lo peor: es la asimetría del §20.4.

        Declarar buena una cartografía que nadie midió manda a alguien por una
        vía que quizá no existe; declararla mala cuando era buena solo suena
        prudente de más.
        """
        motor = object.__new__(RouteEngine)
        motor.session = _SesionFalsa(None)
        assert motor.cobertura("Lurigancho-Chosica").suficiente is False

    def test_distrito_nulo_es_insuficiente(self) -> None:
        motor = object.__new__(RouteEngine)
        motor.session = _SesionFalsa({"Lurigancho-Chosica": {"densidad_vias_km2": 9}})
        assert motor.cobertura(None).suficiente is False

    def test_medicion_por_encima_del_umbral(self) -> None:
        motor = object.__new__(RouteEngine)
        motor.session = _SesionFalsa(
            {"Lurigancho-Chosica": {
                "densidad_vias_km2": UMBRAL_DENSIDAD_VIAS_KM2 + 0.2,
                "pct_vias_etiquetadas": UMBRAL_PCT_VIAS_ETIQUETADAS + 0.04,
                "tiene_elevacion": True,
            }}
        )
        c = motor.cobertura("Lurigancho-Chosica")
        assert c.suficiente is True
        assert c.tiene_elevacion is True

    def test_una_sola_metrica_baja_ya_es_insuficiente(self) -> None:
        """Se exigen las dos: muchas vías mal etiquetadas no sirven."""
        motor = object.__new__(RouteEngine)
        motor.session = _SesionFalsa(
            {"Chosica": {
                "densidad_vias_km2": UMBRAL_DENSIDAD_VIAS_KM2 + 5,
                "pct_vias_etiquetadas": 0.1,
            }}
        )
        assert motor.cobertura("Chosica").suficiente is False

    def test_coincide_sin_tildes_ni_mayusculas(self) -> None:
        """El distrito llega del perfil del hogar, que lo escribe una persona."""
        motor = object.__new__(RouteEngine)
        motor.session = _SesionFalsa(
            {"Lurigancho-Chosica": {
                "densidad_vias_km2": 5.0, "pct_vias_etiquetadas": 0.9,
            }}
        )
        assert motor.cobertura("LURIGANCHO-CHOSICA").suficiente is True


def test_normalizacion() -> None:
    assert _normalizar_distrito("  Áncash ") == "ancash"
    assert _normalizar_distrito("Lurigancho-Chosica") == "lurigancho-chosica"
