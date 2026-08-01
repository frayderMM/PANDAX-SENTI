"""Cliente de Valhalla (§20.1).

El §9 elige Valhalla sobre OSRM y GraphHopper por tres cosas concretas que se
usan aquí: `exclude_polygons` y `exclude_locations` nativos, costing
configurable y curvas de elevación para penalizar pendiente.

El reparto del §20.1 se respeta al construir la petición: solo entran cierres
**puntuales o de tramo pequeño**. Las zonas de peligro amplias no se mandan a
Valhalla — se filtran después en PostGIS — porque `exclude_polygons` es costoso
por petición y está pensado para áreas pequeñas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ValhallaUnavailable(RuntimeError):
    """Valhalla no respondió. Sin motor de rutas no se inventa una ruta."""


class SinRutaValhalla(RuntimeError):
    """Valhalla no encontró ninguna ruta con las exclusiones dadas.

    No es un error: es un resultado. Con todos los cierres excluidos puede que
    no exista camino, y el §20.2 dice que en ese caso la respuesta es `sin ruta
    verificable`.
    """


# §14 → §20.1: el perfil del hogar elige el costing.
COSTING_PEATONAL = "pedestrian"
COSTING_AUTO = "auto"


@dataclass
class ManeuverInfo:
    instruccion: str
    distancia_m: float
    duracion_s: float
    begin_shape_index: int
    end_shape_index: int


@dataclass
class ValhallaRoute:
    shape: str  # polilínea codificada, precisión 6
    puntos: list[tuple[float, float]]  # (lat, lon) decodificados
    distancia_m: float
    duracion_s: float
    maniobras: list[ManeuverInfo] = field(default_factory=list)


def decodificar_polilinea(shape: str, precision: int = 6) -> list[tuple[float, float]]:
    """Decodifica la polilínea de Valhalla.

    Valhalla usa precisión 6 (Google usa 5). Con la precisión equivocada las
    coordenadas salen desplazadas por un factor de 10 y el cruce con PostGIS
    no encuentra nada — un fallo silencioso que convierte cualquier ruta en
    "sin riesgo detectado".
    """
    factor = 10**precision
    puntos: list[tuple[float, float]] = []
    indice = lat = lon = 0

    while indice < len(shape):
        for objetivo in ("lat", "lon"):
            resultado = shift = 0
            while True:
                byte = ord(shape[indice]) - 63
                indice += 1
                resultado |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(resultado >> 1) if resultado & 1 else (resultado >> 1)
            if objetivo == "lat":
                lat += delta
            else:
                lon += delta
        puntos.append((lat / factor, lon / factor))

    return puntos


def costing_para_perfil(
    *, vehiculo: bool, movilidad_reducida: bool, adultos_mayores: int
) -> tuple[str, dict[str, Any]]:
    """Costing y sus opciones a partir del perfil del hogar (§14).

    §14: "Sin vehículo → costing peatonal, radio de destino acotado";
    "Movilidad reducida → penaliza pendiente pronunciada y escaleras;
    prioriza vías accesibles".
    """
    if vehiculo:
        return COSTING_AUTO, {"auto": {"use_highways": 0.5, "use_tolls": 0.5}}

    opciones: dict[str, Any] = {
        "pedestrian": {
            "walking_speed": 5.1,
            "sidewalk_factor": 1.0,
            "alley_factor": 2.0,
            "driveway_factor": 5.0,
            "step_penalty": 0.0,
        }
    }
    peatonal = opciones["pedestrian"]

    if movilidad_reducida:
        # NO se usa `type: wheelchair`. En Valhalla eso es un filtro DURO:
        # descarta toda vía sin etiqueta explícita de accesibilidad, y en la
        # cartografía peruana casi ninguna la tiene. Medido en Chosica: con
        # `wheelchair` Valhalla devuelve 442 "no path could be found" en calles
        # por las que sí encuentra ruta peatonal normal.
        #
        # El efecto era que la persona con movilidad reducida —la más
        # vulnerable y la razón de ser del §14— era la única que se quedaba sin
        # ninguna ruta. El §20.3 trata la accesibilidad como PENALIZACIÓN, y el
        # §20.2 no incluye "vía sin etiquetar" entre los descartes duros.
        #
        # Se penaliza fuerte y se deja que `S_accesible` ordene las candidatas.
        peatonal["step_penalty"] = 900.0
        peatonal["max_hiking_difficulty"] = 0
        peatonal["walking_speed"] = 3.0
        peatonal["sidewalk_factor"] = 0.7
        peatonal["driveway_factor"] = 10.0
    elif adultos_mayores > 0:
        # §14: "Adulto mayor → amplía tiempo estimado, prioriza destinos cercanos".
        peatonal["walking_speed"] = 3.5
        peatonal["step_penalty"] = 120.0

    return COSTING_PEATONAL, opciones


class ValhallaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        self.base_url = (base_url or settings.valhalla_url).rstrip("/")
        self.timeout = timeout

    def status(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as c:
                r = c.get(f"{self.base_url}/status")
                r.raise_for_status()
                return r.json()
        except httpx.HTTPError as exc:
            raise ValhallaUnavailable(str(exc)) from exc

    def route(
        self,
        origen: tuple[float, float],
        destino: tuple[float, float],
        *,
        costing: str = COSTING_PEATONAL,
        costing_options: dict[str, Any] | None = None,
        exclude_locations: list[tuple[float, float]] | None = None,
        exclude_polygons: list[list[tuple[float, float]]] | None = None,
        # Más candidatas aumentan la probabilidad de conservar una salida
        # válida cuando el usuario marcó varios accesos de una misma zona.
        alternates: int = 4,
    ) -> list[ValhallaRoute]:
        """Pide rutas a Valhalla con las exclusiones ya aplicadas.

        Las exclusiones van en la PETICIÓN, no en un filtro posterior (§20.1):
        una ruta que nunca se genera no puede recomendarse por error.
        """
        cuerpo: dict[str, Any] = {
            "locations": [
                {"lat": origen[0], "lon": origen[1], "type": "break"},
                {"lat": destino[0], "lon": destino[1], "type": "break"},
            ],
            "costing": costing,
            "costing_options": costing_options or {},
            "alternates": alternates,
            "units": "kilometers",
            "language": "es-ES",
            "directions_options": {"directions_type": "maneuvers"},
        }

        if exclude_locations:
            cuerpo["exclude_locations"] = [
                {"lat": lat, "lon": lon} for lat, lon in exclude_locations
            ]

        if exclude_polygons:
            # Valhalla espera [[ [lon,lat], ... ]] — longitud primero. Invertir
            # el orden aquí excluye un polígono en el hemisferio equivocado sin
            # dar ningún error.
            recortados = exclude_polygons[: settings.max_exclude_polygons]
            if len(exclude_polygons) > settings.max_exclude_polygons:
                logger.warning(
                    "§20.1: %d polígonos de exclusión recortados a %d; el resto "
                    "se resuelve con el filtro PostGIS posterior",
                    len(exclude_polygons),
                    settings.max_exclude_polygons,
                )
            cuerpo["exclude_polygons"] = [
                [[lon, lat] for lat, lon in anillo] for anillo in recortados
            ]

        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(f"{self.base_url}/route", json=cuerpo)
                if r.status_code == 400:
                    detalle = r.json()
                    # 442 = no path. Con todos los cierres excluidos puede que
                    # simplemente no exista camino.
                    if detalle.get("error_code") in (442, 171):
                        raise SinRutaValhalla(detalle.get("error", "sin ruta"))
                r.raise_for_status()
                data = r.json()
        except SinRutaValhalla:
            raise
        except httpx.HTTPError as exc:
            raise ValhallaUnavailable(f"Valhalla no respondió: {exc}") from exc

        rutas: list[ValhallaRoute] = []
        for trip in [data.get("trip")] + [a.get("trip") for a in data.get("alternates", [])]:
            if not trip:
                continue
            rutas.append(_parsear_trip(trip))

        if not rutas:
            raise SinRutaValhalla("Valhalla no devolvió ninguna ruta")
        return rutas


def _parsear_trip(trip: dict[str, Any]) -> ValhallaRoute:
    shape = ""
    maniobras: list[ManeuverInfo] = []
    distancia_km = 0.0
    duracion = 0.0

    for leg in trip.get("legs", []):
        shape += leg.get("shape", "")
        for m in leg.get("maneuvers", []):
            maniobras.append(
                ManeuverInfo(
                    instruccion=m.get("instruction", ""),
                    distancia_m=m.get("length", 0.0) * 1000.0,
                    duracion_s=m.get("time", 0.0),
                    begin_shape_index=m.get("begin_shape_index", 0),
                    end_shape_index=m.get("end_shape_index", 0),
                )
            )

    resumen = trip.get("summary", {})
    distancia_km = resumen.get("length", 0.0)
    duracion = resumen.get("time", 0.0)

    return ValhallaRoute(
        shape=shape,
        puntos=decodificar_polilinea(shape) if shape else [],
        distancia_m=distancia_km * 1000.0,
        duracion_s=duracion,
        maniobras=maniobras,
    )
