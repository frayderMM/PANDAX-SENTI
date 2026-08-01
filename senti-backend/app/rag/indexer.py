"""Ingesta documental al RAG (§19).

    Para SENAMHI, SUTRAN, SIGRID, DIHIDRONAV y COEN la ingesta documental
    extrae número, fecha, nivel, zona, inicio y fin; guarda copia y hash; y
    marca el dato como pendiente cuando el formato de origen cambia.

El hash cumple dos funciones distintas y ambas importan:

- **§12, autenticidad.** Todo contenido oficial ingerido se almacena con hash y
  URL de origen, y la respuesta cita ambos. Es la medida contra el precedente
  de suplantación que describe el §12.
- **Idempotencia.** Reingerir el mismo boletín no duplica fragmentos ni gasta
  embeddings, que en CPU son lo caro de esta operación.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.crypto import content_hash
from app.domain import HazardType
from app.llm import LLMUnavailable, get_embeddings
from app.models import Document, DocumentChunk, OfficialSource
from app.rag.chunker import trocear

logger = logging.getLogger(__name__)

# Los embeddings se piden por lotes: una llamada HTTP por fragmento sobre un
# servidor de CPU multiplica la latencia por el número de trozos sin motivo.
LOTE = 16


class IngestaResultado:
    def __init__(self, document_id, fragmentos: int, ya_existia: bool, sin_embeddings: bool):
        self.document_id = document_id
        self.fragmentos = fragmentos
        self.ya_existia = ya_existia
        self.sin_embeddings = sin_embeddings

    def __repr__(self) -> str:
        return (
            f"IngestaResultado(fragmentos={self.fragmentos}, "
            f"ya_existia={self.ya_existia}, sin_embeddings={self.sin_embeddings})"
        )


def ingerir(
    session: Session,
    *,
    titulo: str,
    texto: str,
    source_slug: str | None = None,
    url_origen: str | None = None,
    coleccion: str | None = None,
    hazard: HazardType | None = None,
    region: str | None = None,
    vigencia_fin: datetime | None = None,
    nivel: str | None = None,
    numero: str | None = None,
    mime_type: str = "text/plain",
) -> IngestaResultado:
    """Indexa un documento oficial. Idempotente por hash de contenido."""
    ahora = datetime.now(UTC)
    sha = content_hash(texto.encode("utf-8"))

    existente = session.scalar(select(Document).where(Document.sha256 == sha))
    if existente is not None:
        n = session.scalar(
            select(DocumentChunk.id).where(DocumentChunk.document_id == existente.id).limit(1)
        )
        if n is not None:
            logger.info("Documento ya ingerido (sha=%s), se omite", sha[:12])
            return IngestaResultado(existente.id, 0, ya_existia=True, sin_embeddings=False)
        documento = existente
    else:
        source_id = None
        if source_slug:
            source_id = session.scalar(
                select(OfficialSource.id).where(OfficialSource.slug == source_slug)
            )
        documento = Document(
            source_id=source_id,
            titulo=titulo,
            url_origen=url_origen,
            sha256=sha,
            mime_type=mime_type,
            coleccion=coleccion,
            hazard_type=hazard,
            nivel=nivel,
            numero=numero,
            zona=region,
            vigencia_fin=vigencia_fin,
            texto_completo=texto,
            ingested_at=ahora,
        )
        session.add(documento)
        session.flush()

    fragmentos = trocear(texto)
    if not fragmentos:
        return IngestaResultado(documento.id, 0, ya_existia=False, sin_embeddings=False)

    # Reindexar sustituye: dejar los fragmentos viejos junto a los nuevos haría
    # que la misma frase apareciera dos veces con vigencias distintas.
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == documento.id))

    vectores: list[list[float] | None] = [None] * len(fragmentos)
    sin_embeddings = False
    try:
        cliente = get_embeddings()
        for i in range(0, len(fragmentos), LOTE):
            lote = fragmentos[i : i + LOTE]
            for j, v in enumerate(cliente.embed([f.texto for f in lote])):
                vectores[i + j] = v
    except LLMUnavailable as exc:
        # Se indexa igual: la búsqueda léxica funciona sin vectores y es
        # preferible a perder el documento. `reindexar_pendientes` los
        # completa cuando el servidor de embeddings vuelva.
        logger.warning("Sin embeddings; se indexa solo texto: %s", exc)
        sin_embeddings = True

    for frag, vector in zip(fragmentos, vectores, strict=True):
        session.add(
            DocumentChunk(
                document_id=documento.id,
                orden=frag.orden,
                texto=frag.texto,
                embedding=vector,
                coleccion=coleccion,
                hazard_type=hazard,
                region=region,
                vigencia_fin=vigencia_fin,
                metadatos={"nivel": nivel, "numero": numero} if (nivel or numero) else None,
            )
        )

    logger.info("Ingerido %r: %d fragmentos", titulo[:50], len(fragmentos))
    return IngestaResultado(documento.id, len(fragmentos), False, sin_embeddings)


def reindexar_pendientes(session: Session, limite: int = 200) -> int:
    """Calcula los embeddings que quedaron a medias.

    Existe porque `ingerir` no aborta cuando el servidor de embeddings está
    caído: un documento indexado solo por texto sigue siendo útil, pero hay que
    completarlo después o la búsqueda semántica lo ignora para siempre.
    """
    pendientes = list(
        session.scalars(
            select(DocumentChunk).where(DocumentChunk.embedding.is_(None)).limit(limite)
        )
    )
    if not pendientes:
        return 0

    cliente = get_embeddings()
    completados = 0
    for i in range(0, len(pendientes), LOTE):
        lote = pendientes[i : i + LOTE]
        for chunk, vector in zip(lote, cliente.embed([c.texto for c in lote]), strict=True):
            chunk.embedding = vector
            completados += 1

    logger.info("Reindexados %d fragmentos", completados)
    return completados
