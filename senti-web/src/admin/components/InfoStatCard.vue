<script setup lang="ts">
import Icon from "../Icon.vue";

defineProps<{
  icon: string;
  title: string;
  value: string;
  detail: string;
  badge: string;
}>();
</script>

<template>
  <section class="stat-card">
    <span class="stat-card__icon"><Icon :name="icon" :size="17" /></span>
    <div class="stat-card__text">
      <p class="stat-card__title">{{ title }}</p>
      <p class="stat-card__value">{{ value }}</p>
      <p class="stat-card__detail">{{ detail }}</p>
    </div>
    <span class="stat-card__badge">{{ badge }}</span>
  </section>
</template>

<style scoped>
.stat-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 18px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
}

.stat-card__icon {
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

.stat-card__text {
  flex: 1;
  min-width: 0;
}

.stat-card__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--texto-secundario);
}

.stat-card__value {
  margin-top: 3px;
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.stat-card__detail {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.stat-card__badge {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  background: var(--fondo);
  color: var(--texto-secundario);
  font-size: 10.5px;
  font-weight: 700;
}
</style>
