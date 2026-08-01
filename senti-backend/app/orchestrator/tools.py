"""Herramientas que Gemma puede solicitar (§16).

    El backend valida cada solicitud, ejecuta la herramienta y verifica el
    resultado antes de devolverlo. Gemma nunca ejecuta directamente ni accede
    a la base de datos.

Ese párrafo es el contrato de este módulo, y se traduce en tres barreras que
toda llamada atraviesa:

1. **Registro cerrado.** Si el modelo pide un nombre que no está registrado, no
   pasa nada: no hay ejecución dinámica ni `getattr` sobre un módulo.
2. **Permiso por rol.** Cada herramienta declara el permiso que exige (§6) y se
   comprueba contra el usuario autenticado, no contra lo que diga el modelo.
3. **Argumentos validados.** Los argumentos pasan por Pydantic antes de tocar
   la base de datos. Un modelo de 7 B emite argumentos mal formados con cierta
   frecuencia, y eso tiene que fallar de forma limpia y explicable.

El modelo tampoco elige el usuario: `ToolContext.user` viene del token, nunca
de los argumentos. Sin esto, pedir `consultar_perfil_hogar(usuario="otro")`
sería una fuga del perfil del hogar ajeno — el dato más sensible del sistema
(§13.2).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.security import Permission, Role, has_permission
from app.models import User

logger = logging.getLogger(__name__)


class ToolDenied(PermissionError):
    """El rol del usuario no permite esta herramienta (§6)."""


class ToolNotFound(KeyError):
    """El modelo pidió una herramienta que no existe."""


class ToolArgumentsInvalid(ValueError):
    """Los argumentos no validan contra el esquema declarado."""


@dataclass
class ToolContext:
    """Todo lo que una herramienta puede saber. Nada de esto lo elige el modelo."""

    session: Session
    user: User | None
    ahora: datetime
    modo_ligero: bool = False
    # Fuentes que las herramientas van acumulando; el §32.2 exige que la
    # respuesta las cite todas.
    fuentes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ToolResult:
    """Resultado ya verificado por el backend (§16)."""

    ok: bool
    datos: dict[str, Any] = field(default_factory=dict)
    fuentes: list[dict[str, Any]] = field(default_factory=list)
    # Mensaje para el modelo cuando no hay dato. El §11.3 y el §19 exigen
    # declarar la ausencia en vez de callarla.
    ausencia: str | None = None


# ── Esquemas de argumentos ────────────────────────────────────────────────
class ZonaArgs(BaseModel):
    zona: str = Field(description="Distrito o zona aproximada del usuario")


class SinArgs(BaseModel):
    pass


class RecursosArgs(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tipo: str = Field(default="centro_salud", max_length=64)
    radio_m: float = Field(default=3000.0, gt=0, le=20000)
    # Cuando alguien nombra un sitio —"el hospital del Rebagliati"— busca ese y
    # no el más cercano. Sin este campo la herramienta solo sabía ordenar por
    # distancia, así que devolvía otro y nadie avisaba del cambio.
    nombre: str | None = Field(default=None, max_length=120)


class RutaArgs(BaseModel):
    origen_lat: float = Field(ge=-90, le=90)
    origen_lon: float = Field(ge=-180, le=180)
    # Opcionales: si no hay destino y `hacia_refugio`, el backend elige el
    # recurso validado más cercano (§34.2). El modelo nunca inventa unas
    # coordenadas de destino.
    destino_lat: float | None = Field(default=None, ge=-90, le=90)
    destino_lon: float | None = Field(default=None, ge=-180, le=180)
    tipo_destino: str | None = Field(default=None, max_length=64)
    hacia_refugio: bool = False


class PlanArgs(BaseModel):
    alert_id: str | None = None
    horizonte_horas: int = Field(default=2, ge=1, le=72)


class ReporteArgs(BaseModel):
    via: str = Field(max_length=240, description="Nombre de la vía a consultar")


class WebOficialArgs(BaseModel):
    url: str = Field(
        max_length=600,
        description=(
            "URL HTTPS de una fuente oficial registrada en SENTI. No acepta "
            "blogs, redes sociales ni dominios no registrados."
        ),
    )


class MensajeContactoArgs(BaseModel):
    contexto: str = Field(max_length=500)


class OfflineArgs(BaseModel):
    incluir_plan: bool = True
    incluir_ruta: bool = True
    incluir_telefonos: bool = True


@dataclass
class ToolSpec:
    nombre: str
    descripcion: str
    args_model: type[BaseModel]
    permiso: Permission
    handler: Callable[[ToolContext, BaseModel], ToolResult]

    def openai_schema(self) -> dict[str, Any]:
        esquema = self.args_model.model_json_schema()
        esquema.pop("title", None)
        esquema["additionalProperties"] = False
        return {
            "type": "function",
            "function": {
                "name": self.nombre,
                "description": self.descripcion,
                "parameters": esquema,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def registrar(self, spec: ToolSpec) -> None:
        self._tools[spec.nombre] = spec

    def __contains__(self, nombre: object) -> bool:
        return nombre in self._tools

    def get(self, nombre: str) -> ToolSpec:
        try:
            return self._tools[nombre]
        except KeyError as exc:
            raise ToolNotFound(
                f"El modelo pidió la herramienta '{nombre}', que no existe. "
                f"Disponibles: {sorted(self._tools)}"
            ) from exc

    def esquemas_para(self, rol: Role | None) -> list[dict[str, Any]]:
        """Solo se le ofrecen al modelo las herramientas que el rol permite.

        Ofrecer una herramienta que luego se va a denegar solo consigue que el
        modelo la pida, falle y reintente, gastando el presupuesto de salida.
        """
        if rol is None:
            return []
        return [
            t.openai_schema() for t in self._tools.values() if has_permission(rol, t.permiso)
        ]

    def ejecutar(self, nombre: str, argumentos: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Las tres barreras del módulo, en orden."""
        spec = self.get(nombre)

        if ctx.user is None or not has_permission(ctx.user.role, spec.permiso):
            rol = ctx.user.role.value if ctx.user else "anónimo"
            raise ToolDenied(f"El rol '{rol}' no tiene el permiso '{spec.permiso.value}'")

        try:
            args = spec.args_model.model_validate(argumentos)
        except ValidationError as exc:
            raise ToolArgumentsInvalid(
                f"Argumentos inválidos para '{nombre}': {exc.errors(include_url=False)}"
            ) from exc

        resultado = spec.handler(ctx, args)
        ctx.fuentes.extend(resultado.fuentes)
        logger.info(
            "herramienta=%s usuario=%s ok=%s fuentes=%d",
            nombre,
            ctx.user.id if ctx.user else None,
            resultado.ok,
            len(resultado.fuentes),
        )
        return resultado


registry = ToolRegistry()


def herramienta(
    nombre: str, descripcion: str, args_model: type[BaseModel], permiso: Permission
):
    """Decorador de registro. Mantiene juntos nombre, esquema, permiso y código."""

    def decorador(fn: Callable[[ToolContext, Any], ToolResult]):
        registry.registrar(
            ToolSpec(
                nombre=nombre,
                descripcion=descripcion,
                args_model=args_model,
                permiso=permiso,
                handler=fn,
            )
        )
        return fn

    return decorador
