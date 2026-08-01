"""SENTI — backend.

SENTI es a la vez la plataforma y el asistente conversacional con el que
habla el ciudadano (§1).

Regla que gobierna todo este paquete: el modelo redacta sobre un resultado ya
verificado (§8). Las decisiones — si una alerta incluye una zona, si una vía
está cerrada, qué ruta se descarta, qué nivel de urgencia aplica — las toma
código determinista en `app.rules` y `app.routing`, nunca Gemma.
"""

__version__ = "0.1.0"
