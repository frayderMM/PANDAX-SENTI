<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import AdminHeader from "../AdminHeader.vue";
import Icon from "../Icon.vue";
import ZoneSelector from "../components/dashboard/ZoneSelector.vue";
import SummaryCard from "../components/dashboard/SummaryCard.vue";
import WeatherMetricsCard from "../components/dashboard/WeatherMetricsCard.vue";
import ZoneMap from "../components/dashboard/ZoneMap.vue";
import LatestAlertsCard from "../components/dashboard/LatestAlertsCard.vue";
import ForecastChartCard from "../components/dashboard/ForecastChartCard.vue";
import RecentIncidentsCard from "../components/dashboard/RecentIncidentsCard.vue";
import { DASHBOARD_MOCK_POR_ZONA, ZONAS } from "../mocks/dashboardData";
import { getCurrentWeatherByZone, getHourlyForecastByZone } from "../services/openMeteo";
import type { ClimaActual, PronosticoHora, ZonaId } from "../types";

const zonaSeleccionada = ref<ZonaId>("centro");
const datosZona = computed(() => DASHBOARD_MOCK_POR_ZONA[zonaSeleccionada.value]);

const clima = ref<ClimaActual | null>(null);
const pronostico = ref<PronosticoHora[]>([]);
const cargandoClima = ref(true);
const actualizadoEn = ref(new Date());
const ahora = ref(new Date());
let temporizador: ReturnType<typeof setInterval> | undefined;

async function cargarClima() {
  cargandoClima.value = true;
  const [actual, horas] = await Promise.all([
    getCurrentWeatherByZone(zonaSeleccionada.value),
    getHourlyForecastByZone(zonaSeleccionada.value),
  ]);
  clima.value = actual;
  pronostico.value = horas;
  cargandoClima.value = false;
  actualizadoEn.value = new Date();
}

watch(zonaSeleccionada, cargarClima);

const textoActualizacion = computed(() => {
  const minutos = Math.max(
    0,
    Math.round((ahora.value.getTime() - actualizadoEn.value.getTime()) / 60000),
  );
  if (minutos < 1) return "Datos actualizados hace instantes";
  if (minutos === 1) return "Datos actualizados hace 1 minuto";
  return `Datos actualizados hace ${minutos} minutos`;
});

const resumenPronostico = computed(() => {
  const conLluvia = pronostico.value.filter((p) => p.probabilidadLluvia >= 50);
  if (!conLluvia.length) return "Sin lluvias relevantes previstas en las próximas horas.";
  const inicio = conLluvia[0].hora;
  const fin = conLluvia[conLluvia.length - 1].hora;
  return `Se esperan lluvias entre ${inicio} y ${fin} h con disminución posterior.`;
});

onMounted(() => {
  cargarClima();
  temporizador = setInterval(() => (ahora.value = new Date()), 30000);
});

onUnmounted(() => {
  if (temporizador) clearInterval(temporizador);
});
</script>

<template>
  <div>
    <AdminHeader
      title="Dashboard"
      subtitle="Monitorea condiciones, pronóstico y actividad de tu zona asignada."
    />

    <ZoneSelector v-model="zonaSeleccionada" :zonas="ZONAS" />

    <div class="dashboard__summary">
      <SummaryCard
        icon="users"
        title="Ciudadanos registrados"
        :value="datosZona.resumen.ciudadanosRegistrados.toLocaleString('es-PE')"
        :detail="`+${datosZona.resumen.ciudadanosNuevosSemana} esta semana`"
        tone="azul"
      />
      <SummaryCard
        icon="file-text"
        title="Incidencias reportadas"
        :value="String(datosZona.resumen.incidenciasReportadas)"
        :detail="`+${datosZona.resumen.incidenciasHoy} hoy`"
        tone="violeta"
      />
      <SummaryCard
        icon="bell"
        title="Alertas activas"
        :value="String(datosZona.resumen.alertasActivas)"
        :detail="`${datosZona.resumen.alertasCriticas} críticas · ${datosZona.resumen.alertasModeradas} moderadas`"
        tone="rojo"
      />
      <SummaryCard
        icon="alert-triangle"
        title="Nivel de riesgo actual"
        :value="datosZona.resumen.riesgo.etiqueta"
        :detail="datosZona.resumen.riesgo.detalle"
        tone="amarillo"
        value-badge
      />
    </div>

    <div class="dashboard__main">
      <WeatherMetricsCard
        v-if="clima"
        :zona-nombre="datosZona.nombre"
        :clima="clima"
        :pronostico="pronostico"
        :cargando="cargandoClima"
      />
      <ZoneMap :zona="datosZona.mapa" />
    </div>

    <div class="dashboard__bottom">
      <LatestAlertsCard :alertas="datosZona.alertas" />
      <ForecastChartCard :puntos="pronostico" :resumen="resumenPronostico" />
      <RecentIncidentsCard :incidencias="datosZona.incidencias" />
    </div>

    <footer class="dashboard__footer">
      <Icon name="refresh-cw" :size="14" />
      <span>{{ textoActualizacion }}</span>
    </footer>
  </div>
</template>

<style scoped>
.dashboard__summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.dashboard__main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
  align-items: stretch;
}

.dashboard__bottom {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  align-items: stretch;
}

.dashboard__footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--borde);
  color: var(--texto-secundario);
  font-size: 12px;
}

@media (max-width: 1100px) {
  .dashboard__summary {
    grid-template-columns: repeat(2, 1fr);
  }

  .dashboard__main {
    grid-template-columns: 1fr;
  }

  .dashboard__bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .dashboard__summary {
    grid-template-columns: 1fr;
  }
}
</style>
