<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

interface Tablero {
  consultado_at: string;
  alertas_activas: number;
  reportes_pendientes: number;
  reportes_confirmados: number;
  vias_bloqueadas: number;
  centros_apoyo: number;
  estado_fuentes: Record<string, number>;
}

interface HeatFeature {
  geometry: { coordinates: [number, number] };
  properties: { reportes: number; peso: number };
}

const tablero = ref<Tablero | null>(null);
const zonas = ref<HeatFeature[]>([]);
const cargando = ref(true);
const error = ref("");
const rol = ref("");

function tokenGuardado() {
  return localStorage.getItem("senti_access_token") || sessionStorage.getItem("senti_access_token");
}

function borrarSesion() {
  for (const almacenamiento of [localStorage, sessionStorage]) {
    almacenamiento.removeItem("senti_access_token");
    almacenamiento.removeItem("senti_role");
  }
}

async function cargar() {
  const token = tokenGuardado();
  rol.value = localStorage.getItem("senti_role") || sessionStorage.getItem("senti_role") || "";
  if (!token) {
    window.location.replace("/login.html");
    return;
  }
  cargando.value = true;
  error.value = "";
  const headers = { Authorization: `Bearer ${token}` };
  try {
    const [tableroRespuesta, mapaRespuesta] = await Promise.all([
      fetch("/api/municipal/tablero", { headers }),
      fetch("/api/municipal/mapa-calor?horas=24&celda_m=300", { headers }),
    ]);
    if (tableroRespuesta.status === 401 || tableroRespuesta.status === 403) {
      borrarSesion();
      error.value = tableroRespuesta.status === 403
        ? "Tu cuenta no tiene permisos para el panel municipal."
        : "La sesión expiró. Vuelve a iniciar sesión.";
      return;
    }
    if (!tableroRespuesta.ok) throw new Error("No se pudo cargar el tablero municipal.");
    tablero.value = (await tableroRespuesta.json()) as Tablero;
    if (mapaRespuesta.ok) {
      const mapa = (await mapaRespuesta.json()) as { features: HeatFeature[] };
      zonas.value = mapa.features.slice(0, 8);
    }
  } catch (motivo) {
    error.value = motivo instanceof Error ? motivo.message : "No se pudo conectar con SENTI.";
  } finally {
    cargando.value = false;
  }
}

function salir() {
  borrarSesion();
  window.location.replace("/login.html");
}

function fecha(iso: string | undefined) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

const fuentesOk = computed(() => tablero.value?.estado_fuentes.ok ?? 0);
const fuentesTotal = computed(() => Object.values(tablero.value?.estado_fuentes ?? {}).reduce((total, n) => total + n, 0));
onMounted(cargar);
</script>

<template>
  <div class="panel">
    <header class="barra">
      <a class="marca" href="/dashboard.html" aria-label="Inicio del panel municipal"><img src="/senti-icono.png" alt="" /><span>SENTI <small>Panel municipal</small></span></a>
      <div class="acciones"><span class="rol">{{ rol.replaceAll("_", " ") }}</span><button class="salir" type="button" @click="salir">Cerrar sesión</button></div>
    </header>
    <main class="contenido">
      <section class="encabezado"><div><p class="kicker">Monitoreo operativo</p><h1>Situación municipal</h1><p class="subtitulo">Indicadores verificados para priorizar la respuesta.</p></div><button class="actualizar" type="button" :disabled="cargando" @click="cargar">{{ cargando ? "Consultando…" : "Actualizar" }}</button></section>
      <p v-if="error" class="aviso" role="alert">{{ error }}</p>
      <section v-if="cargando && !tablero" class="cargando" aria-live="polite">Cargando tablero…</section>
      <template v-if="tablero">
        <section class="metricas" aria-label="Indicadores municipales">
          <article><span>Alertas activas</span><strong>{{ tablero.alertas_activas }}</strong></article>
          <article><span>Reportes pendientes</span><strong>{{ tablero.reportes_pendientes }}</strong></article>
          <article><span>Reportes confirmados</span><strong>{{ tablero.reportes_confirmados }}</strong></article>
          <article><span>Vías bloqueadas</span><strong>{{ tablero.vias_bloqueadas }}</strong></article>
          <article><span>Centros de apoyo</span><strong>{{ tablero.centros_apoyo }}</strong></article>
        </section>
        <section class="grid">
          <article class="tarjeta fuentes"><div class="tarjeta-cabeza"><div><h2>Fuentes oficiales</h2><p>Estado de la última consulta</p></div><strong>{{ fuentesOk }}/{{ fuentesTotal }}</strong></div><div class="fuente-linea"><span class="punto punto-ok"></span><span>Operativas</span><b>{{ tablero.estado_fuentes.ok }}</b></div><div class="fuente-linea"><span class="punto punto-alerta"></span><span>Degradadas</span><b>{{ tablero.estado_fuentes.degradado }}</b></div><div class="fuente-linea"><span class="punto punto-error"></span><span>Sin respuesta</span><b>{{ tablero.estado_fuentes.caido }}</b></div></article>
          <article class="tarjeta zonas"><div class="tarjeta-cabeza"><div><h2>Zonas prioritarias</h2><p>Agregación de las últimas 24 horas</p></div><span class="etiqueta">Sin puntos individuales</span></div><p v-if="!zonas.length" class="vacio">No hay reportes suficientes para mostrar zonas prioritarias.</p><ul v-else><li v-for="(zona, indice) in zonas" :key="`${zona.geometry.coordinates.join("-")}-${indice}`"><span class="zona-numero">{{ indice + 1 }}</span><span>Celda aproximada {{ zona.geometry.coordinates[1].toFixed(3) }}, {{ zona.geometry.coordinates[0].toFixed(3) }}</span><b>{{ zona.properties.reportes }} reportes</b></li></ul></article>
        </section>
        <p class="pie">Datos consultados {{ fecha(tablero.consultado_at) }}. Las posiciones están agregadas para proteger a las personas.</p>
      </template>
    </main>
  </div>
