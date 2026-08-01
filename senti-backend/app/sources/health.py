"""Healthcheck de fuentes oficiales (§11.3).

    Cada 15 minutos, por fuente:
        GET <endpoint>?f=json
        Registrar: http_status, latencia, currentVersion, conteo de features,
                   hash del esquema

    | ok        | responde y el esquema coincide       | uso normal          |
    | degradado | cambió el esquema o latencia alta    | uso con advertencia |
    | caído     | sin respuesta en 3 intentos          | no se cita          |
    | obsoleto  | el dato más reciente excede vigencia | referencia histórica|

La frase que gobierna el módulo es la última del §11.3: "Si una fuente está
caída, SENTI lo dice. Nunca presenta silencio como ausencia de peligro."
Por eso `caido` no significa "ignorar la fuente" sino "declarar que no se pudo
consultar" — son cosas distintas y el §12 depende de la diferencia.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.domain import SourceStatus

logger = logging.getLogger(__name__)

INTENTOS = 3
UMBRAL_LATENCIA_MS = 5000.0
TIMEOUT_S = 10.0


@dataclass
class HealthResult:
    status: SourceStatus
    http_status: int | None = None
    latencia_ms: float | None = None
    current_version: str | None = None
    feature_count: int | None = None
    schema_hash: str | None = None
    detalle: str | None = None
    esquema_cambio: bool = False

    @property
    def citable(self) -> bool:
        """§11.3: solo `ok` y `degradado` se citan; `degradado` con advertencia."""
        return self.status in (SourceStatus.OK, SourceStatus.DEGRADADO)


def hash_esquema(payload: dict[str, Any]) -> str:
    """Huella del esquema, no del contenido.

    Se queda con los nombres y tipos de campo y descarta los datos: el objetivo
    es detectar que la institución cambió el formato, no que publicó un dato
    nuevo. Sin esta separación, cada sismo nuevo se vería como un cambio de
    esquema y todas las fuentes estarían permanentemente `degradado`.
    """
    huella: dict[str, Any] = {}

    if "fields" in payload and isinstance(payload["fields"], list):
        huella["fields"] = sorted(
            f"{f.get('name')}:{f.get('type')}"
            for f in payload["fields"]
            if isinstance(f, dict)
        )
    if "geometryType" in payload:
        huella["geometryType"] = payload["geometryType"]
    if "currentVersion" in payload:
        huella["currentVersion"] = payload["currentVersion"]
    if "layers" in payload and isinstance(payload["layers"], list):
        huella["layers"] = sorted(
            str(lyr.get("name")) for lyr in payload["layers"] if isinstance(lyr, dict)
        )
    if not huella:
        huella["claves"] = sorted(str(k) for k in payload)

    return hashlib.sha256(
        json.dumps(huella, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def comprobar(
    url: str,
    *,
    schema_hash_previo: str | None = None,
    dato_mas_reciente: datetime | None = None,
    vigencia_horas: int | None = None,
    ahora: datetime | None = None,
    intentos: int = INTENTOS,
) -> HealthResult:
    """Ejecuta el healthcheck del §11.3 sobre una fuente."""
    separador = "&" if "?" in url else "?"
    objetivo = f"{url}{separador}f=json"
    ultimo_error: str | None = None

    for intento in range(1, intentos + 1):
        inicio = time.perf_counter()
        try:
            with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True) as c:
                r = c.get(objetivo, headers={"User-Agent": "SENTI/0.1 (gestion de emergencias)"})
            latencia = (time.perf_counter() - inicio) * 1000.0
        except httpx.HTTPError as exc:
            ultimo_error = f"intento {intento}: {exc}"
            continue

        if r.status_code >= 500:
            ultimo_error = f"intento {intento}: HTTP {r.status_code}"
            continue

        try:
            payload = r.json()
        except ValueError:
            return HealthResult(
                status=SourceStatus.DEGRADADO,
                http_status=r.status_code,
                latencia_ms=latencia,
                detalle="la respuesta no es JSON; el formato de origen cambió",
                esquema_cambio=True,
            )

        # Un ArcGIS REST puede devolver 200 con un error dentro del cuerpo.
        if isinstance(payload, dict) and "error" in payload:
            return HealthResult(
                status=SourceStatus.DEGRADADO,
                http_status=r.status_code,
                latencia_ms=latencia,
                detalle=f"error de la fuente: {payload['error']}",
            )

        h = hash_esquema(payload)
        cambio = schema_hash_previo is not None and h != schema_hash_previo
        conteo = _contar_features(payload)

        estado = SourceStatus.OK
        detalle = None
        if cambio:
            estado = SourceStatus.DEGRADADO
            detalle = "el esquema cambió respecto de la última comprobación"
        elif latencia > UMBRAL_LATENCIA_MS:
            estado = SourceStatus.DEGRADADO
            detalle = f"latencia alta ({latencia:.0f} ms)"

        # `obsoleto` gana sobre `ok`: que el servidor responda no significa que
        # el dato sirva. Es la diferencia entre "la fuente está viva" y "la
        # fuente está informando".
        if (
            dato_mas_reciente is not None
            and vigencia_horas is not None
            and ahora is not None
            and ahora - dato_mas_reciente > timedelta(hours=vigencia_horas)
        ):
            estado = SourceStatus.OBSOLETO
            detalle = (
                f"el dato más reciente ({dato_mas_reciente.isoformat()}) excede "
                f"la vigencia de {vigencia_horas} h"
            )

        return HealthResult(
            status=estado,
            http_status=r.status_code,
            latencia_ms=latencia,
            current_version=str(payload.get("currentVersion")) if isinstance(payload, dict) else None,
            feature_count=conteo,
            schema_hash=h,
            detalle=detalle,
            esquema_cambio=cambio,
        )

    return HealthResult(
        status=SourceStatus.CAIDO,
        detalle=f"sin respuesta en {intentos} intentos. {ultimo_error or ''}".strip(),
    )


def _contar_features(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("features"), list):
        return len(payload["features"])
    if isinstance(payload.get("count"), int):
        return payload["count"]
    return None


def declarar_ausencia(institucion: str, estado: SourceStatus) -> str:
    """El texto que se le muestra al usuario cuando una fuente no sirve (§11.3).

    Nunca se calla. Que no haya dato es información, y presentarlo como
    ausencia de peligro es exactamente lo que el §12 prohíbe.
    """
    if estado is SourceStatus.CAIDO:
        return (
            f"No pude consultar {institucion} en este momento. "
            f"Eso no significa que no haya peligro: significa que no tengo el dato."
        )
    if estado is SourceStatus.OBSOLETO:
        return (
            f"El dato más reciente de {institucion} está fuera de vigencia. "
            f"Lo uso solo como referencia histórica."
        )
    if estado is SourceStatus.DEGRADADO:
        return f"{institucion} respondió, pero el dato puede estar desactualizado."
    return ""
