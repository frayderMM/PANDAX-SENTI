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
    <a class="salto-contenido" href="#contenido">Saltar al contenido</a>
    <header class="topbar">
      <a class="brand" href="#inicio" aria-label="SENTI, volver al inicio">
        <img src="/senti-icono.png" alt="" />
        <div>
          <strong>SENTI</strong>
          <small>Información pública</small>
        </div>
      </a>
      <nav aria-label="Navegación principal">
        <a href="#como-funciona">Cómo funciona</a>
        <a href="#actividad">Mapa</a>
        <a href="#fuentes">Fuentes</a>
        <a href="#reportes">Reportes</a>
      </nav>
      <a class="boton-cabecera" href="#reportes">Ver reportes</a>
    </header>

    <main id="contenido">
      <section id="inicio" class="hero">
        <div class="hero-texto">
          <p class="kicker"><span></span> Observatorio ciudadano de emergencias</p>
          <h1>Información clara para actuar <em>a tiempo.</em></h1>
          <p class="lead">
            Consulta actividad reportada por la comunidad, revisa el estado de
            las fuentes oficiales y entiende qué información ha sido verificada
            antes de tomar una decisión.
          </p>
          <div class="hero-acciones">
            <a class="boton primario" href="#actividad">Explorar actividad</a>
            <a class="boton secundario" href="#como-funciona">Conocer SENTI</a>
          </div>
          <ul class="garantias" aria-label="Principios de la consulta pública">
            <li>Sin identidad pública</li>
            <li>Sin ubicaciones exactas</li>
            <li>Con fecha y nivel de confianza</li>
          </ul>
        </div>
        <aside class="estado-general" aria-label="Estado actual de SENTI">
          <div class="estado-superior">
            <span class="estado-icono" aria-hidden="true">◎</span>
            <div>
              <span class="eyebrow">Estado de la información</span>
              <strong>{{ loading ? "Sincronizando datos" : "Consulta actualizada" }}</strong>
            </div>
            <span class="luz" :class="{ cargando: loading }"></span>
          </div>
          <div class="estado-cifra">
            <strong>{{ visibles.length }}</strong>
            <span>reportes vigentes en la consulta pública</span>
          </div>
          <div class="estado-fila">
            <span>Fuentes operativas</span>
            <strong>{{ fuentesOperativas }}/{{ fuentes.length || "—" }}</strong>
          </div>
          <div class="estado-fila">
            <span>Última consulta</span>
            <strong>{{ consultedAt ? fecha(consultedAt) : "Pendiente" }}</strong>
          </div>
          <p>Que no aparezca un reporte no significa que no exista peligro. Ante una emergencia, usa los canales oficiales.</p>
        </aside>
      </section>

      <p v-if="error" class="aviso-error">{{ error }}</p>

      <section class="franja-emergencia" aria-label="Teléfonos de emergencia">
        <div>
          <span class="franja-icono" aria-hidden="true">!</span>
          <p><strong>¿Hay peligro inmediato?</strong> No esperes una respuesta en esta página.</p>
        </div>
        <div class="telefonos-rapidos">
          <a href="tel:116"><span>Bomberos</span><strong>116</strong></a>
          <a href="tel:106"><span>SAMU</span><strong>106</strong></a>
          <a href="tel:115"><span>Defensa Civil</span><strong>115</strong></a>
        </div>
      </section>

      <section id="como-funciona" class="bloque-presentacion">
        <header class="titulo-seccion">
          <div>
            <p class="kicker">Una red de información responsable</p>
            <h2>SENTI conecta reportes ciudadanos con fuentes verificables</h2>
          </div>
          <p>
            La inteligencia artificial ayuda a entender y redactar. Las reglas
            del sistema validan permisos, ubicación, vigencia y nivel de confianza.
          </p>
        </header>
        <div class="pasos">
          <article>
            <span class="numero-paso">01</span>
            <div class="icono-paso" aria-hidden="true">◉</div>
            <h3>Recibimos señales</h3>
            <p>Reportes ciudadanos y consultas periódicas a instituciones especializadas.</p>
          </article>
          <article>
            <span class="numero-paso">02</span>
            <div class="icono-paso" aria-hidden="true">✓</div>
            <h3>Verificamos contexto</h3>
            <p>Se revisan fuente, fecha, zona, evidencia y coincidencia con otros registros.</p>
          </article>
          <article>
            <span class="numero-paso">03</span>
            <div class="icono-paso" aria-hidden="true">↗</div>
            <h3>Publicamos con cuidado</h3>
            <p>Mostramos información agregada, sin exponer personas, domicilios ni fotografías.</p>
          </article>
        </div>
      </section>

      <section id="actividad" class="seccion-datos">
        <header class="titulo-seccion compacto">
          <div>
            <p class="kicker">Panorama actual</p>
            <h2>Actividad reportada</h2>
          </div>
          <p>Los niveles indican cuánta verificación tiene cada reporte; no representan la gravedad del evento.</p>
        </header>
        <div class="metricas">
        <article class="metrica destacada">
          <span class="cifra">{{ visibles.length }}</span>
          <span class="etiqueta">Reportes vigentes</span>
          <small>Total visible con los filtros actuales</small>
        </article>
        <article v-for="c in porConfianza" :key="c.nivel" class="metrica">
          <span class="cifra" :class="c.clase">{{ c.total }}</span>
          <span class="etiqueta">{{ c.etiqueta }}</span>
          <small v-if="c.nivel === 'confirmado'">Comunicado por una autoridad</small>
          <small v-else-if="c.nivel === 'validado'">Revisado con evidencia</small>
          <small v-else-if="c.nivel === 'probable'">Coincidencias suficientes</small>
          <small v-else>Aún requiere verificación</small>
        </article>
        </div>
      </section>

      <section id="mapa" class="tarjeta mapa-tarjeta tarjeta-elevada">
        <header class="cabecera">
          <div>
            <h2>Actividad aproximada en el mapa</h2>
            <p class="subtitulo">Concentración de reportes durante los últimos 7 días</p>
          </div>
          <span class="etiqueta-mapa">Privacidad: celdas de 1 km</span>
        </header>
        <div class="mapa-contenedor">
          <div ref="mapaRef" class="mapa" role="img" aria-label="Mapa de actividad agregada de reportes"></div>
          <div v-if="mapaError" class="mapa-alternativo">
            <span aria-hidden="true">⊙</span>
            <strong>El mapa interactivo no está disponible</strong>
            <p>La actividad por distrito y los reportes continúan disponibles.</p>
          </div>
        </div>
        <p class="nota nota-privacidad">Las áreas están agregadas para proteger la ubicación de las personas. No representan domicilios ni puntos exactos.</p>
      </section>

      <div class="columnas">
        <section class="tarjeta tarjeta-elevada">
          <header class="cabecera">
            <h2>Dónde se concentra</h2>
            <small>Actividad relativa por distrito</small>
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

        <section class="tarjeta filtros-tarjeta">
          <header class="cabecera">
            <div>
              <p class="kicker">Personaliza la vista</p>
              <h2>Filtrar reportes</h2>
            </div>
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

      <section id="fuentes" class="tarjeta tarjeta-elevada fuentes-seccion">
        <header class="cabecera">
          <div>
            <p class="kicker">Transparencia de origen</p>
            <h2>Estado de las fuentes oficiales</h2>
          </div>
          <span class="contador-fuentes">{{ fuentesOperativas }} de {{ fuentes.length }} operativas</span>
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

      <section id="reportes" class="tarjeta tarjeta-elevada reportes-seccion">
        <header class="cabecera">
          <div>
            <p class="kicker">Actividad de la comunidad</p>
            <h2>Reportes recientes</h2>
          </div>
          <span class="contador-fuentes">{{ visibles.length }} resultados</span>
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

      <section class="confianza-info">
        <div>
          <p class="kicker">Lee antes de actuar</p>
          <h2>No todos los reportes significan lo mismo</h2>
          <p>
            SENTI muestra el nivel de confianza con texto y color. Un reporte
            pendiente sirve como señal ciudadana, pero no equivale a una alerta oficial.
          </p>
        </div>
        <ol>
          <li><span class="nivel confirmado"></span><strong>Confirmado</strong><small>Publicado o ratificado por una autoridad.</small></li>
          <li><span class="nivel validado"></span><strong>Validado</strong><small>Cuenta con evidencia revisada.</small></li>
          <li><span class="nivel probable"></span><strong>Probable</strong><small>Coincide con otros reportes independientes.</small></li>
          <li><span class="nivel pendiente"></span><strong>Sin confirmar</strong><small>Todavía no tiene evidencia suficiente.</small></li>
        </ol>
      </section>

      <section class="preparacion">
        <div class="preparacion-texto">
          <p class="kicker">Prepararse también es responder</p>
          <h2>Ten información esencial incluso cuando falle la conexión</h2>
          <p>
            SENTI permite conservar un paquete básico con teléfonos de emergencia,
            plan familiar, checklist y la última alerta descargada con su fecha.
          </p>
        </div>
        <ul class="preparacion-lista">
          <li><span>01</span><div><strong>Define un punto de reunión</strong><small>Que toda tu familia pueda recordar.</small></div></li>
          <li><span>02</span><div><strong>Guarda los teléfonos oficiales</strong><small>No dependas de una sola aplicación.</small></div></li>
          <li><span>03</span><div><strong>Revisa la fecha de sincronización</strong><small>Una alerta guardada puede haber cambiado.</small></div></li>
        </ul>
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
      <div class="footer-marca">
        <div class="brand">
          <img src="/senti-icono.png" alt="" />
          <div><strong>SENTI</strong><small>Asistencia e información para emergencias</small></div>
        </div>
        <p>Información comprensible, verificable y respetuosa de la privacidad.</p>
      </div>
      <div class="footer-enlaces">
        <strong>Explorar</strong>
        <a href="#actividad">Actividad</a>
        <a href="#fuentes">Fuentes</a>
        <a href="#reportes">Reportes</a>
      </div>
      <div class="footer-aviso">
        <strong>SENTI no reemplaza al canal oficial del Estado.</strong>
        <p>El canal de alerta masiva del Perú es SISMATE (MTC e INDECI).</p>
        <p class="telefonos">115 Defensa Civil · 116 Bomberos · 106 SAMU</p>
      </div>
      <p class="creditos">Datos cartográficos © OpenStreetMap contributors.</p>
    </footer>
  </div>
</template>
