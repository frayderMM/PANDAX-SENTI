<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import AdminHeader from "../AdminHeader.vue";
import Icon from "../Icon.vue";
import SummaryCard from "../components/dashboard/SummaryCard.vue";
import WeatherMetricsCard from "../components/dashboard/WeatherMetricsCard.vue";
import ZoneMap from "../components/dashboard/ZoneMap.vue";
import LatestAlertsCard from "../components/dashboard/LatestAlertsCard.vue";
import ForecastChartCard from "../components/dashboard/ForecastChartCard.vue";
import RecentIncidentsCard from "../components/dashboard/RecentIncidentsCard.vue";
import { MAPA_MUNICIPIO } from "../mocks/dashboardData";
import { getCurrentWeather, getHourlyForecast } from "../services/openMeteo";
import { getTableroMunicipal } from "../services/municipal";
import type { AlertaResumen, ClimaActual, Incidencia, PronosticoHora, ResumenZona } from "../types";

const NOMBRE_MUNICIPIO = "Lurigancho-Chosica";

const RESUMEN_VACIO: ResumenZona = {
  ciudadanosRegistrados: 0,
  ciudadanosNuevosSemana: 0,
  incidenciasReportadas: 0,
  incidenciasHoy: 0,
  alertasActivas: 0,
  alertasCriticas: 0,
  alertasModeradas: 0,
  riesgo: { etiqueta: "Bajo", detalle: "Sin datos todavía" },
};

const resumen = ref<ResumenZona>(RESUMEN_VACIO);
const alertas = ref<AlertaResumen[]>([]);
const incidencias = ref<Incidencia[]>([]);
const cargandoTablero = ref(true);
const errorTablero = ref("");

async function cargarTablero() {
  cargandoTablero.value = true;
  errorTablero.value = "";
  try {
    const tablero = await getTableroMunicipal();
    resumen.value = tablero.resumen;
    alertas.value = tablero.alertas;
    incidencias.value = tablero.incidencias;
  } catch (motivo) {
    errorTablero.value =
      motivo instanceof Error ? motivo.message : "No se pudo cargar el panel municipal.";
  } finally {
    cargandoTablero.value = false;
  }
}

const clima = ref<ClimaActual | null>(null);
const pronostico = ref<PronosticoHora[]>([]);
const cargandoClima = ref(true);
const errorClima = ref("");
const actualizadoEn = ref(new Date());
const ahora = ref(new Date());
let temporizador: ReturnType<typeof setInterval> | undefined;

async function cargarClima() {
  cargandoClima.value = true;
  errorClima.value = "";
  try {
    const [actual, horas] = await Promise.all([getCurrentWeather(), getHourlyForecast()]);
    clima.value = actual;
    pronostico.value = horas;
    actualizadoEn.value = new Date();
  } catch (motivo) {
    clima.value = null;
    pronostico.value = [];
    errorClima.value =
      motivo instanceof Error
        ? `No se pudieron obtener los datos meteorológicos: ${motivo.message}`
        : "No se pudieron obtener los datos meteorológicos.";
  } finally {
    cargandoClima.value = false;
  }
}

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
  cargarTablero();
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
      subtitle="Monitorea condiciones, pronóstico y actividad del municipio."
    />

    <p v-if="errorTablero" class="dashboard__aviso" role="alert">{{ errorTablero }}</p>

    <div class="dashboard__summary">
      <SummaryCard
        icon="users"
        title="Ciudadanos registrados"
        :value="resumen.ciudadanosRegistrados.toLocaleString('es-PE')"
        :detail="`+${resumen.ciudadanosNuevosSemana} esta semana`"
        tone="azul"
      />
      <SummaryCard
        icon="file-text"
        title="Incidencias reportadas"
        :value="String(resumen.incidenciasReportadas)"
        :detail="`+${resumen.incidenciasHoy} hoy`"
        tone="violeta"
      />
      <SummaryCard
        icon="bell"
        title="Alertas activas"
        :value="String(resumen.alertasActivas)"
        :detail="`${resumen.alertasCriticas} críticas · ${resumen.alertasModeradas} moderadas`"
        tone="rojo"
      />
      <SummaryCard
        icon="alert-triangle"
        title="Nivel de riesgo actual"
        :value="resumen.riesgo.etiqueta"
        :detail="resumen.riesgo.detalle"
        tone="amarillo"
        value-badge
      />
    </div>

    <div class="dashboard__main">
      <WeatherMetricsCard
        :zona-nombre="NOMBRE_MUNICIPIO"
        :clima="clima"
        :pronostico="pronostico"
        :cargando="cargandoClima"
        :error="errorClima"
      />
      <ZoneMap :zona="MAPA_MUNICIPIO" />
    </div>

    <div class="dashboard__bottom">
      <LatestAlertsCard :alertas="alertas" />
      <ForecastChartCard v-if="pronostico.length" :puntos="pronostico" :resumen="resumenPronostico" />
      <section v-else class="dashboard__chart-vacio">
        <h2 class="dashboard__chart-vacio-title">Pronóstico próximas horas</h2>
        <p>{{ cargandoClima ? "Cargando pronóstico…" : (errorClima || "Pronóstico no disponible.") }}</p>
      </section>
      <RecentIncidentsCard :incidencias="incidencias" />
    </div>

    <footer class="dashboard__footer">
      <Icon name="refresh-cw" :size="14" />
      <span>{{ textoActualizacion }}</span>
    </footer>
  </div>
</template>

<style scoped>
.dashboard__aviso {
  margin: -8px 0 16px;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--rojo-tenue);
  color: var(--rojo);
  font-size: 13px;
}

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

.dashboard__chart-vacio {
  padding: 20px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
  color: var(--texto-secundario);
  font-size: 13px;
}

.dashboard__chart-vacio-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--azul-oscuro);
  margin-bottom: 8px;
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
