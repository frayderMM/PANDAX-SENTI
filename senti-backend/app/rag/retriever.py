"""Recuperación del RAG (§19).

    Pregunta → búsqueda por palabras y embeddings → selección de fragmentos
    → filtro por peligro, región y vigencia → contexto para el modelo
    → respuesta con fuente

Dos cosas que este módulo NO hace, y son las que lo hacen seguro:

1. **No devuelve nada sin fuente.** Cada fragmento viaja con su documento, su
   institución y su URL. El §19 pone a Gemma en el último lugar de la
   precedencia justamente para que nunca redacte sobre algo sin origen.

2. **No devuelve fragmentos vencidos.** El filtro de vigencia va en la
   consulta SQL, no después: un boletín caducado no debe llegar ni siquiera a
   la fase de ordenación, porque un fragmento vencido bien redactado es más
   peligroso que ninguno.

La búsqueda es híbrida —léxica y semántica— porque ninguna de las dos basta
sola aquí. "Huaico" es un peruanismo que un modelo de embeddings multilingüe
puede situar lejos de "flujo de lodo"; y al revés, buscar "qué hago si sube el
agua" por palabras no encuentra un protocolo titulado "inundación súbita".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.domain import HazardType
from app.llm import LLMUnavailable, get_embeddings
from app.models import Document, DocumentChunk, OfficialSource

logger = logging.getLogger(__name__)

# Cuántos fragmentos se le pasan al modelo. Con `max_tokens: 96` de salida y un
# servidor de CPU, más de tres fragmentos solo alarga el prompt sin cambiar la
# respuesta.
# Fragmentos que llegan al prompt.
#
# Era 3 y se baja a 2: la respuesta se recorta a 320 caracteres (§24), así que
# darle 2 000 de contexto para producir 320 es pagar lectura que no se usa.
# Medido en el servidor, cada fragmento son ~350 fichas y la lectura va a 91
# fichas/s: cuatro segundos de espera por fragmento que el modelo apenas mira.
#
# No baja a 1 porque el corte relativo del 0,92 existe precisamente para dejar
# pasar un segundo fragmento cuando está a la altura del primero, y en una
# consulta que cruza dos temas —«qué llevo y por dónde salgo»— hacen falta los
# dos para no responder a medias.
TOP_K = 2
# Por debajo de esto, el vecino más cercano no se parece lo bastante como para
# citarlo. Preferimos "no pude verificar" (§19) a un fragmento traído por los
# pelos.
# Medido con el corpus real: fragmentos de temas distintos puntúan 0,57-0,63
# entre sí. Un umbral de 0,35 los aceptaba todos, y una foto de un incendio se
# respondía con el protocolo de huaico —la coincidencia más cercana— en vez de
# con "no pude verificar" (§19). Preferimos callar a orientar mal.
UMBRAL_SIMILITUD = 0.62
# Peso de la búsqueda semántica frente a la léxica en la fusión.
PESO_VECTOR = 0.6
# Un fragmento entra solo si se parece al mejor al menos en esta proporción.
# Complementa al umbral absoluto: con un corpus pequeño todo supera 0,35, y sin
# este corte se cuelan dos fragmentos de relleno en cada prompt.
CAIDA_RELATIVA = 0.92

# Tope por fragmento. Un párrafo del §19 entero puede pasar de 700 caracteres,
# y la respuesta final son 320: el resto es lectura que se paga y no se usa.
MAX_CARACTERES_FRAGMENTO = 450


@dataclass(frozen=True)
class FragmentoRecuperado:
    texto: str
    documento: str
    institucion: str | None
    url: str | None
    sha256: str | None
    similitud: float
    vigencia_fin: datetime | None

    def cita(self) -> dict:
        """§11.4 y §12: institución, URL y hash del origen."""
        return {
            "institucion": self.institucion or self.documento,
            "url": self.url,
            "sha256": self.sha256,
            "confianza": "OFICIAL",
        }


class Retriever:
    def __init__(self, session: Session) -> None:
        self.session = session

    def buscar(
        self,
        consulta: str,
        ahora: datetime,
        *,
        hazard: HazardType | None = None,
        region: str | None = None,
        coleccion: str | None = None,
        top_k: int = TOP_K,
    ) -> list[FragmentoRecuperado]:
        """Devuelve los fragmentos vigentes más relevantes, con su fuente."""
        if not consulta.strip():
            return []

        vector: list[float] | None = None
        try:
            vector = get_embeddings().embed([consulta])[0]
        except (LLMUnavailable, IndexError) as exc:
            # Sin embeddings el RAG no se cae: degrada a búsqueda léxica. El
            # §19 pide declarar la ausencia, no quedarse mudo.
            logger.warning("Sin embeddings, se busca solo por palabras: %s", exc)

        candidatos = self._consultar(
            consulta, ahora, vector, hazard=hazard, region=region,
            coleccion=coleccion, limite=top_k * 4,
        )

        # El umbral solo aplica a la similitud coseno. `ts_rank` vive en otra
        # escala —valores de 0,0x— así que compararlo con 0,35 descartaría
        # todos los resultados sin decir por qué. En modo léxico basta el
        # `rank > 0` que ya impone la consulta: significa que alguna palabra
        # coincidió.
        if vector is None:
            seleccion = candidatos[:top_k]
        else:
            seleccion = self._recortar(candidatos, top_k)
        logger.info(
            "rag consulta=%r candidatos=%d sobre_umbral=%d",
            consulta[:60], len(candidatos), len(seleccion),
        )
        return seleccion

    @staticmethod
    def _recortar(
        candidatos: list[FragmentoRecuperado], top_k: int
    ) -> list[FragmentoRecuperado]:
        """Se queda con los que se parecen al mejor, no con los `top_k` primeros.

        Un umbral absoluto no basta. Con un corpus pequeño todo se parece a
        todo: medido con cinco documentos, la mejor coincidencia daba 0,66 y la
        tercera 0,57 hablando de otra cosa. Devolver siempre tres fragmentos
        mete dos irrelevantes en el prompt —caro en CPU— y le da al modelo
        material para responder de lo que no se le preguntó.

        El corte relativo se adapta al tamaño del corpus: si el segundo
        fragmento es casi tan bueno como el primero, entran los dos; si baja de
        golpe, entra solo uno.
        """
        vivos = [c for c in candidatos if c.similitud >= UMBRAL_SIMILITUD]
        if not vivos:
            return []
        mejor = vivos[0].similitud
        piso = mejor * CAIDA_RELATIVA
        return [c for c in vivos if c.similitud >= piso][:top_k]

    def _consultar(
        self,
        consulta: str,
        ahora: datetime,
        vector: list[float] | None,
        *,
        hazard: HazardType | None,
        region: str | None,
        coleccion: str | None,
        limite: int,
    ) -> list[FragmentoRecuperado]:
        tsquery = func.plainto_tsquery(text("'senti_es'::regconfig"), consulta)
        rank_lexico = func.ts_rank(
            func.to_tsvector(text("'senti_es'::regconfig"), DocumentChunk.texto), tsquery
        )

        if vector is not None:
            # `cosine_distance` va de 0 (idéntico) a 2. Se convierte a
            # similitud para poder mezclarla con el rank léxico.
            distancia = DocumentChunk.embedding.cosine_distance(vector)
            similitud = (1.0 - distancia).label("sim_vec")
            puntaje = (PESO_VECTOR * (1.0 - distancia) + (1 - PESO_VECTOR) * rank_lexico)
        else:
            similitud = rank_lexico.label("sim_vec")
            puntaje = rank_lexico

        stmt = (
            select(
                DocumentChunk.texto,
                Document.titulo,
                OfficialSource.institucion,
                Document.url_origen,
                Document.sha256,
                similitud,
                DocumentChunk.vigencia_fin,
                puntaje.label("puntaje"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(OfficialSource, OfficialSource.id == Document.source_id)
            .where(
                # §19: el filtro de vigencia va en la consulta, no después.
                or_(
                    DocumentChunk.vigencia_fin.is_(None),
                    DocumentChunk.vigencia_fin >= ahora,
                ),
                # §19: un documento cuya extracción quedó pendiente porque
                # cambió el formato de origen no se cita hasta revisarlo.
                Document.extraccion_pendiente.is_(False),
            )
            .order_by(text("puntaje DESC"))
            .limit(limite)
        )

        if vector is None:
            # Sin vector, un rank de 0 significa que no coincide ninguna
            # palabra: devolverlo sería ruido puro.
            stmt = stmt.where(rank_lexico > 0)
        if hazard is not None:
            stmt = stmt.where(
                or_(DocumentChunk.hazard_type == hazard, DocumentChunk.hazard_type.is_(None))
            )
        if region:
            stmt = stmt.where(
                or_(DocumentChunk.region.is_(None), DocumentChunk.region.ilike(f"%{region}%"))
            )
        if coleccion:
            stmt = stmt.where(DocumentChunk.coleccion == coleccion)

        filas = self.session.execute(stmt).all()
        return [
            FragmentoRecuperado(
                texto=f[0],
                documento=f[1],
                institucion=f[2],
                url=f[3],
                sha256=f[4],
                similitud=float(f[5] or 0.0),
                vigencia_fin=f[6],
            )
            for f in filas
        ]


def como_contexto(fragmentos: list[FragmentoRecuperado]) -> str:
    """Empaqueta los fragmentos para el prompt, cada uno con su fuente.

    La fuente va pegada al fragmento y no en una lista aparte: si el modelo ve
    tres textos y luego tres fuentes sueltas, los cruza mal. Pegada, la
    atribución sobrevive aunque solo use uno.
    """
    if not fragmentos:
        return ""
    partes = []
    for f in fragmentos:
        origen = f.institucion or f.documento
        # Se recorta el fragmento: en CPU cada ficha de prompt se paga en
        # espera, y el final de un párrafo largo casi nunca aporta a una
        # respuesta de 320 caracteres. Se corta en el último punto para no
        # entregar media frase, que es peor que entregar una menos.
        texto = f.texto.strip()
        if len(texto) > MAX_CARACTERES_FRAGMENTO:
            recorte = texto[:MAX_CARACTERES_FRAGMENTO]
            corte = recorte.rfind(". ")
            texto = (recorte[: corte + 1] if corte > 200 else recorte).rstrip() + " […]"
        partes.append(f"[{origen}] {texto}")
    return "\n\n".join(partes)