</template>

<style scoped>
.panel { min-height: 100vh; }.barra { display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 6vw;background:#071b4a;color:#fff; }.marca { display:flex;align-items:center;gap:12px;color:inherit;text-decoration:none;font-weight:800;font-size:20px; }.marca img { width:38px;height:38px;border-radius:11px; }.marca small { display:block;color:#b8c9ef;font-size:11px;font-weight:500; }.acciones { display:flex;align-items:center;gap:18px; }.rol { color:#b8c9ef;font-size:13px;text-transform:capitalize; }.salir,.actualizar { border:1px solid #cbd8ed;border-radius:9px;background:transparent;color:inherit;padding:9px 14px;font-weight:700; }.salir:hover { background:rgba(255,255,255,.1); }.contenido { max-width:1280px;margin:0 auto;padding:48px 6vw; }.encabezado { display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:28px; }.kicker { margin:0 0 8px;color:#0866f5;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase; }h1,h2,p { margin:0; }h1 { font-size:clamp(28px,4vw,42px);letter-spacing:-.03em; }h2 { font-size:18px; }.subtitulo,.tarjeta-cabeza p { margin-top:8px;color:#65738e;font-size:14px; }.actualizar { border-color:#0866f5;color:#0866f5;background:#fff; }.actualizar:disabled { opacity:.6;cursor:wait; }.aviso { margin-bottom:24px;padding:14px 16px;border:1px solid #f1b4b0;border-radius:10px;background:#fff0ef;color:#a12722; }.cargando { padding:48px;border-radius:16px;background:#fff;color:#65738e;text-align:center; }.metricas { display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:22px; }.metricas article,.tarjeta { border:1px solid #e2e7f3;border-radius:16px;background:#fff;box-shadow:0 8px 24px rgba(7,27,74,.05); }.metricas article { display:flex;min-height:116px;flex-direction:column;justify-content:space-between;padding:18px; }.metricas span { color:#65738e;font-size:13px; }.metricas strong { color:#0866f5;font-size:34px; }.grid { display:grid;grid-template-columns:minmax(260px,.8fr) minmax(0,1.6fr);gap:22px; }.tarjeta { padding:24px; }.tarjeta-cabeza { display:flex;align-items:start;justify-content:space-between;gap:16px;margin-bottom:24px; }.tarjeta-cabeza>strong { color:#0866f5;font-size:23px; }.fuente-linea { display:flex;align-items:center;gap:10px;padding:13px 0;border-top:1px solid #edf0f6;color:#45536e;font-size:14px; }.fuente-linea b { margin-left:auto;color:#071b4a; }.punto { width:9px;height:9px;border-radius:50%; }.punto-ok { background:#1b9c6a; }.punto-alerta { background:#e4a62c; }.punto-error { background:#d0342c; }.etiqueta { padding:5px 8px;border-radius:6px;background:#eef4ff;color:#0866f5;font-size:11px;font-weight:700; }.zonas ul { display:grid;gap:10px;margin:0;padding:0;list-style:none; }.zonas li { display:grid;grid-template-columns:25px 1fr auto;align-items:center;gap:10px;padding:12px;border-radius:9px;background:#f6f8fc;color:#45536e;font-size:13px; }.zonas li b { color:#071b4a;white-space:nowrap; }.zona-numero { display:grid;width:24px;height:24px;place-items:center;border-radius:50%;background:#dfeaff;color:#0866f5;font-weight:800; }.vacio { color:#65738e;font-size:14px; }.pie { margin-top:18px;color:#65738e;font-size:12px; }
@media (max-width:800px) { .metricas { grid-template-columns:repeat(2,1fr); }.grid { grid-template-columns:1fr; }.encabezado { align-items:start;flex-direction:column; } }
@media (max-width:520px) { .barra { align-items:start;flex-direction:column;padding:16px; }.acciones { width:100%;justify-content:space-between; }.contenido { padding:30px 16px; }.zonas li { grid-template-columns:25px 1fr; }.zonas li b { grid-column:2; } }
</style>
