<script setup lang="ts">
import Icon from "../Icon.vue";

defineProps<{
  nombre: string;
  detalle: string;
}>();
</script>

<template>
  <section class="zona-card">
    <div class="zona-card__info">
      <span class="zona-card__icon"><Icon name="map-pin" :size="17" /></span>
      <div class="zona-card__text">
        <p class="zona-card__title">Zona afectada</p>
        <p class="zona-card__nombre">{{ nombre }}</p>
        <p class="zona-card__detalle">{{ detalle }}</p>
      </div>
    </div>

    <svg
      class="zona-card__map"
      viewBox="0 0 96 64"
      role="img"
      aria-label="Mapa esquemático de la zona afectada"
    >
      <rect width="96" height="64" rx="10" fill="#eef2fb" />
      <g stroke="#c9d4ef" stroke-width="1">
        <path d="M0 16H96M0 32H96M0 48H96" />
        <path d="M24 0V64M48 0V64M72 0V64" />
      </g>
      <path
        d="M30 20 L70 16 L78 40 L52 50 L26 42 Z"
        fill="#0b55f5"
        fill-opacity="0.22"
        stroke="#0b55f5"
        stroke-width="1.4"
      />
      <circle cx="50" cy="32" r="3" fill="#0b55f5" />
    </svg>
  </section>
</template>

<style scoped>
.zona-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
}

.zona-card__info {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.zona-card__icon {
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

.zona-card__text {
  min-width: 0;
}

.zona-card__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--texto-secundario);
}

.zona-card__nombre {
  margin-top: 3px;
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.zona-card__detalle {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.zona-card__map {
  width: 84px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 10px;
}

@media (max-width: 380px) {
  .zona-card__map {
    display: none;
  }
}
</style>
