"""Contrato de salida del modelo en las tareas que devuelven JSON (§15, §21.1, §25).

El chat no pasa por aquí: ahí el modelo redacta texto y quien lo verifica es la
guardia de lenguaje de `rules/response.py`. Estos esquemas son el contrato de
las dos tareas de análisis, que sí devuelven campos estructurados.

Se usan de dos formas a la vez:

1. Se convierten a JSON Schema y se envían como `response_format`, para que el
   servidor fuerce la forma por gramática.
2. Se validan otra vez al recibir, porque el §25 dice que el backend verifica
   antes de enviar cualquier mensaje — y confiar en que el servidor cumplió no
   es verificar.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain import HazardType


class ObservacionImagen(BaseModel):
    """§25: sobre imágenes devuelve observaciones, NO conclusiones.

        Permitido: "Se observa material sobre parte de la vía."
        Prohibido: "La carretera está libre por el lado izquierdo."

    Por eso el campo se llama `observacion` y existe `confianza`, pero no
    existe ningún campo del tipo `transitable` o `es_seguro`: el esquema no
    ofrece un lugar donde escribir una conclusión.
    """

    observacion: str = Field(description="Lo que se ve, sin interpretar si es seguro o no")
    confianza: float = Field(ge=0.0, le=1.0, default=0.5)


class AlertaExtraida(BaseModel):
    """§15: extracción documental. Lo que el modelo propone, no lo que se publica.

    Ninguno de estos campos entra en `alerts` sin pasar por el operador o por
    un conector oficial: el §15 dice que Gemma no puede cambiar el nivel
    oficial, inventar zonas afectadas, extender la vigencia ni publicar una
    alerta por sí sola.
    """

    tipo_evento: HazardType
    titulo: str = Field(max_length=300)
    nivel_detectado: str | None = Field(default=None, max_length=64)
    entidad_emisora: str | None = Field(default=None, max_length=160)
    zonas_mencionadas: list[str] = Field(default_factory=list, max_length=40)
    vigencia_inicio_texto: str | None = None
    vigencia_fin_texto: str | None = None
    numero_documento: str | None = Field(default=None, max_length=120)
    recomendaciones: list[str] = Field(default_factory=list, max_length=15)
    resumen_ciudadano: str = Field(max_length=1000)
    terminos_tecnicos: dict[str, str] = Field(default_factory=dict)
    # §15: "detecta datos faltantes e indica cuando no puede confirmar algo".
    datos_faltantes: list[str] = Field(default_factory=list)


class CategoriaReporte(BaseModel):
    """§21.1: Gemma propone categoría y descripción; el ciudadano revisa y publica."""

    tipo: HazardType
    descripcion_propuesta: str = Field(max_length=400)
    observaciones_imagen: list[ObservacionImagen] = Field(default_factory=list)
    requiere_revision_humana: bool = True


def json_schema_de(modelo: type[BaseModel]) -> dict:
    """JSON Schema listo para `response_format` de LM Studio / llama.cpp.

    Se fuerza `additionalProperties: false` en todo el árbol: sin eso, el modo
    `strict` de algunos servidores acepta campos extra y el modelo se inventa
    claves que luego nadie mira.
    """
    esquema = modelo.model_json_schema()
    _cerrar(esquema)
    return esquema


def _cerrar(nodo: object) -> None:
    if isinstance(nodo, dict):
        if nodo.get("type") == "object":
            nodo.setdefault("additionalProperties", False)
        for valor in nodo.values():
            _cerrar(valor)
    elif isinstance(nodo, list):
        for item in nodo:
            _cerrar(item)
