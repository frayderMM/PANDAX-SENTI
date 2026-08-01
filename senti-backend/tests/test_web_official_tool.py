from datetime import UTC, datetime
from types import SimpleNamespace

from app.orchestrator.handlers import (
    _dominio_autorizado,
    _dominio_publico_permitido,
    _dominios_oficiales,
)
from app.orchestrator.pipeline import _llamada_web_emitida_como_texto
from app.orchestrator.tools import ToolContext


class _Session:
    def __init__(self, fuentes):
        self._fuentes = fuentes

    def scalars(self, _stmt):
        return self._fuentes


def test_dominio_publico_rechaza_localhost_e_ips_privadas():
    assert not _dominio_publico_permitido("localhost")
    assert not _dominio_publico_permitido("127.0.0.1")
    assert not _dominio_publico_permitido("10.0.0.2")
    assert _dominio_publico_permitido("www.senamhi.gob.pe")


def test_dominio_autorizado_permite_subdominios_oficiales():
    permitidos = {"senamhi.gob.pe", "igp.gob.pe"}

    assert _dominio_autorizado("www.senamhi.gob.pe", permitidos)
    assert _dominio_autorizado("ide.igp.gob.pe", permitidos)
    assert not _dominio_autorizado("senamhi.gob.pe.ejemplo.com", permitidos)


def test_dominios_oficiales_salen_de_fuentes_activas():
    session = _Session(
        [
            SimpleNamespace(
                url="https://www.senamhi.gob.pe/?p=aviso-meteorologico",
                healthcheck_url=None,
            ),
            SimpleNamespace(
                url="https://ide.igp.gob.pe/arcgis/rest/services",
                healthcheck_url="https://ide.igp.gob.pe/arcgis/rest/services/status",
            ),
        ]
    )
    ctx = ToolContext(
        session=session,  # type: ignore[arg-type]
        user=None,
        ahora=datetime(2026, 7, 30, tzinfo=UTC),
    )

    assert _dominios_oficiales(ctx) == {"senamhi.gob.pe", "ide.igp.gob.pe"}


def test_adaptador_acepta_solo_llamada_web_exacta():
    assert _llamada_web_emitida_como_texto(
        'consultar_web_oficial(url="https://www.indeci.gob.pe/")'
    ) == {"url": "https://www.indeci.gob.pe/"}
    assert _llamada_web_emitida_como_texto("texto normal") is None
    assert _llamada_web_emitida_como_texto(
        'consultar_web_oficial(url="https://ejemplo.test/", extra="x")'
    ) is None


class TestBusquedaPorNombre:
    """Pedir un sitio por su nombre busca ese, no el más cercano."""

    def test_el_nombre_es_un_argumento_de_la_herramienta(self) -> None:
        from app.orchestrator.tools import RecursosArgs

        assert "nombre" in RecursosArgs.model_fields
        assert RecursosArgs(lat=-12.0, lon=-77.0).nombre is None

    def test_el_catalogo_le_dice_al_modelo_que_puede_usarlo(self) -> None:
        """Si la descripción no lo menciona, el modelo no lo pasa nunca y el
        campo no sirve de nada."""
        from app.orchestrator import handlers  # noqa: F401 — registra las herramientas
        from app.orchestrator.tools import registry

        spec = registry.get("buscar_recursos_cercanos")
        assert "nombre" in spec.descripcion.lower()

    def test_busca_lejos_cuando_se_nombra_un_sitio(self) -> None:
        """Rebagliati queda a 7,7 km de Surco: con los 3 km por defecto no
        aparece, y la respuesta acababa siendo la lista de al lado."""
        from app.orchestrator.handlers import RADIO_BUSQUEDA_POR_NOMBRE_M

        assert RADIO_BUSQUEDA_POR_NOMBRE_M >= 20000

    def test_no_sustituye_por_el_mas_cercano(self) -> None:
        """El fallo que esto corrige: pedir Rebagliati y recibir otro hospital
        sin que nadie avise puede acabar con alguien en el sitio equivocado."""
        import inspect

        from app.orchestrator import handlers

        fuente = inspect.getsource(handlers.buscar_recursos_cercanos)
        # Cuando hay nombre y no hay resultados, se declara la ausencia.
        assert "No encuentro ningún sitio registrado que se llame" in fuente

    def test_el_nombre_manda_sobre_el_tipo(self) -> None:
        """Si el modelo dedujo `refugio` y el usuario dijo "Rebagliati",
        exigir las dos cosas no encuentra nada."""
        import inspect

        from app.orchestrator import handlers

        fuente = inspect.getsource(handlers.buscar_recursos_cercanos)
        pos_nombre = fuente.index("Resource.nombre.ilike")
        pos_tipo = fuente.index("Resource.tipo == args.tipo")
        # El tipo se aplica en la rama `else`, después del filtro por nombre.
        assert pos_nombre < pos_tipo


class TestNombreSinPrefijo:
    """El nombre que se guarda es el que lee el ciudadano."""

    def test_el_importador_no_antepone_nada(self) -> None:
        import inspect

        from app.db import importar_recursos

        fuente = inspect.getsource(importar_recursos)
        assert 'f"[OSM] {nombre}"' not in fuente

    def test_lo_importado_se_reconoce_por_origen_osm(self) -> None:
        """Y no por un prefijo en el nombre: la columna está indexada y es la
        que activa el aviso de ubicación referencial."""
        import inspect

        from app.db import importar_recursos

        fuente = inspect.getsource(importar_recursos)
        assert "Resource.origen_osm.is_(True)" in fuente
        assert 'Resource.nombre.like("[OSM]%")' not in fuente

    def test_hay_migracion_para_los_ya_importados(self) -> None:
        from app.db.bootstrap import MIGRACIONES

        assert any("[OSM] " in m and "UPDATE resources" in m for m in MIGRACIONES)
