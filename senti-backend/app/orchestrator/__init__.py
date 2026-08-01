"""Orquestador de IA y seguridad (§8).

Es la única capa que habla con el modelo. Todo lo que entra al modelo ya está
verificado y todo lo que sale pasa por `app.rules.response` antes de llegar al
usuario.
"""

from app.orchestrator.pipeline import EntradaUsuario, Orchestrator, SalidaOrquestador
from app.orchestrator.tools import ToolContext, ToolResult, registry

__all__ = [
    "EntradaUsuario",
    "Orchestrator",
    "SalidaOrquestador",
    "ToolContext",
    "ToolResult",
    "registry",
]
