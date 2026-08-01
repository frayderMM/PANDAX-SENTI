<script setup lang="ts">
import Icon from "../../Icon.vue";
import type { PronosticoHora } from "../../types";

defineProps<{
  puntos: PronosticoHora[];
}>();

const ICONO_CONDICION: Record<PronosticoHora["condicion"], string> = {
  soleado: "cloud",
  nublado: "cloud",
  lluvia: "cloud-rain",
  tormenta: "cloud-lightning",
};
</script>

<template>
  <div class="forecast-strip">
    <p class="forecast-strip__title">Pronóstico por hora</p>
    <div class="forecast-strip__row">
      <div v-for="punto in puntos" :key="punto.hora" class="forecast-strip__item">
        <span class="forecast-strip__hora">{{ punto.hora }}</span>
        <Icon :name="ICONO_CONDICION[punto.condicion]" :size="18" class="forecast-strip__icono" />
        <span class="forecast-strip__temp">{{ Math.round(punto.temperatura) }}°</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.forecast-strip {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--borde);
}

.forecast-strip__title {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--azul-oscuro);
  margin-bottom: 10px;
}

.forecast-strip__row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
}

.forecast-strip__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 52px;
  padding: 10px 6px;
  border-radius: 12px;
  background: var(--fondo);
}

.forecast-strip__hora {
  font-size: 11px;
  font-weight: 600;
  color: var(--texto-secundario);
}

.forecast-strip__icono {
  color: var(--azul);
}

.forecast-strip__temp {
  font-size: 13px;
  font-weight: 800;
  color: var(--azul-oscuro);
}
</style>
