<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";

/**
 * Vista pública de SENTI.
 *
 * Muestra dos cosas y ninguna más: la actividad ciudadana vigente y el estado
 * de las fuentes oficiales. Todo lo demás —identidad, coordenadas, fotos— no
 * sale de aquí (§13.2, §22).
 *
 * El listado público no devuelve coordenadas individuales porque un punto
 * exacto cruzado con la hora señala una vivienda. El mapa usa exclusivamente
 * la agregación segura de `GET /reportes/mapa-publico`; nunca inventa puntos a
 * partir del índice de la lista.
 */

interface Report {
  id: string;
  tipo: string;
  estado: string;
  confianza: string;
  confirmado: boolean;
  descripcion: string | null;
  distrito: string | null;
  reportado_at: string;
  vence_at: string | null;
}

interface Fuente {
  slug: string;
  institucion: string;
  estado: string;
  verificada: boolean;
  citable: boolean;
  ultima_consulta: string | null;
  declaracion: string | null;
}

interface MapaFeature {
  geometry: { coordinates: [number, number] };
  properties: { reportes: number; peso: number };
}

const reports = ref<Report[]>([]);
const fuentes = ref<Fuente[]>([]);
const note = ref("");
const consultedAt = ref("");
const loading = ref(false);
const error = ref("");

const district = ref("");
const onlyConfirmed = ref(false);
const limit = ref(50);
const mapaRef = ref<HTMLDivElement | null>(null);
const mapaFeatures = ref<MapaFeature[]>([]);
const mapaError = ref("");
const reporteSeleccionado = ref<Report | null>(null);

const TIPOS: Record<string, string> = {
  via_bloqueada: "Vía bloqueada",
  inundacion: "Inundación",
  huaico: "Huaico",
  deslizamiento: "Deslizamiento",
  sismo: "Sismo",
  incendio: "Incendio",
  otro: "Otro",
};

// §21.2, la escalera de confianza. Se muestra siempre y con palabras, no solo
// con color: el §31.2 pide que el color nunca sea la única información, y aquí
// la diferencia entre «confirmado» y «sin confirmar» decide si alguien cambia
// de ruta.
const CONFIANZA: Record<string, { texto: string; clase: string }> = {
  confirmado: { texto: "Confirmado por autoridad", clase: "c-confirmado" },
  validado: { texto: "Validado con evidencia", clase: "c-validado" },
  probable: { texto: "Probable", clase: "c-probable" },
  pendiente: { texto: "Sin confirmar", clase: "c-pendiente" },
};

const ESTADO_FUENTE: Record<string, { texto: string; clase: string }> = {
  ok: { texto: "Operativa", clase: "f-ok" },
  degradado: { texto: "Degradada", clase: "f-degradado" },
  caido: { texto: "Sin respuesta", clase: "f-caido" },
  obsoleto: { texto: "Desactualizada", clase: "f-obsoleto" },
};

async function cargar() {
  loading.value = true;
  error.value = "";
  try {
    const [rReportes, rFuentes] = await Promise.all([
      fetch(`/api/reportes/publicos?limite=${limit.value}`),
      fetch("/api/fuentes/estado"),
    ]);
    if (!rReportes.ok) throw new Error("No se pudieron cargar los reportes.");
    const datos = (await rReportes.json()) as {
      reportes: Report[];
      nota: string;
      consultado_at: string;
    };
    reports.value = datos.reportes;
    note.value = datos.nota;
    consultedAt.value = datos.consultado_at;
    // El estado de las fuentes es complementario: si falla, la página sirve
    // lo principal en vez de quedarse en blanco.
    if (rFuentes.ok) {
      fuentes.value = ((await rFuentes.json()) as { fuentes: Fuente[] }).fuentes;
    }
  } catch (motivo) {
    error.value = motivo instanceof Error ? motivo.message : "Error al consultar.";
  } finally {
    loading.value = false;
  }
}

