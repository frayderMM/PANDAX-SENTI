<script setup lang="ts">
import Icon from "./Icon.vue";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: "home" },
  { to: "/alertas", label: "Alertas", icon: "bell" },
];
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <img class="sidebar__logo" src="/senti-icono.png" alt="Senti" />
      <div>
        <p class="sidebar__brand-name">Senti</p>
        <p class="sidebar__brand-tagline">Operador Municipal</p>
      </div>
    </div>

    <nav class="sidebar__nav">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="sidebar__link"
        active-class="sidebar__link--active"
      >
        <Icon :name="item.icon" :size="19" />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="sidebar__footer">
      <div class="sidebar__org">
        <img class="sidebar__org-icon" src="/senti-icono.png" alt="" aria-hidden="true" />
        <span class="sidebar__org-text">
          <strong>Protección Civil</strong>
          <small>Municipio de Centro</small>
        </span>
        <Icon name="chevron-down" :size="16" class="sidebar__org-chevron" />
      </div>

      <div class="sidebar__status">
        <span class="sidebar__status-text">
          <small>Operador</small>
          <strong>En línea</strong>
        </span>
        <span class="sidebar__status-dot" aria-hidden="true"></span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
  padding: 24px 18px;
  background: var(--superficie);
  border-right: 1px solid var(--borde);
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 6px 24px;
}

.sidebar__logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  object-fit: cover;
}

.sidebar__brand-name {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.sidebar__brand-tagline {
  margin: 1px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--azul);
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar__link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 14.5px;
  font-weight: 600;
  color: var(--texto-secundario);
  text-decoration: none;
}

.sidebar__link:hover {
  background: var(--fondo);
}

.sidebar__link--active {
  background: var(--azul-tenue);
  color: var(--azul);
}

.sidebar__footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar__org {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--borde);
  border-radius: 12px;
  background: var(--superficie);
  text-align: left;
}

.sidebar__org-icon {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  object-fit: cover;
  flex-shrink: 0;
}

.sidebar__org-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.sidebar__org-text strong {
  font-size: 13px;
  color: var(--azul-oscuro);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar__org-text small {
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.sidebar__org-chevron {
  color: var(--texto-secundario);
  flex-shrink: 0;
}

.sidebar__status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}

.sidebar__status-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar__status-text small {
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.sidebar__status-text strong {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--verde);
}

.sidebar__status-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--verde);
}
</style>
