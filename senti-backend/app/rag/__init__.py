"""RAG sobre pgvector (§19).

Gemma ocupa el último lugar de la precedencia del §19. Este paquete es lo que
hay por encima: fragmentos oficiales, vigentes y con fuente, para que el modelo
redacte sobre algo verificable en vez de sobre lo que recuerde.
"""

from app.rag.chunker import Fragmento, trocear
from app.rag.indexer import IngestaResultado, ingerir, reindexar_pendientes
from app.rag.retriever import (
    TOP_K,
    UMBRAL_SIMILITUD,
    FragmentoRecuperado,
    Retriever,
    como_contexto,
)

__all__ = [
    "TOP_K",
    "UMBRAL_SIMILITUD",
    "Fragmento",
    "FragmentoRecuperado",
    "IngestaResultado",
    "Retriever",
    "como_contexto",
    "ingerir",
    "reindexar_pendientes",
    "trocear",
]
