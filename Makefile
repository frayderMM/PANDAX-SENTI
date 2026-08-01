.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help
help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Arranque ───────────────────────────────────────────────────────────────
.PHONY: up
up: ## Levanta el núcleo (db, valkey, api, worker, beat)
	$(COMPOSE) up -d

.PHONY: up-geo
up-geo: ## Añade Valhalla y Martin (descarga y construye teselas: lento)
	$(COMPOSE) --profile geo up -d

.PHONY: up-llm
up-llm: ## Sirve el modelo en contenedor (requiere nvidia-container-toolkit)
	$(COMPOSE) --profile llm-cuda up -d

.PHONY: up-obs
up-obs: ## Prometheus y Grafana
	$(COMPOSE) --profile obs up -d

.PHONY: down
down: ## Para todo sin borrar datos
	$(COMPOSE) --profile geo --profile llm-cuda --profile obs down

.PHONY: reset
reset: ## Para todo y BORRA los volúmenes (base de datos incluida)
	$(COMPOSE) --profile geo --profile llm-cuda --profile obs down -v

.PHONY: logs
logs: ## Sigue los logs de la API
	$(COMPOSE) logs -f api

.PHONY: ps
ps: ## Estado de los servicios
	$(COMPOSE) ps

# ── Base de datos ──────────────────────────────────────────────────────────
.PHONY: db-init
db-init: ## Crea extensiones, tablas y catálogo base
	$(COMPOSE) run --rm api python -m app.db.bootstrap --seed

.PHONY: db-demo
db-demo: ## Además carga el escenario del §34 (Lurigancho-Chosica)
	$(COMPOSE) run --rm api python -m app.db.bootstrap --demo

.PHONY: db-recursos
db-recursos: ## Importa los establecimientos de OSM (~58 000, tarda: usa Overpass)
	$(COMPOSE) run --rm api python -m app.db.importar_recursos --bbox $(or $(BBOX),peru)

.PHONY: db-shell
db-shell: ## psql contra la base de datos
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-senti} -d $${POSTGRES_DB:-senti}

# ── Calidad ────────────────────────────────────────────────────────────────
.PHONY: test
test: ## Ejecuta los tests de las reglas duras (§32)
	$(COMPOSE) run --rm --no-deps api python -m pytest tests/ -q

.PHONY: lint
lint: ## Ruff sobre el backend
	$(COMPOSE) run --rm --no-deps api ruff check app tests

.PHONY: check-modelo
check-modelo: ## Comprueba que el modelo local responde y con qué contexto
	@curl -s http://localhost:$${API_HOST_PORT:-8000}/health/detalle | python3 -m json.tool

.PHONY: check-fuentes
check-fuentes: ## Estado de las fuentes oficiales (§11.3)
	@curl -s http://localhost:$${API_HOST_PORT:-8000}/fuentes/estado | python3 -m json.tool

.PHONY: healthcheck
healthcheck: ## Fuerza una ronda del healthcheck de fuentes
	$(COMPOSE) run --rm api python -c \
		"from app.tasks.celery_app import healthcheck_fuentes; print(healthcheck_fuentes())"

# ── Clientes ───────────────────────────────────────────────────────────────
.PHONY: android
android: ## Compila el cliente Android
	cd senti-android && ./gradlew :app:assembleDebug

.PHONY: modelos
modelos: ## Descarga los GGUF (Docker NO los baja solo)
	./scripts/descargar-modelos.sh $(VARIANTE)
