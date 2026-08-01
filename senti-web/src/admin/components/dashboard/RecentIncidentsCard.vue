<script setup lang="ts">
import Icon from "../../Icon.vue";
import type { Incidencia } from "../../types";

defineProps<{
  incidencias: Incidencia[];
}>();

const emit = defineEmits<{
  (e: "ver-todas"): void;
}>();
</script>

<template>
  <section class="incidents-card">
    <header class="incidents-card__header">
      <h2 class="incidents-card__title">Incidencias recientes</h2>
      <button type="button" class="incidents-card__link" @click="emit('ver-todas')">Ver todas</button>
    </header>

    <p v-if="!incidencias.length" class="incidents-card__empty">Sin incidencias registradas en esta zona.</p>

    <ul v-else class="incidents-card__list">
      <li v-for="incidencia in incidencias" :key="incidencia.id" class="incidents-card__row">
        <span class="incidents-card__icon"><Icon :name="incidencia.icono" :size="16" /></span>
        <span class="incidents-card__text">
          <strong>{{ incidencia.titulo }}</strong>
          <small>{{ incidencia.ubicacion }} · {{ incidencia.hora }}</small>
        </span>
        <span
          class="incidents-card__badge"
          :class="{ 'incidents-card__badge--atendida': incidencia.estado === 'Atendida' }"
        >
          {{ incidencia.estado }}
        </span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.incidents-card {
  display: flex;
  flex-direction: column;
  padding: 20px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
  height: 100%;
}

.incidents-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.incidents-card__title {
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.incidents-card__link {
  border: none;
  background: none;
  padding: 0;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--azul);
}

.incidents-card__link:hover {
  text-decoration: underline;
}

.incidents-card__empty {
  font-size: 13px;
  color: var(--texto-secundario);
}

.incidents-card__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.incidents-card__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 6px;
  border-radius: 10px;
}

.incidents-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 9px;
  background: var(--azul-tenue);
  color: var(--azul);
}

.incidents-card__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.incidents-card__text strong {
  font-size: 13px;
  color: var(--azul-oscuro);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.incidents-card__text small {
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.incidents-card__badge {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  background: var(--amarillo-tenue);
  color: #a06400;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.incidents-card__badge--atendida {
  background: var(--verde-tenue);
  color: #146b3e;
}

.incidents-card__link:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}
</style>
