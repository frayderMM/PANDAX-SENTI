<script setup lang="ts">
import Icon from "../Icon.vue";
import type { Gravedad } from "../types";

const nivel = defineModel<Gravedad>({ required: true });

const NIVELES: { value: Gravedad; icon: string; label: string; sub: string }[] = [
  { value: "verde", icon: "shield-check", label: "Verde", sub: "Bajo" },
  { value: "amarillo", icon: "alert-triangle", label: "Amarillo", sub: "Medio" },
  { value: "rojo", icon: "alert-octagon", label: "Rojo", sub: "Alto" },
];
</script>

<template>
  <section class="severity-card">
    <h2 class="severity-card__title">Nivel de gravedad</h2>
    <p class="severity-card__subtitle">Selecciona el nivel de gravedad de la alerta.</p>

    <div class="severity-card__options">
      <button
        v-for="n in NIVELES"
        :key="n.value"
        type="button"
        class="severity-option"
        :class="[`severity-option--${n.value}`, { 'severity-option--active': nivel === n.value }]"
        :aria-pressed="nivel === n.value"
        @click="nivel = n.value"
      >
        <span class="severity-option__icon"><Icon :name="n.icon" :size="19" /></span>
        <strong>{{ n.label }}</strong>
        <small>{{ n.sub }}</small>
      </button>
    </div>
  </section>
</template>

<style scoped>
.severity-card {
  padding: 20px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
}

.severity-card__title {
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.severity-card__subtitle {
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--texto-secundario);
}

.severity-card__options {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 16px;
}

.severity-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 6px;
  border: 1.5px solid var(--borde);
  border-radius: 14px;
  background: var(--superficie);
  color: var(--azul-oscuro);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.severity-option:hover {
  transform: translateY(-2px);
}

.severity-option__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--fondo);
  color: var(--texto-secundario);
}

.severity-option strong {
  font-size: 12.5px;
  font-weight: 700;
}

.severity-option small {
  font-size: 11px;
  color: var(--texto-secundario);
}

.severity-option--verde.severity-option--active {
  border-color: var(--verde);
  background: var(--verde-tenue);
}

.severity-option--verde.severity-option--active .severity-option__icon {
  background: #ffffff;
  color: var(--verde);
}

.severity-option--amarillo.severity-option--active {
  border-color: var(--amarillo);
  background: var(--amarillo-tenue);
}

.severity-option--amarillo.severity-option--active .severity-option__icon {
  background: #ffffff;
  color: var(--amarillo);
}

.severity-option--rojo.severity-option--active {
  border-color: var(--rojo);
  background: var(--rojo-tenue);
}

.severity-option--rojo.severity-option--active .severity-option__icon {
  background: #ffffff;
  color: var(--rojo);
}

.severity-option:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}
</style>
