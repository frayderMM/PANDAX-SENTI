"""Capa del modelo local.

Nada de este paquete decide nada: produce texto y propuestas. Las decisiones
las toma `app.rules`. La frontera es el §8 —"Gemma explica" es el penúltimo
paso, después de que el backend ya validó el resultado.
"""

from app.llm.client import (
    ChatResult,
    EmbeddingClient,
    LLMClient,
    LLMInvalidOutput,
    LLMUnavailable,
    ToolCall,
    get_deep_llm,
    get_embeddings,
    get_llm,
    imagen_a_data_uri,
)

__all__ = [
    "ChatResult",
    "EmbeddingClient",
    "LLMClient",
    "LLMInvalidOutput",
    "LLMUnavailable",
    "ToolCall",
    "get_deep_llm",
    "get_embeddings",
    "get_llm",
    "imagen_a_data_uri",
]
