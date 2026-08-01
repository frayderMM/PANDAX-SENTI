"""Cliente del modelo local, contrato OpenAI (§9).

Sirve sin cambios para las tres formas en que SENTI ejecuta el modelo:

  1. LM Studio en el host          → http://host.docker.internal:1234/v1
  2. LM Studio en el servidor      → http://<ip-servidor>:1234/v1
  3. llama.cpp server-cuda en Docker → http://llama-chat:1234/v1

Es el mismo motor en los tres casos: el backend de LM Studio en esta máquina es
`llama.cpp-linux-x86_64-nvidia-cuda12-avx2`, y el contenedor levanta ese mismo
llama.cpp con el mismo GGUF. Cambiar de uno a otro es cambiar
`SENTI_LLM_BASE_URL`, nada más.

`LLMUnavailable` no es un error excepcional sino un estado previsto: el §29
exige que el nivel rojo responda con el modelo apagado, así que el orquestador
lo captura y cae a plantilla fija.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """El modelo no respondió. Estado previsto, no excepcional (§29)."""


class LLMInvalidOutput(ValueError):
    """El modelo respondió algo que no valida contra el esquema (§25)."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # El JSON tal como lo emitió el modelo. Al devolverle su propia llamada en
    # la vuelta siguiente hay que reenviar ESTA cadena: reserializar el dict
    # con `str()` produce comillas simples de Python, que el servidor rechaza
    # con un 500 sin decir por qué.
    arguments_raw: str = "{}"


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    latencia_ms: float = 0.0
    modelo: str = ""

    @property
    def pide_herramienta(self) -> bool:
        return bool(self.tool_calls)


def _plantilla_sin_herramientas(respuesta: httpx.Response) -> bool:
    """True si el 400 es «esta plantilla no sabe de herramientas».

    Se mira el mensaje y no solo el código: un 400 también puede ser un
    argumento mal formado, y ese sí hay que dejar que falle en vez de
    reintentar en bucle escondiendo el error.
    """
    try:
        mensaje = respuesta.json().get("error", {}).get("message", "")
    except ValueError:
        mensaje = respuesta.text
    return "generate parser" in mensaje or "parser generation failed" in mensaje


def imagen_a_data_uri(datos: bytes, mime: str = "image/jpeg") -> str:
    """Codifica una imagen para el contenido multimodal.

    El GGUF cargado trae `mmproj-google_gemma-4-E2B-it-bf16.gguf`, el proyector de
    visión: sin él el modelo ignora las imágenes en silencio, que es peor que
    fallar. `LLMClient.tiene_vision` lo comprueba al arrancar.
    """
    return f"data:{mime};base64,{base64.b64encode(datos).decode('ascii')}"


