"""SENTI — aplicación FastAPI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routers import (
    admin,
    auth,
    chat,
    ciudadano,
    comunidad,
    health,
    municipal,
    rutas,
    whatsapp,
    events,
)
from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SENTI arrancando · env=%s · modelo=%s", settings.env, settings.llm_model)
    # No se comprueba el modelo al arrancar: el §29 exige que el sistema
    # funcione con el modelo apagado, así que bloquear el arranque por eso
    # sería contradecir el propio diseño. El estado se consulta en
    # /health/detalle cuando alguien lo necesite.
    yield
    logger.info("SENTI apagándose")


app = FastAPI(
    title="SENTI",
    description=(
        "Gestión de emergencias naturales con monitoreo y asistencia. "
        "Convierte alertas oficiales y reportes comunitarios en orientación "
        "personalizada, planes familiares y rutas de menor riesgo."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# §29: disponibilidad, latencia por nivel, errores, profundidad de cola.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

for router in (
    health.router,
    auth.router,
    chat.router,
    ciudadano.router,
    comunidad.router,
    rutas.router,
    municipal.router,
    admin.router,
    whatsapp.router,
    events.router,
):
    app.include_router(router)


@app.get("/", include_in_schema=False)
def raiz() -> dict:
    return {
        "servicio": "SENTI",
        "descripcion": "Gestión de Emergencias Naturales con Monitoreo y Asistencia",
        "docs": "/docs",
        "salud": "/health",
        "atribucion": "© OpenStreetMap contributors",
        "aviso": (
            "SENTI no es un sistema de alerta temprana y no reemplaza al canal "
            "oficial del Estado. El canal de alerta masiva del Perú es SISMATE "
            "(MTC e INDECI)."
        ),
    }
