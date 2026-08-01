<script setup lang="ts">
import Icon from "../../Icon.vue";

withDefaults(
  defineProps<{
    icon: string;
    title: string;
    value: string;
    detail: string;
    tone?: "azul" | "violeta" | "rojo" | "amarillo";
    valueBadge?: boolean;
  }>(),
  { tone: "azul", valueBadge: false },
);
</script>

<template>
  <article class="summary-card">
    <span class="summary-card__icon" :class="`summary-card__icon--${tone}`">
      <Icon :name="icon" :size="18" />
    </span>
    <div class="summary-card__text">
      <p class="summary-card__title">{{ title }}</p>
      <p v-if="valueBadge" class="summary-card__value-badge" :class="`summary-card__value-badge--${tone}`">
        {{ value }}
      </p>
      <p v-else class="summary-card__value">{{ value }}</p>
      <p class="summary-card__detail" :class="{ 'summary-card__detail--rojo': tone === 'rojo' }">
        {{ detail }}
      </p>
    </div>
  </article>
</template>

<style scoped>
.summary-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 18px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
}

.summary-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 11px;
}

.summary-card__icon--azul {
  background: var(--azul-tenue);
  color: var(--azul);
}

.summary-card__icon--violeta {
  background: #efeafe;
  color: #6f4fe0;
}

.summary-card__icon--rojo {
  background: var(--rojo-tenue);
  color: var(--rojo);
}

.summary-card__icon--amarillo {
  background: var(--amarillo-tenue);
  color: var(--amarillo);
}

.summary-card__text {
  min-width: 0;
}

.summary-card__title {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--texto-secundario);
}

.summary-card__value {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.summary-card__value-badge {
  display: inline-flex;
  width: fit-content;
  margin-top: 4px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 800;
}

.summary-card__value-badge--amarillo {
  background: var(--amarillo-tenue);
  color: #a06400;
}

.summary-card__value-badge--rojo {
  background: var(--rojo-tenue);
  color: var(--rojo);
}

.summary-card__value-badge--azul {
  background: var(--azul-tenue);
  color: var(--azul);
}

.summary-card__value-badge--violeta {
  background: #efeafe;
  color: #6f4fe0;
}

.summary-card__detail {
  margin-top: 2px;
  font-size: 12px;
  color: var(--texto-secundario);
}

.summary-card__detail--rojo {
  color: var(--rojo);
  font-weight: 600;
}
</style>