async function cargarMapa() {
  mapaError.value = "";
  try {
    const respuesta = await fetch("/api/reportes/mapa-publico?horas=168&celda_m=1000");
    if (!respuesta.ok) throw new Error("No se pudo cargar la actividad del mapa.");
    const datos = (await respuesta.json()) as { features: MapaFeature[] };
    mapaFeatures.value = datos.features;
    await nextTick();
    await cargarGoogleMaps();
  } catch (motivo) {
    mapaError.value = motivo instanceof Error ? motivo.message : "Mapa no disponible.";
  }
}

async function cargarGoogleMaps() {
  const clave = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
  if (!clave) throw new Error("Falta configurar la clave de Google Maps.");
  const ventana = window as Window & { google?: any };
  if (!ventana.google?.maps) {
    await new Promise<void>((resolve, reject) => {
      const existente = document.getElementById("google-maps-script");
      if (existente) {
        existente.addEventListener("load", () => resolve(), { once: true });
        existente.addEventListener("error", () => reject(new Error("Google Maps no respondió.")), { once: true });
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
  const google = ventana.google;
  if (!mapaRef.value || !google?.maps) return;
  const mapa = new google.maps.Map(mapaRef.value, {
    center: { lat: -11.935, lng: -76.696 },
    zoom: 11,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
  });
  for (const feature of mapaFeatures.value) {
    const [lng, lat] = feature.geometry.coordinates;
    new google.maps.Circle({
      map: mapa,
      center: { lat, lng },
      radius: Math.min(850, 250 + feature.properties.reportes * 100),
      fillColor: "#16806b",
      fillOpacity: 0.25,
      strokeColor: "#16806b",
      strokeOpacity: 0.7,
      strokeWeight: 1,
    });
  }
}

onMounted(async () => {
  await cargar();
  await cargarMapa();
});

const visibles = computed(() =>
  reports.value.filter((r) => {
    const coincideDistrito =
      !district.value.trim() ||
      (r.distrito ?? "").toLowerCase().includes(district.value.trim().toLowerCase());
    return coincideDistrito && (!onlyConfirmed.value || r.confirmado);
  }),
);

const porConfianza = computed(() =>
  (["confirmado", "validado", "probable", "pendiente"] as const).map((nivel) => ({
    nivel,
    etiqueta: CONFIANZA[nivel].texto,
    clase: CONFIANZA[nivel].clase,
    total: visibles.value.filter((r) => r.confianza === nivel).length,
  })),
);

/** Dónde se concentra la actividad. Es la única agregación que el dato permite. */
const porDistrito = computed(() => {
  const cuenta = new Map<string, number>();
  for (const r of visibles.value) {
    const clave = r.distrito || "Sin distrito indicado";
    cuenta.set(clave, (cuenta.get(clave) ?? 0) + 1);
  }
  const filas = [...cuenta.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  const mayor = filas[0]?.[1] ?? 1;
  return filas.map(([nombre, total]) => ({
    nombre,
    total,
    porcentaje: Math.round((total / mayor) * 100),
  }));
});

const fuentesOperativas = computed(
  () => fuentes.value.filter((f) => f.estado === "ok").length,
);

const tipo = (v: string) => TIPOS[v] ?? v.replace(/_/g, " ");
const confianza = (v: string) => CONFIANZA[v] ?? { texto: v, clase: "c-pendiente" };

/**
 * «Sin respuesta» y «sin consultar» no son lo mismo.
 *
 * Una fuente sin `healthcheck_url` arranca en `caido` y se queda ahí para
 * siempre, porque el sondeo del §11.3 solo recorre las que tienen URL. Decir
 * que INDECI no responde cuando SENTI nunca le ha preguntado es afirmar algo
 * que no se ha comprobado, que es justo lo que este sistema no hace. Ninguna
 * de las dos es citable, así que la diferencia es de honestidad, no de
 * seguridad — y por eso mismo no cuesta nada respetarla.
 */
function estadoFuente(f: Fuente) {
  if (!f.ultima_consulta) {
    return { texto: "Sin consultar", clase: "f-obsoleto" };
  }
  return ESTADO_FUENTE[f.estado] ?? { texto: f.estado, clase: "f-caido" };
}

function fecha(iso: string | null) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("es-PE", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <img src="/senti-icono.png" alt="" />
        <div>
          <strong>SENTI</strong>
          <small>Consulta pública</small>
        </div>
      </div>
      <nav>
        <a href="#actividad">Actividad</a>
        <a href="#fuentes">Fuentes</a>
        <a href="#reportes">Reportes</a>
      </nav>
    </header>

    <main>
      <section class="hero">
        <div class="hero-texto">
          <p class="kicker">Observatorio ciudadano</p>
          <h1>Lo que está pasando ahora en tu zona</h1>
          <p class="lead">
            Reportes vigentes de la comunidad y estado de las fuentes oficiales
            que SENTI consulta. Sin identidad, sin ubicación exacta y sin fotos:
            aquí solo se publica lo que puede verse sin señalar a nadie.
          </p>
        </div>
        <div class="pulso" :class="{ cargando: loading }">
          <span class="luz"></span>
          <strong>{{ loading ? "Sincronizando" : "Datos vigentes" }}</strong>
          <small>{{ consultedAt ? fecha(consultedAt) : "—" }}</small>
        </div>
      </section>

      <p v-if="error" class="aviso-error">{{ error }}</p>

      <section id="actividad" class="metricas">
        <article class="metrica destacada">
          <span class="cifra">{{ visibles.length }}</span>
          <span class="etiqueta">reportes vigentes</span>
        </article>
        <article v-for="c in porConfianza" :key="c.nivel" class="metrica">
          <span class="cifra" :class="c.clase">{{ c.total }}</span>
          <span class="etiqueta">{{ c.etiqueta }}</span>
        </article>
      </section>

      <section id="mapa" class="tarjeta mapa-tarjeta">
        <header class="cabecera">
          <div>
            <h2>Actividad en el mapa</h2>
            <p class="subtitulo">Concentración aproximada de reportes en los últimos 7 días</p>
          </div>
          <small>celdas de 1 km</small>
        </header>
        <div ref="mapaRef" class="mapa" role="img" aria-label="Mapa de actividad agregada de reportes"></div>
        <p v-if="mapaError" class="aviso-error">{{ mapaError }}</p>
        <p class="nota">Las áreas están agregadas para proteger la ubicación de las personas. No representan domicilios ni puntos exactos.</p>
      </section>

      <div class="columnas">
        <section class="tarjeta">
          <header class="cabecera">
            <h2>Dónde se concentra</h2>
            <small>por distrito</small>
          </header>
          <p v-if="!porDistrito.length" class="vacio">Sin actividad registrada.</p>
          <ul v-else class="barras">
            <li v-for="d in porDistrito" :key="d.nombre">
              <span class="nombre">{{ d.nombre }}</span>
              <span class="barra"><i :style="{ width: d.porcentaje + '%' }"></i></span>
              <span class="valor">{{ d.total }}</span>
            </li>
          </ul>
          <p class="nota">
            No se publican coordenadas: un punto exacto cruzado con la hora
            señalaría una vivienda concreta.
          </p>
        </section>

        <section class="tarjeta">
          <header class="cabecera">
            <h2>Filtros</h2>
          </header>
          <label>
            Distrito
            <input v-model="district" type="search" placeholder="Todos" />
          </label>
          <label class="fila-check">
            <input v-model="onlyConfirmed" type="checkbox" />
            Solo confirmados por autoridad
          </label>
          <label>
            Cuántos consultar
            <select v-model="limit" @change="cargar">
              <option :value="25">25</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </label>
          <button class="recargar" :disabled="loading" @click="cargar">
            {{ loading ? "Consultando…" : "Actualizar" }}
          </button>
        </section>
      </div>

      <section id="fuentes" class="tarjeta">
        <header class="cabecera">
          <h2>Fuentes oficiales</h2>
          <small>{{ fuentesOperativas }} de {{ fuentes.length }} operativas</small>
        </header>
        <p class="nota">
          Cuando una fuente no responde, o todavía no se ha consultado, SENTI lo
          dice en vez de callarlo: que no haya dato no significa que no haya
          peligro. Solo se cita como vigente lo que se pudo comprobar.
        </p>
        <ul class="fuentes">
          <li v-for="f in fuentes" :key="f.slug">
            <span class="punto" :class="estadoFuente(f).clase"></span>
            <span class="institucion">{{ f.institucion }}</span>
            <span class="estado">{{ estadoFuente(f).texto }}</span>
            <span class="consulta">{{ fecha(f.ultima_consulta) }}</span>
          </li>
        </ul>
      </section>

      <section id="reportes" class="tarjeta">
        <header class="cabecera">
          <h2>Reportes recientes</h2>
          <small>{{ visibles.length }} resultados</small>
        </header>
        <p v-if="loading && !reports.length" class="vacio">Cargando…</p>
        <p v-else-if="!visibles.length" class="vacio">
          No hay reportes para esta consulta.
        </p>
        <ul v-else class="reportes">
          <li v-for="r in visibles" :key="r.id">
            <button class="reporte-acceso" type="button" @click="reporteSeleccionado = r">
              <span class="pastilla" :class="confianza(r.confianza).clase">
                {{ confianza(r.confianza).texto }}
              </span>
              <div class="cuerpo">
                <h3>{{ tipo(r.tipo) }}</h3>
                <p>{{ r.descripcion || "Sin descripción adicional." }}</p>
              </div>
              <div class="lado">
                <strong><span class="icono-ubicacion" aria-hidden="true">⌖</span>{{ r.distrito || "Distrito no indicado" }}</strong>
                <time>{{ fecha(r.reportado_at) }}</time>
                <span class="ver-info">Ver información</span>
              </div>
            </button>
          </li>
        </ul>
        <p v-if="note" class="nota">{{ note }}</p>
      </section>

      <div v-if="reporteSeleccionado" class="modal-fondo" role="presentation" @click.self="reporteSeleccionado = null">
        <section class="modal-reporte" role="dialog" aria-modal="true" aria-labelledby="titulo-reporte">
          <button class="modal-cerrar" type="button" aria-label="Cerrar información" @click="reporteSeleccionado = null">×</button>
          <span class="pastilla" :class="confianza(reporteSeleccionado.confianza).clase">
            {{ confianza(reporteSeleccionado.confianza).texto }}
          </span>
          <h2 id="titulo-reporte">{{ tipo(reporteSeleccionado.tipo) }}</h2>
          <p>{{ reporteSeleccionado.descripcion || "Sin descripción adicional." }}</p>
          <p class="detalle-ubicacion"><span class="icono-ubicacion" aria-hidden="true">⌖</span>{{ reporteSeleccionado.distrito || "Distrito no indicado" }}</p>
          <time>{{ fecha(reporteSeleccionado.reportado_at) }}</time>
          <p class="nota">La vista pública muestra una zona agregada para proteger la ubicación exacta de quien reportó.</p>
        </section>
      </div>
    </main>

    <footer>
      <p>
        <strong>SENTI no reemplaza al canal oficial del Estado.</strong>
        El canal de alerta masiva del Perú es SISMATE (MTC e INDECI).
      </p>
      <p class="telefonos">
        Emergencias: 115 Defensa Civil · 116 Bomberos · 106 SAMU
      </p>
      <p class="creditos">Datos cartográficos © OpenStreetMap contributors.</p>
    </footer>
  </div>
</template>
