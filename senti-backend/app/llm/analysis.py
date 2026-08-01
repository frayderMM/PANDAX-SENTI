"""Análisis con el modelo profundo: documentos e imágenes (§15, §21.1, §25).

Las dos funciones de este módulo devuelven **propuestas**, nunca hechos.

- `extraer_alerta` lee un boletín oficial y propone los campos. El §15 es
  explícito: Gemma no puede cambiar el nivel oficial, inventar zonas afectadas,
  extender la vigencia ni publicar una alerta por sí sola. Lo que sale de aquí
  pasa por un operador antes de existir como alerta.
- `categorizar_reporte` propone tipo y descripción para que **el ciudadano los
  revise y publique** (§21.1). Su propuesta no publica nada.

Ambas usan `response_format` con esquema JSON, así que la forma la garantiza el
servidor por gramática y no el prompt. Y ambas se validan otra vez al recibir,
porque el §25 dice que el backend verifica antes de enviar cualquier mensaje, y
confiar en que el servidor cumplió no es verificar.
"""

from __future__ import annotations

import logging
from io import BytesIO

from pydantic import ValidationError

from app.core.config import settings
from app.llm.client import LLMInvalidOutput, get_deep_llm, imagen_a_data_uri
from app.llm.prompts import SYSTEM_CATEGORIA_REPORTE, SYSTEM_EXTRACCION_ALERTA
from app.llm.schemas import AlertaExtraida, CategoriaReporte, json_schema_de

logger = logging.getLogger(__name__)

# Un boletín entero no cabe en el contexto de 8192 junto al esquema y la
# respuesta. Se recorta por delante: los campos que interesan —número, nivel,
# zonas, vigencia— van siempre en la cabecera del documento.
MAX_CARACTERES_DOCUMENTO = 6000


def extraer_texto_pdf(contenido: bytes) -> str:
    """Texto plano de un PDF, página por página, para pasarlo a `extraer_alerta`.

    Solo lee texto ya embebido en el PDF. Un PDF escaneado (imagen sin capa de
    texto) devuelve una cadena vacía — no hay OCR aquí — y quien llame debe
    tratar eso como "no se pudo leer", nunca como "documento vacío de verdad".
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        lector = PdfReader(BytesIO(contenido))
    except PdfReadError as exc:
        raise LLMInvalidOutput(f"El archivo no es un PDF válido: {exc}") from exc

    paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    return "\n".join(paginas).strip()


def extraer_alerta(
    texto_documento: str,
    *,
    titulo: str | None = None,
    entidad: str | None = None,
) -> AlertaExtraida:
    """§15: extrae los campos de un boletín oficial. Devuelve una PROPUESTA."""
    if not texto_documento.strip():
        raise LLMInvalidOutput("El documento está vacío")

    recorte = texto_documento[:MAX_CARACTERES_DOCUMENTO]
    if len(texto_documento) > MAX_CARACTERES_DOCUMENTO:
        logger.info(
            "Documento recortado de %d a %d caracteres para la extracción",
            len(texto_documento), MAX_CARACTERES_DOCUMENTO,
        )

    contexto = []
    if titulo:
        contexto.append(f"Título: {titulo}")
    if entidad:
        contexto.append(f"Entidad emisora declarada: {entidad}")
    contexto.append("Documento:")
    contexto.append(recorte)

    datos = get_deep_llm().chat_json(
        [
            {"role": "system", "content": SYSTEM_EXTRACCION_ALERTA},
            {"role": "user", "content": "\n".join(contexto)},
        ],
        json_schema_de(AlertaExtraida),
        max_tokens=settings.llm_deep_max_tokens,
        # Extraer no es redactar: cualquier creatividad aquí es una alerta
        # inventada.
        temperature=0.0,
    )

    try:
        return AlertaExtraida.model_validate(datos)
    except ValidationError as exc:
        raise LLMInvalidOutput(
            f"La extracción no valida contra el esquema del §15: "
            f"{exc.errors(include_url=False)}"
        ) from exc


def categorizar_reporte(
    descripcion: str,
    *,
    imagen: bytes | None = None,
    imagen_mime: str = "image/jpeg",
) -> CategoriaReporte:
    """§21.1: propone tipo y descripción de un reporte ciudadano.

    Si hay imagen la usa, y por eso corre en el modelo profundo: es el único
    que carga el proyector de visión. Lo que devuelve sobre la foto son
    observaciones, nunca conclusiones (§25) — el esquema no ofrece ningún campo
    donde escribir una.
    """
    contenido: object = descripcion or "El ciudadano no escribió descripción."
    if imagen is not None:
        contenido = [
            {"type": "text", "text": descripcion or "Describe lo observable en la imagen."},
            {
                "type": "image_url",
                "image_url": {"url": imagen_a_data_uri(imagen, imagen_mime)},
            },
        ]

    datos = get_deep_llm().chat_json(
        [
            {"role": "system", "content": SYSTEM_CATEGORIA_REPORTE},
            {"role": "user", "content": contenido},
        ],
        json_schema_de(CategoriaReporte),
        max_tokens=settings.llm_deep_max_tokens,
        temperature=0.1,
    )

    try:
        propuesta = CategoriaReporte.model_validate(datos)
    except ValidationError as exc:
        raise LLMInvalidOutput(
            f"La propuesta no valida contra el esquema del §21.1: "
            f"{exc.errors(include_url=False)}"
        ) from exc

    # El §21.1 exige que el ciudadano revise antes de publicar. Que el modelo
    # se declare seguro no cambia eso, así que la bandera se fuerza aquí en vez
    # de confiar en lo que haya devuelto.
    return propuesta.model_copy(update={"requiere_revision_humana": True})
