<script setup lang="ts">
import Icon from "./Icon.vue";

defineProps<{
  icon: string;
  title: string;
  description: string;
}>();
</script>

<template>
  <article class="feature-card">
    <span class="feature-card__icon">
      <Icon :name="icon" :size="20" />
    </span>
    <h3 class="feature-card__title">{{ title }}</h3>
    <p class="feature-card__desc">{{ description }}</p>
  </article>
</template>

<style scoped>
.feature-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  height: 100%;
  padding: 18px 16px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.05);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.feature-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(7, 27, 74, 0.09);
}

.feature-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  margin-bottom: 4px;
  border-radius: 11px;
  background: var(--azul-tenue);
  color: var(--azul);
}

.feature-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--azul-oscuro);
}

.feature-card__desc {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.4;
  color: var(--tinta-suave);
}
</style>
