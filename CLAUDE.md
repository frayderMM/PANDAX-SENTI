# Instrucciones para Claude Code — SENTI

## Antes de tocar nada
## hola

Lee **[README.md](README.md)**. Es el contrato del sistema: qué decide código
determinista, qué decide el modelo y qué no puede decidir nadie.

## Reglas de trabajo

1. **Todo cambio se ajusta a `README.md`.** Si el código y ese documento
   se contradicen, uno de los dos está mal. Averigua cuál antes de seguir; no
   escribas código que lo incumpla "temporalmente".

2. **Si cambias la lógica, reescribe el documento en el mismo commit.**
   Sobrescribe la sección afectada, no añadas una nota al final. Un documento
   con la versión vieja y la nueva conviviendo es peor que no tenerlo.

3. **Valida siempre antes de dar algo por hecho.**

   ```bash
   cd senti-backend && docker compose -f ../docker-compose.yml run --rm --no-deps \
     -v "$PWD/app:/srv/app:ro" -v "$PWD/tests:/srv/tests:ro" \
     -v "$PWD/pyproject.toml:/srv/pyproject.toml:ro" \
     api sh -c "ruff check app tests && python -m pytest tests/ -q"
   docker compose config --quiet
   ```

   **Los tres montajes hacen falta.** Sin ellos se valida el código que quedó
   dentro de la imagen, no el que acabas de escribir. El de `pyproject.toml`
   es el menos obvio y el que más engaña: si falta, ruff no encuentra la
   selección de reglas del proyecto y aplica sus reglas por defecto — te
   escupe decenas de avisos de estilo que nadie pidió y, entre ese ruido, se
   pierde justo el `F821` por el que se puso el `ruff check`.

   El `ruff check` no es cosmético: detecta nombres usados sin importar. Un
   endpoint al que le falta un import arranca bien, pasa los tests y revienta
   con un 500 la primera vez que alguien lo llama, porque ningún test lo
   ejercita. Ya ocurrió con `GET /reportes`.

   Y si tocaste Android:

   ```bash
   cd senti-android && ./gradlew :app:compileDebugKotlin
   ```

   No declares que algo funciona sin haberlo ejecutado. Si no pudiste
   comprobarlo, dilo.

4. **Borra el código muerto.** Si dejas de usar una función, una rama, un
   parámetro, un import o un archivo entero, elimínalo en el mismo cambio. Nada
   de dejarlo "por si acaso" ni comentado: el historial de git ya lo guarda. En
   un sistema donde un camino no probado puede mandar a alguien a una vía
   cerrada, el código que nadie ejecuta es riesgo, no respaldo.

5. **Nombres.** La app es **SENTI**, plataforma y asistente.

6. **Commits sin atribución a IA.** Ni `Co-Authored-By`, ni "Generated with".
   Mensaje en español, explicando el porqué y no el qué.

7. **Secretos fuera del repositorio.** `.env` nunca se commitea. Antes de
   `git push`, comprueba que no entró: `git ls-files | grep -x .env`.

8. **El código se edita solo en local.** El servidor no es un sitio donde
   escribir: es un sitio donde desplegar.

   ```
   local:    editar → validar → commit → push
   servidor: pull → rebuild → up → TESTEAR
   ```

   **Los tests se ejecutan también en el servidor, después de cada despliegue.**
   Que pasen en local no basta: el servidor tiene otra CPU, otra RAM, otro
   modelo y otro `.env`. Es justo donde aparecen los fallos que en local no se
   ven.

   ```bash
   docker compose run --rm --no-deps api python -m pytest tests/ -q
   curl -s localhost:8000/health/detalle
   ```

   El `/health/detalle` no es opcional: dice si el modelo que el backend tiene
   configurado es el que el servidor de inferencia sirve de verdad, y ese
   desajuste no da error por su cuenta — revienta en la primera pregunta.
   Lo que **no** comprueba es el contexto: `SENTI_LLM_CONTEXT_LENGTH` y el
   `--ctx-size` del contenedor se cotejan a mano, y si no coinciden las
   respuestas se cortan en silencio.

   En el servidor solo se tocan **variables de entorno** (`.env`) y se ejecutan
   `git pull`, `docker compose build`, `docker compose up -d`, los `make` de
   operación y los tests. Nada de `vim` sobre un archivo del repo, ni parches
   en caliente, ni "lo arreglo aquí y luego lo paso". Si algo solo se puede
   arreglar en el servidor, es que falta una variable de entorno; añádela al
   `.env.example` y al `docker-compose.yml` desde local.

   Si al hacer `pull` el servidor reporta cambios locales, no los fusiones:
   averigua quién los hizo y por qué, porque son un parche fuera de git.

## Dónde va cada cosa

| Si cambias… | Toca… | Y actualiza en README.md |
|---|---|---|
| una regla dura | `app/rules/` | la tabla de decisiones |
| el flujo del modelo | `app/orchestrator/` | el diagrama de etapas |
| el esquema de datos | `app/models/` | la tabla de entidades |
| una fuente oficial | `app/sources/registry.py` | la tabla de fuentes |
| un endpoint | `app/api/routers/` | la tabla de la API |

## Lo que nunca se hace

- Meter una decisión de seguridad en el prompt en vez de en el código.
- Dejar que el modelo escriba la fuente, la hora o el nivel oficial.
- Devolver "la ruta menos mala" cuando todas se descartan.
- Presentar el silencio de una fuente como ausencia de peligro.