class LLMClient:
    """Cliente síncrono. La concurrencia la da Celery, no asyncio (§29)."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ── Diagnóstico ────────────────────────────────────────────────────────
    def modelos(self) -> list[dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as c:
                r = c.get(f"{self.base_url}/models", headers=self._headers())
                r.raise_for_status()
                return r.json().get("data", [])
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"No se pudo listar modelos en {self.base_url}: {exc}") from exc

    def estado(self) -> dict[str, Any]:
        """Estado del modelo para `/health` y para el panel de administración.

        Consulta además el endpoint nativo `/api/v0/models` de LM Studio, que
        expone `loaded_context_length` y `state`. Es lo único que permite
        detectar el desajuste clásico: el contexto que el backend asume no
        coincide con el que el servidor cargó, y las respuestas se cortan sin
        que nada dé error. En llama.cpp ese endpoint no existe y se omite sin
        romper nada.
        """
        info: dict[str, Any] = {"base_url": self.base_url, "modelo_configurado": self.model}
        try:
            modelos = self.modelos()
            info["disponible"] = True
            info["modelos"] = [m.get("id") for m in modelos]
            info["modelo_presente"] = any(m.get("id") == self.model for m in modelos)
        except LLMUnavailable as exc:
            info["disponible"] = False
            info["error"] = str(exc)
            return info

        raiz = self.base_url.removesuffix("/v1")
        ctx: int | None = None

        try:
            with httpx.Client(timeout=5.0) as c:
                r = c.get(f"{raiz}/api/v0/models", headers=self._headers())
                if r.status_code == 200:
                    for m in r.json().get("data", []):
                        if m.get("id") == self.model:
                            ctx = m.get("loaded_context_length")
                            info["state"] = m.get("state")
                            info["tiene_vision"] = m.get("vision")
                            break
        except httpx.HTTPError:
            # llama.cpp no expone /api/v0. No es un fallo: se pregunta abajo.
            pass

        if ctx is None:
            # llama.cpp publica el contexto realmente cargado en `/props`. Sin
            # esta rama la comprobación se saltaba entera en el despliegue real,
            # que es justo donde el desajuste aparece.
            try:
                with httpx.Client(timeout=5.0) as c:
                    r = c.get(f"{raiz}/props", headers=self._headers())
                    if r.status_code == 200:
                        props = r.json()
                        ctx = props.get("default_generation_settings", {}).get("n_ctx")
                        info["tiene_vision"] = bool(props.get("modalities", {}).get("vision"))
            except httpx.HTTPError:
                pass

        info["loaded_context_length"] = ctx
        if ctx is None:
            info["aviso"] = (
                "El servidor no publica el contexto cargado: nadie puede comprobar "
                "que coincide con el que asume SENTI."
            )
        elif ctx != settings.llm_context_length:
            info["aviso"] = (
                f"El servidor cargó {ctx} de contexto pero SENTI asume "
                f"{settings.llm_context_length}. Las respuestas se cortarán sin dar error."
            )
        return info

    # ── Chat ───────────────────────────────────────────────────────────────
    def chat(
        self,
        mensajes: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        # Sin razonamiento, siempre.
        #
        # Gemma 4 razona antes de emitir una llamada a herramienta, y activarlo
        # le costaba ~350 fichas: a 10 fichas/s en CPU son 35 segundos que el
        # ciudadano espera para que el modelo delibere consigo mismo.
        #
        # Se puede quitar porque quien elige la herramienta es el router, que es
        # determinista y no delibera. Si el modelo recibe el catálogo y no pide
        # nada, el pipeline reintenta como redacción pura.
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": mensajes,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if json_schema:
            # Salida estructurada forzada por gramática. Es lo que convierte el
            # §25 ("Gemma devuelve ... en JSON validado") en una garantía del
            # servidor y no en una esperanza sobre el prompt.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "senti", "strict": True, "schema": json_schema},
            }

        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                # No todas las plantillas saben de herramientas. La de Gemma 3
                # no las declara, y llama.cpp rechaza la petición entera con
                # «Unable to generate parser for this template».
                #
                # Perder la respuesta por eso es desproporcionado: quien decide
                # qué herramienta hace falta es el router, y el resultado ya
                # viene verificado en los mensajes. Se reintenta sin catálogo y
                # el modelo redacta igual, que es su único trabajo.
                if r.status_code == 400 and tools and _plantilla_sin_herramientas(r):
                    logger.warning(
                        "La plantilla de %s no admite herramientas; se redacta sin ellas",
                        self.model,
                    )
                    payload.pop("tools", None)
                    payload.pop("tool_choice", None)
                    payload["chat_template_kwargs"] = {"enable_thinking": False}
                    payload["max_tokens"] = max_tokens or settings.llm_max_tokens
                    r = c.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                r.raise_for_status()
                data = r.json()
                latencia = r.elapsed.total_seconds() * 1000
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(f"El modelo no respondió en {self.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Error hablando con el modelo: {exc}") from exc

        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as exc:
            raise LLMUnavailable(f"Respuesta con forma inesperada: {data}") from exc

        llamadas: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            crudo = fn.get("arguments") or "{}"
            try:
                args = json.loads(crudo)
            except json.JSONDecodeError:
                # Pasa cuando el modelo agota `max_tokens` a mitad del JSON.
                # Gemma 4 razona antes de llamar a la herramienta y ese
                # razonamiento consume presupuesto de salida, así que el corte
                # cae justo aquí más a menudo de lo que parece.
                logger.warning("Argumentos de herramienta no parseables: %s", crudo)
                args, crudo = {}, "{}"
            llamadas.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=args,
                    arguments_raw=crudo,
                )
            )

        return ChatResult(
            content=message.get("content"),
            tool_calls=llamadas,
            finish_reason=choice.get("finish_reason"),
            latencia_ms=latencia,
            modelo=data.get("model", self.model),
        )

    def chat_json(
        self,
        mensajes: list[dict[str, Any]],
        json_schema: dict[str, Any],
        **kw: Any,
    ) -> dict[str, Any]:
        """Chat con salida JSON validada (§25)."""
        resultado = self.chat(mensajes, json_schema=json_schema, **kw)
        if not resultado.content:
            raise LLMInvalidOutput("El modelo devolvió contenido vacío")
        try:
            return json.loads(resultado.content)
        except json.JSONDecodeError as exc:
            raise LLMInvalidOutput(
                f"El modelo no devolvió JSON válido: {resultado.content[:200]}"
            ) from exc


class EmbeddingClient:
    """Embeddings para el RAG del §19.

    `nomic-embed-text-v1.5` produce 768 dimensiones y la columna `vector(n)` de
    `document_chunks` se dimensiona con `SENTI_EMBEDDING_DIM`. Si no coinciden,
    la inserción falla en Postgres; `verificar_dimension` lo detecta al
    arrancar en vez de a mitad de una ingesta.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.embedding_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.embedding_model

    def embed(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []
        try:
            with httpx.Client(timeout=60.0) as c:
                r = c.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": textos},
                )
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Error obteniendo embeddings: {exc}") from exc

        ordenados = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in ordenados]

    def verificar_dimension(self) -> int:
        vector = self.embed(["verificación de dimensión"])[0]
        if len(vector) != settings.embedding_dim:
            raise LLMInvalidOutput(
                f"El modelo de embeddings devuelve {len(vector)} dimensiones pero "
                f"SENTI_EMBEDDING_DIM es {settings.embedding_dim}. La columna "
                f"document_chunks.embedding no aceptará estos vectores."
            )
        return len(vector)


_deep: LLMClient | None = None


def get_deep_llm() -> LLMClient:
    """Cliente del modelo profundo (§15, §21.1, §25).

    Mismo contrato OpenAI y misma clase: lo único que cambia es a qué servidor
    apunta, cuántas fichas gasta y cuánto se le deja tardar. Si ambas URLs
    coinciden, se degrada a un solo modelo sin tocar código.
    """
    global _deep
    if _deep is None:
        _deep = LLMClient(
            base_url=settings.llm_deep_base_url,
            model=settings.llm_deep_model,
            timeout=settings.llm_deep_timeout_seconds,
        )
    return _deep


_llm: LLMClient | None = None
_embed: EmbeddingClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def get_embeddings() -> EmbeddingClient:
    global _embed
    if _embed is None:
        _embed = EmbeddingClient()
    return _embed
