<script setup lang="ts">
import Icon from "../../Icon.vue";

defineProps<{
  icon: string;
  title: string;
  value: string;
  detail?: string;
}>();
</script>

<template>
  <div class="metric-item">
    <span class="metric-item__icon"><Icon :name="icon" :size="16" /></span>
    <div class="metric-item__text">
      <p class="metric-item__title">{{ title }}</p>
      <p class="metric-item__value">{{ value }}</p>
      <p v-if="detail" class="metric-item__detail">{{ detail }}</p>
    </div>
  </div>
</template>

<style scoped>
.metric-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--borde);
  border-radius: 12px;
}

.metric-item__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border-radius: 9px;
  background: var(--fondo);
  color: var(--azul);
}

.metric-item__text {
  min-width: 0;
}

.metric-item__title {
  font-size: 11px;
  font-weight: 600;
  color: var(--texto-secundario);
}

.metric-item__value {
  margin-top: 2px;
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.metric-item__detail {
  margin-top: 1px;
  font-size: 10.5px;
  color: var(--texto-secundario);
}
</style>
