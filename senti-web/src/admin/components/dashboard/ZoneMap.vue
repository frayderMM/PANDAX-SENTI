<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import type { ZonaMapaConfig } from "../../types";

const props = defineProps<{
  zona: ZonaMapaConfig;
}>();

const contenedorRef = ref<HTMLDivElement | null>(null);
const usandoGoogleMaps = ref(false);
const errorMapa = ref("");

const COLOR_MARCADOR: Record<string, string> = {
  roja: "#e53935",
  amarilla: "#f6a800",
  verde: "#16a45b",
};

/**
 * Mismo patrón que ya usa la vista pública (`App.vue`, `cargarGoogleMaps`):
 * el script de Google Maps se inyecta una sola vez y se reutiliza. Si no hay
 * `VITE_GOOGLE_MAPS_API_KEY` configurada (el caso hoy), se queda en el
 * placeholder de abajo — no hay forma de "simular" un mapa real sin la
 * clave, y fingirlo sería peor que decir que falta.
 */
async function cargarGoogleMaps(): Promise<any> {
  const clave = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;
  if (!clave) return null;

  const ventana = window as Window & { google?: any };
  if (!ventana.google?.maps) {
    await new Promise<void>((resolve, reject) => {
      const existente = document.getElementById("google-maps-script");
      if (existente) {
        existente.addEventListener("load", () => resolve(), { once: true });
        existente.addEventListener("error", () => reject(new Error("Google Maps no respondió.")), {
          once: true,
        });
        return;
      }
      const script = document.createElement("script");
      script.id = "google-maps-script";
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(clave)}`;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Google Maps no respondió."));
      document.head.appendChild(script);
    });
  }
  return ventana.google ?? null;
}

async function dibujarMapa() {
  errorMapa.value = "";
  try {
    const google = await cargarGoogleMaps();
    if (!google?.maps || !contenedorRef.value) {
      usandoGoogleMaps.value = false;
      return;
    }
    usandoGoogleMaps.value = true;
    const mapa = new google.maps.Map(contenedorRef.value, {
      center: props.zona.centro,
      zoom: props.zona.zoom,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
    });
    new google.maps.Polygon({
      map: mapa,
      paths: props.zona.poligono,
      strokeColor: "#0b55f5",
      strokeWeight: 1.5,
      fillColor: "#0b55f5",
      fillOpacity: 0.18,
    });
    for (const marcador of props.zona.marcadores) {
      new google.maps.Marker({
        map: mapa,
        position: marcador,
        title: marcador.tipo,
      });
    }
  } catch (motivo) {
    usandoGoogleMaps.value = false;
    errorMapa.value = motivo instanceof Error ? motivo.message : "Mapa no disponible.";
  }
}

onMounted(async () => {
  await nextTick();
  await dibujarMapa();
});

watch(
  () => props.zona,
  async () => {
    if (usandoGoogleMaps.value) await dibujarMapa();
  },
);
</script>

<template>
  <section class="zone-map">
    <div class="zone-map__header">
      <h2 class="zone-map__title">Mapa de la zona</h2>
    </div>

    <div ref="contenedorRef" class="zone-map__canvas" :class="{ 'zone-map__canvas--placeholder': !usandoGoogleMaps }">
      <svg
        v-if="!usandoGoogleMaps"
        class="zone-map__placeholder"
        viewBox="0 0 320 220"
        role="img"
        aria-label="Mapa esquemático de la zona seleccionada"
      >
        <rect width="320" height="220" fill="#eef2fb" />
        <g stroke="#d7deef" stroke-width="1">
          <path d="M0 44H320M0 88H320M0 132H320M0 176H320" />
          <path d="M64 0V220M128 0V220M192 0V220M256 0V220" />
        </g>
        <path
          d="M90 60 L235 44 L268 118 L172 168 L70 140 Z"
          fill="#0b55f5"
          fill-opacity="0.2"
          stroke="#0b55f5"
          stroke-width="1.6"
        />
        <circle cx="160" cy="110" r="4" fill="#0b55f5" />
        <circle
          v-for="(marcador, i) in zona.marcadores"
          :key="i"
          :cx="96 + ((i * 47) % 170)"
          :cy="72 + ((i * 31) % 96)"
          r="6"
          :fill="COLOR_MARCADOR[marcador.tipo]"
        />
      </svg>

      <div class="zone-map__controls" aria-hidden="true">
        <span class="zone-map__control">+</span>
        <span class="zone-map__control">−</span>
      </div>
    </div>

    <p v-if="!usandoGoogleMaps" class="zone-map__hint">
      Vista esquemática. Falta configurar <code>VITE_GOOGLE_MAPS_API_KEY</code> para el mapa real.
    </p>
    <p v-if="errorMapa" class="zone-map__hint zone-map__hint--error" role="alert">{{ errorMapa }}</p>
  </section>
</template>

<style scoped>
.zone-map {
  padding: 22px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
  display: flex;
  flex-direction: column;
  height: 100%;
}

.zone-map__title {
  font-size: 15.5px;
  font-weight: 800;
  color: var(--azul-oscuro);
  margin-bottom: 14px;
}

.zone-map__canvas {
  position: relative;
  flex: 1;
  min-height: 260px;
  border-radius: 12px;
  overflow: hidden;
}

.zone-map__canvas--placeholder {
  background: #eef2fb;
}

.zone-map__placeholder {
  width: 100%;
  height: 100%;
  display: block;
}

.zone-map__controls {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.zone-map__control {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--superficie);
  color: var(--texto-secundario);
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(7, 27, 74, 0.12);
}

.zone-map__hint {
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.zone-map__hint code {
  font-size: 11px;
}

.zone-map__hint--error {
  color: var(--rojo);
}
</style>
