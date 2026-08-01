<script setup lang="ts">
import Icon from "./Icon.vue";

defineProps<{
  title: string;
  subtitle: string;
}>();
</script>

<template>
  <header class="admin-header">
    <div>
      <h1 class="admin-header__title">{{ title }}</h1>
      <p class="admin-header__subtitle">{{ subtitle }}</p>
    </div>

    <div class="admin-header__actions">
      <button type="button" class="admin-header__icon-btn" aria-label="Ayuda">
        <Icon name="help-circle" :size="19" />
      </button>

      <button type="button" class="admin-header__icon-btn" aria-label="Notificaciones (3 sin leer)">
        <Icon name="bell" :size="19" />
        <span class="admin-header__badge" aria-hidden="true">3</span>
      </button>

      <div class="admin-header__profile">
        <span class="admin-header__avatar">OP</span>
        <Icon name="chevron-down" :size="16" class="admin-header__profile-chevron" />
      </div>
    </div>
  </header>
</template>

<style scoped>
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.admin-header__title {
  font-size: 26px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.admin-header__subtitle {
  margin-top: 4px;
  font-size: 14px;
  color: var(--texto-secundario);
}

.admin-header__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.admin-header__icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--borde);
  border-radius: 50%;
  background: var(--superficie);
  color: var(--texto-secundario);
}

.admin-header__icon-btn:hover {
  background: var(--fondo);
  color: var(--azul);
}

.admin-header__icon-btn:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}

.admin-header__badge {
  position: absolute;
  top: -3px;
  right: -3px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--rojo);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
}

.admin-header__profile {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px 4px 4px;
  border-radius: 999px;
}

.admin-header__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--azul);
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
}

.admin-header__profile-chevron {
  color: var(--texto-secundario);
}

@media (max-width: 640px) {
  .admin-header {
    flex-direction: column;
  }
}
</style>
