<script setup lang="ts">
import AdminHeader from "../AdminHeader.vue";
</script>

<template>
  <div>
    <AdminHeader
      title="Dashboard"
      subtitle="Panel general del operador municipal."
    />
    <div class="dashboard-placeholder">
      <p>El panel general todavía no está implementado.</p>
      <p class="dashboard-placeholder__hint">Usa "Alertas" en el menú lateral.</p>
    </div>
  </div>
</template>

<style scoped>
.dashboard-placeholder {
  padding: 48px 24px;
  text-align: center;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  color: var(--texto-secundario);
}

.dashboard-placeholder__hint {
  margin-top: 6px;
  font-size: 13px;
}
</style>
