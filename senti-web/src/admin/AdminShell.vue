<script setup lang="ts">
import Sidebar from "./Sidebar.vue";
</script>

<template>
  <div class="admin-shell">
    <Sidebar />
    <main class="admin-shell__content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.admin-shell {
  --azul: #0b55f5;
  --azul-oscuro: #071b4a;
  --azul-tenue: #eaf0fe;
  --fondo: #f6f8fc;
  --superficie: #ffffff;
  --borde: #e2e8f3;
  --texto-secundario: #66749a;
  --verde: #16a45b;
  --verde-tenue: #e8f7ee;
  --amarillo: #f6a800;
  --amarillo-tenue: #fef4e2;
  --rojo: #e91824;
  --rojo-tenue: #fdeaec;

  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
  background: var(--fondo);
  color: var(--azul-oscuro);
  font-family: Inter, Manrope, system-ui, -apple-system, "Segoe UI", sans-serif;
}

.admin-shell__content {
  min-width: 0;
  padding: 28px 32px 48px;
  overflow-x: auto;
}
</style>
