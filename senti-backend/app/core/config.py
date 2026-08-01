"""Configuración del backend. Todo secreto llega por entorno (§28)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"
    pilot_district: str = "Lurigancho-Chosica"

    # ── Modelo local ────────────────────────────────────────────────────
    # Contrato OpenAI. Sirve igual para LM Studio (host o servidor) y para
    # llama.cpp en contenedor: es el mismo motor y el mismo GGUF.
    llm_base_url: str = "http://llama-cpu:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = "google/gemma-4-e4b"
    # 8192 y no 32768: el despliegue objetivo es un servidor de 2 vCPU sin GPU,
    # donde el contexto se paga en cada token generado. Debe coincidir con
    # .env.example y con el --ctx-size del contenedor; si no coinciden, las
    # respuestas se cortan sin que nada dé error.
    llm_context_length: int = 8192
    # 80 y no 96: la guardia recorta la salida a 320 caracteres (§24), que son
    # ~80 fichas. Las 16 de más se generaban para tirarlas, y a 10 fichas/s en
    # CPU eso es segundo y medio que alguien espera por nada.
    llm_max_tokens: int = 80
    # El turno en que el modelo ELIGE herramienta no es el turno en que
    # redacta. 96 fichas bastan para una respuesta de ≤320 caracteres y no
    # llegan para razonar y emitir el JSON de la llamada: se trunca a medias y
    # la herramienta se pierde **sin dar error**. Medido: con 96 elegía cero
    # herramientas de tres intentos y pedía la ubicación que ya tenía.
    #
    # 256 y no 512: solo se le ofrece UNA herramienta, así que no hay nada que
    # deliberar. A 9 fichas/s en CPU, cada ficha de razonamiento de más es una
    # décima de segundo que alguien espera.
    llm_tool_max_tokens: int = 256
    llm_timeout_seconds: float = 120.0
    llm_temperature: float = 0.2
    # §29: por encima de esta profundidad de cola, el amarillo responde
    # con plantillas fijas sin pasar por el modelo.
    llm_queue_max_depth: int = 32

    # ── Tareas de análisis ──────────────────────────────────────────────
    # Imágenes (§25), extracción documental de alertas (§15) y categorización
    # de reportes (§21.1). Apuntan al MISMO servidor que el chat.
    #
    # Hubo dos modelos, repartidos por latencia tolerable. Se midió en el
    # servidor y el reparto no existía: los dos GGUF eran enlaces al mismo
    # archivo, así que llama.cpp cargaba el mismo modelo dos veces y los dos
    # procesos competían por los mismos cinco núcleos. Uno solo va más rápido.
    #
    # Estos ajustes siguen separados porque las tareas son distintas: analizar
    # una foto necesita más fichas de salida y más paciencia que contestar en
    # un chat. Si algún día hay dos servidores de verdad, basta cambiar la URL.
    llm_deep_base_url: str = "http://llama-cpu:1234/v1"
    llm_deep_model: str = "google/gemma-4-e4b"
    # Más holgado que el chat: describir una imagen o extraer los campos de una
    # alerta no cabe en las 96 fichas que basta para responder al ciudadano.
    llm_deep_max_tokens: int = 512
    llm_deep_timeout_seconds: float = 300.0

    embedding_base_url: str = "http://host.docker.internal:1234/v1"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    # nomic-embed-text-v1.5 → 768. Debe coincidir con la columna vector(n).
    embedding_dim: int = 768

    # ── Infraestructura ─────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://senti:senti@localhost:5432/senti"
    valkey_url: str = "redis://localhost:6379/0"
    valhalla_url: str = "http://localhost:8002"
    max_exclude_polygons: int = 8

    # ── Seguridad (§28) ─────────────────────────────────────────────────
    secret_key: str = "dev-only-no-usar-en-produccion"
    field_encryption_key: str = ""
    phone_hash_salt: str = "dev-salt"
    access_token_minutes: int = 60

    # ── WhatsApp por Evolution API (§10.1) ──────────────────────────────
    #
    # Evolution habla WhatsApp por Baileys, no por la nube de Meta: no hay
    # `phone_number_id` ni plantillas aprobadas. La ventana de 24 h del §10.1
    # se sigue respetando igual, porque es una regla de WhatsApp y no del
    # proveedor: fuera de ella no se inicia conversación.
    #
    # `whatsapp_enabled` en false deja el webhook devolviendo 503. Es
    # deliberado: un canal de emergencia a medio configurar que acepta
    # mensajes y no responde es peor que uno que dice que no está.
    whatsapp_enabled: bool = False
    evolution_api_url: str = ""
    evolution_instance: str = "mi_bot"
    evolution_api_key: str = ""
    # Cabecera compartida que debe traer el webhook. Evolution no firma sus
    # peticiones, así que sin esto cualquiera que sepa la URL puede inyectar
    # mensajes falsos y hacer que SENTI conteste a quien él diga.
    whatsapp_webhook_token: str = ""

    # ── Operación ───────────────────────────────────────────────────────
    source_healthcheck_minutes: int = 15
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Agrupación de reportes ciudadanos en eventos unificados.
    citizen_report_group_radius_meters: float = Field(500.0, validation_alias="CITIZEN_REPORT_GROUP_RADIUS_METERS")
    citizen_report_group_time_hours: float = Field(6.0, validation_alias="CITIZEN_REPORT_GROUP_TIME_HOURS")
    citizen_report_min_text_similarity: float = Field(0.65, validation_alias="CITIZEN_REPORT_MIN_TEXT_SIMILARITY")
    citizen_llm_base_url: str = Field("http://llama-citizen:1236/v1", validation_alias="SENTI_CITIZEN_LLM_BASE_URL")
    citizen_llm_model: str = Field("google/gemma-2-2b-it", validation_alias="SENTI_CITIZEN_LLM_MODEL")
    citizen_source_poll_minutes: int = Field(10, validation_alias="SENTI_CITIZEN_SOURCE_POLL_MINUTES")
    nominatim_url: str = Field("https://nominatim.openstreetmap.org", validation_alias="SENTI_NOMINATIM_URL")

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
