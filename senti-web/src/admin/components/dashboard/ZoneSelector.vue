<script setup lang="ts">
import Icon from "../../Icon.vue";
import type { ZonaId } from "../../types";

defineProps<{
  zonas: { id: ZonaId; nombre: string }[];
}>();

const zona = defineModel<ZonaId>({ required: true });
</script>

<template>
  <label class="zone-selector">
    <Icon name="map-pin" :size="16" class="zone-selector__icon" />
    <span class="zone-selector__label">Zona encargada:</span>
    <select v-model="zona" class="zone-selector__select" aria-label="Zona encargada">
      <option v-for="z in zonas" :key="z.id" :value="z.id">{{ z.nombre }}</option>
    </select>
    <Icon name="chevron-down" :size="15" class="zone-selector__chevron" />
  </label>
</template>

<style scoped>
.zone-selector {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  margin-bottom: 20px;
  border: 1px solid var(--borde);
  border-radius: 999px;
  background: var(--superficie);
  color: var(--azul-oscuro);
  width: fit-content;
}

.zone-selector:focus-within {
  border-color: var(--azul);
  box-shadow: 0 0 0 3px var(--azul-tenue);
}

.zone-selector__icon {
  color: var(--azul);
}

.zone-selector__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--texto-secundario);
}

.zone-selector__select {
  appearance: none;
  -webkit-appearance: none;
  border: none;
  background: transparent;
  padding-right: 18px;
  font-size: 13.5px;
  font-weight: 700;
  color: var(--azul-oscuro);
}

.zone-selector__chevron {
  position: absolute;
  right: 12px;
  color: var(--texto-secundario);
  pointer-events: none;
}
</style>
