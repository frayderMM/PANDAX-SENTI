<script setup lang="ts">
import Icon from "../../Icon.vue";
import type { AlertaResumen } from "../../types";

defineProps<{
  alertas: AlertaResumen[];
}>();

const emit = defineEmits<{
  (e: "ver-todas"): void;
  (e: "abrir", alerta: AlertaResumen): void;
}>();

const ETIQUETA_COLOR: Record<AlertaResumen["color"], string> = {
  roja: "Roja",
  amarilla: "Amarilla",
  verde: "Verde",
};
</script>

<template>
  <section class="alerts-card">
    <header class="alerts-card__header">
      <h2 class="alerts-card__title">Últimas alertas</h2>
      <button type="button" class="alerts-card__link" @click="emit('ver-todas')">Ver todas</button>
    </header>

    <p v-if="!alertas.length" class="alerts-card__empty">Sin alertas registradas en esta zona.</p>

    <ul v-else class="alerts-card__list">
      <li v-for="alerta in alertas" :key="alerta.id">
        <button type="button" class="alerts-card__row" @click="emit('abrir', alerta)">
          <span class="alerts-card__badge" :class="`alerts-card__badge--${alerta.color}`">
            {{ ETIQUETA_COLOR[alerta.color] }}
          </span>
          <span class="alerts-card__text">
            <strong>{{ alerta.titulo }}</strong>
            <small>{{ alerta.zona }} · {{ alerta.hora }}</small>
          </span>
          <Icon name="chevron-right" :size="16" class="alerts-card__chevron" />
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.alerts-card {
  display: flex;
  flex-direction: column;
  padding: 20px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
  height: 100%;
}

.alerts-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.alerts-card__title {
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.alerts-card__link {
  border: none;
  background: none;
  padding: 0;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--azul);
}

.alerts-card__link:hover {
  text-decoration: underline;
}

.alerts-card__empty {
  font-size: 13px;
  color: var(--texto-secundario);
}

.alerts-card__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alerts-card__row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 6px;
  border: none;
  background: none;
  border-radius: 10px;
  text-align: left;
}

.alerts-card__row:hover {
  background: var(--fondo);
}

.alerts-card__badge {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
}

.alerts-card__badge--roja {
  background: var(--rojo);
}

.alerts-card__badge--amarilla {
  background: var(--amarillo);
}

.alerts-card__badge--verde {
  background: var(--verde);
}

.alerts-card__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.alerts-card__text strong {
  font-size: 13px;
  color: var(--azul-oscuro);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alerts-card__text small {
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.alerts-card__chevron {
  flex-shrink: 0;
  color: var(--texto-secundario);
}

.alerts-card__row:focus-visible,
.alerts-card__link:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}
</style>
