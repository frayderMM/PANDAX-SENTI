"""Salud del sistema y de las fuentes (§11.3, §29)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.config import settings
from app.llm import LLMUnavailable, get_deep_llm, get_embeddings, get_llm
from app.models import OfficialSource
from app.sources.health import declarar_ausencia

router = APIRouter(tags=["salud"])


@router.get("/health")
def health() -> dict:
    """Liveness. Deliberadamente no toca la base de datos ni el modelo.

    Si `/health` dependiera del modelo, el orquestador de contenedores mataría
    la API cada vez que LM Studio descarga el modelo por inactividad — y el
    §29 exige justo lo contrario: que el sistema siga respondiendo con el
    modelo apagado.
    """
    return {"status": "ok", "servicio": "senti-api", "env": settings.env}


@router.get("/health/detalle")
def health_detalle(session: Session = Depends(db)) -> dict:
    """Readiness. Aquí sí se comprueba todo, para operación y diagnóstico."""
    detalle: dict = {"env": settings.env, "ahora": datetime.now(UTC).isoformat()}

    try:
        session.execute(text("SELECT 1"))
        postgis = session.scalar(text("SELECT PostGIS_Version()"))
        pgvector = session.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        detalle["base_datos"] = {"ok": True, "postgis": postgis, "pgvector": pgvector}
    except Exception as exc:  # noqa: BLE001 - el detalle es el objetivo
        detalle["base_datos"] = {"ok": False, "error": str(exc)}

    try:
        detalle["modelo"] = get_llm().estado()
    except LLMUnavailable as exc:
        detalle["modelo"] = {"disponible": False, "error": str(exc)}

    # El chat no es lo único que se cae. El modelo profundo sostiene el §15, el
    # §21.1 y las imágenes; los embeddings sostienen el RAG. Si cualquiera de
    # los dos falta, el sistema sigue respondiendo y va perdiendo capacidades en
    # silencio, que es exactamente lo que este endpoint existe para evitar.
    try:
        detalle["modelo_profundo"] = get_deep_llm().estado()
    except LLMUnavailable as exc:
        detalle["modelo_profundo"] = {"disponible": False, "error": str(exc)}

    embeddings = get_embeddings()
    detalle["embeddings"] = {
        "base_url": embeddings.base_url,
        "modelo_configurado": embeddings.model,
        "dimensiones_esperadas": settings.embedding_dim,
    }
    try:
        vector = embeddings.embed(["comprobación de salud"])[0]
        detalle["embeddings"]["disponible"] = True
        detalle["embeddings"]["dimensiones"] = len(vector)
        if len(vector) != settings.embedding_dim:
            detalle["embeddings"]["aviso"] = (
                f"El modelo devuelve {len(vector)} dimensiones y la columna espera "
                f"{settings.embedding_dim}: la indexación fallará."
            )
    except Exception as exc:  # noqa: BLE001 - el detalle es el objetivo
        detalle["embeddings"]["disponible"] = False
        detalle["embeddings"]["error"] = str(exc)

    return detalle


@router.get("/fuentes/estado")
def estado_fuentes(session: Session = Depends(db)) -> dict:
    """§11.3. Si una fuente está caída, SENTI lo dice."""
    ahora = datetime.now(UTC)
    fuentes = list(session.scalars(select(OfficialSource).where(OfficialSource.activa.is_(True))))
    return {
        "consultado_at": ahora.isoformat(),
        "fuentes": [
            {
                "slug": f.slug,
                "institucion": f.institucion,
                "estado": f.ultimo_estado.value,
                "verificada": f.verificada,
                "citable": f.puede_citarse_como_vigente(ahora),
                "ultima_consulta": f.ultima_consulta_at.isoformat()
                if f.ultima_consulta_at
                else None,
                "declaracion": declarar_ausencia(f.institucion, f.ultimo_estado),
            }
            for f in fuentes
        ],
    }
