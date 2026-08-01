<script setup lang="ts">
import { computed } from "vue";
import type { PronosticoHora } from "../../types";

const props = defineProps<{
  puntos: PronosticoHora[];
  resumen: string;
}>();

const ANCHO = 560;
const ALTO = 180;
const PAD_X = 24;
const PAD_Y = 16;

function escalaX(i: number) {
  const pasos = props.puntos.length - 1 || 1;
  return PAD_X + (i * (ANCHO - PAD_X * 2)) / pasos;
}

function escalaY(valor: number, minimo: number, maximo: number) {
  const rango = maximo - minimo || 1;
  return ALTO - PAD_Y - ((valor - minimo) / rango) * (ALTO - PAD_Y * 2);
}

const temperaturaMin = computed(() => Math.min(...props.puntos.map((p) => p.temperatura)) - 1);
const temperaturaMax = computed(() => Math.max(...props.puntos.map((p) => p.temperatura)) + 1);

const lineaTemperatura = computed(() =>
  props.puntos
    .map((p, i) => `${escalaX(i)},${escalaY(p.temperatura, temperaturaMin.value, temperaturaMax.value)}`)
    .join(" "),
);

const lineaProbabilidad = computed(() =>
  props.puntos.map((p, i) => `${escalaX(i)},${escalaY(p.probabilidadLluvia, 0, 100)}`).join(" "),
);
</script>

<template>
  <section class="chart-card">
    <div class="chart-card__header">
      <h2 class="chart-card__title">Pronóstico próximas horas</h2>
      <div class="chart-card__legend">
        <span><i class="chart-card__dot chart-card__dot--temp" aria-hidden="true"></i>Temperatura (°C)</span>
        <span><i class="chart-card__dot chart-card__dot--prob" aria-hidden="true"></i>Prob. de lluvia (%)</span>
      </div>
    </div>

    <svg
      class="chart-card__svg"
      :viewBox="`0 0 ${ANCHO} ${ALTO + 24}`"
      role="img"
      aria-label="Gráfico de temperatura y probabilidad de lluvia por hora"
    >
      <g stroke="#edf1f9" stroke-width="1">
        <line v-for="n in 4" :key="n" :x1="PAD_X" :x2="ANCHO - PAD_X" :y1="(ALTO / 4) * n" :y2="(ALTO / 4) * n" />
      </g>
      <polyline :points="lineaProbabilidad" fill="none" stroke="#7cc4f2" stroke-width="2" />
      <polyline :points="lineaTemperatura" fill="none" stroke="#0b55f5" stroke-width="2.4" />
      <g v-for="(p, i) in puntos" :key="p.hora">
        <circle :cx="escalaX(i)" :cy="escalaY(p.temperatura, temperaturaMin, temperaturaMax)" r="3" fill="#0b55f5" />
        <text :x="escalaX(i)" :y="ALTO + 16" text-anchor="middle" class="chart-card__eje-x">{{ p.hora }}</text>
      </g>
    </svg>

    <p class="chart-card__resumen">{{ resumen }}</p>
  </section>
</template>

<style scoped>
.chart-card {
  padding: 20px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chart-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.chart-card__title {
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.chart-card__legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--texto-secundario);
}

.chart-card__legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.chart-card__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.chart-card__dot--temp {
  background: #0b55f5;
}

.chart-card__dot--prob {
  background: #7cc4f2;
}

.chart-card__svg {
  width: 100%;
  height: auto;
  flex: 1;
}

.chart-card__eje-x {
  font-size: 9px;
  fill: #66749a;
}

.chart-card__resumen {
  margin-top: 8px;
  font-size: 12px;
  color: var(--texto-secundario);
}
</style>
