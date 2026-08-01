<script setup lang="ts">
import WeatherMetricItem from "./WeatherMetricItem.vue";
import HourlyForecastStrip from "./HourlyForecastStrip.vue";
import type { ClimaActual, PronosticoHora } from "../../types";

defineProps<{
  zonaNombre: string;
  clima: ClimaActual | null;
  pronostico: PronosticoHora[];
  cargando: boolean;
  error?: string;
}>();
</script>

<template>
  <section class="weather-card">
    <h2 class="weather-card__title">Condiciones actuales – Zona {{ zonaNombre }}</h2>

    <p v-if="cargando" class="weather-card__loading">Actualizando condiciones…</p>
    <p v-else-if="error" class="weather-card__error" role="alert">{{ error }}</p>

    <template v-else-if="clima">
      <div class="weather-card__grid">
        <WeatherMetricItem
          icon="thermometer"
          title="Temperatura"
          :value="`${clima.temperatura.toFixed(1)} °C`"
          :detail="`Sensación ${clima.sensacionTermica.toFixed(1)} °C`"
        />
        <WeatherMetricItem
          icon="droplet"
          title="Lluvia (última hora)"
          :value="`${clima.lluviaUltimaHora.toFixed(1)} mm`"
        />
        <WeatherMetricItem
          icon="percent"
          title="Prob. de lluvia"
          :value="`${clima.probabilidadLluvia} %`"
        />
        <WeatherMetricItem
          icon="cloud-rain"
          title="Lluvia acumulada (24h)"
          :value="`${clima.lluviaAcumulada24h.toFixed(1)} mm`"
        />
        <WeatherMetricItem
          icon="wind"
          title="Viento"
          :value="`${clima.vientoVelocidad} km/h`"
          :detail="`Ráfagas ${clima.vientoRafagas} km/h`"
        />
        <WeatherMetricItem
          icon="sprout"
          title="Humedad del suelo"
          :value="`${clima.humedadSuelo} %`"
          detail="Estimado"
        />
        <WeatherMetricItem
          icon="waves"
          title="Caudal ríos (est.)"
          :value="`${clima.caudalRios.toFixed(2)} m`"
          :detail="clima.caudalRiosDetalle"
        />
        <WeatherMetricItem
          icon="eye"
          title="Visibilidad"
          :value="`${clima.visibilidad.toFixed(1)} km`"
        />
        <WeatherMetricItem
          icon="cloud"
          title="Código meteorológico"
          :value="String(clima.codigoMeteorologico)"
          :detail="clima.codigoMeteorologicoTexto"
        />
      </div>

      <HourlyForecastStrip :puntos="pronostico" />
    </template>
  </section>
</template>

<style scoped>
.weather-card {
  padding: 22px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
}

.weather-card__title {
  font-size: 15.5px;
  font-weight: 800;
  color: var(--azul-oscuro);
  margin-bottom: 16px;
}

.weather-card__loading {
  padding: 20px 0;
  color: var(--texto-secundario);
  font-size: 13px;
}

.weather-card__error {
  padding: 20px 0;
  color: var(--rojo);
  font-size: 13px;
}

.weather-card__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

@media (max-width: 720px) {
  .weather-card__grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
