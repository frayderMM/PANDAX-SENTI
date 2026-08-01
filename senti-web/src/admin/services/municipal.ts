import type { AlertaResumen, ColorAlerta, EstadoIncidencia, Incidencia, ResumenZona } from "../types";

export interface TableroMunicipal {
  resumen: ResumenZona;
  alertas: AlertaResumen[];
  incidencias: Incidencia[];
}

// Forma cruda de `GET /municipal/tablero` (senti-backend/app/api/routers/municipal.py).
interface TableroRespuesta {
  ciudadanos_registrados: number;
  ciudadanos_nuevos_semana: number;
  reportes_totales: number;
  reportes_hoy: number;
  alertas_activas: number;
  alertas_criticas: number;
  alertas_moderadas: number;
  nivel_riesgo: { etiqueta: ResumenZona["riesgo"]["etiqueta"]; detalle: string };
  ultimas_alertas: { id: string; color: ColorAlerta; titulo: string; zona: string; hora: string }[];
  incidencias_recientes: {
    id: string;
    tipo: string;
    titulo: string;
    ubicacion: string;
    hora: string;
    estado: EstadoIncidencia;
  }[];
}

// El backend no manda icono (es presentación pura); se deriva del `tipo`
// real de `HazardType` (senti-backend/app/domain.py).
const ICONO_POR_TIPO: Record<string, string> = {
  inundacion: "droplet",
  huaico: "mountain",
  deslizamiento: "mountain",
  lluvia: "cloud-rain",
  sismo: "alert-octagon",
  tsunami: "waves",
  incendio: "alert-triangle",
  via_bloqueada: "alert-triangle",
  puente_afectado: "alert-triangle",
  acumulacion_agua: "droplet",
};

function formatearHora(iso: string): string {
  return new Intl.DateTimeFormat("es-PE", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function tokenGuardado(): string | null {
  return localStorage.getItem("senti_access_token") || sessionStorage.getItem("senti_access_token");
}

export function borrarSesion(): void {
  for (const almacenamiento of [localStorage, sessionStorage]) {
    almacenamiento.removeItem("senti_access_token");
    almacenamiento.removeItem("senti_role");
  }
}

/**
 * Mismo patrón que ya usa `InfoGeneralPage.vue`: token en `localStorage` o
 * `sessionStorage`, `Authorization: Bearer`, y si expira o falta permiso se
 * borra la sesión y se vuelve a `/login.html` en vez de mostrar un tablero
 * vacío como si no hubiera pasado nada.
 */
export async function getTableroMunicipal(): Promise<TableroMunicipal> {
  const token = tokenGuardado();
  if (!token) {
    window.location.replace("/login.html");
    throw new Error("Sesión no iniciada.");
  }

  const respuesta = await fetch("/api/municipal/tablero", {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (respuesta.status === 401 || respuesta.status === 403) {
    borrarSesion();
    window.location.replace("/login.html");
    throw new Error("La sesión expiró o no tiene permisos para el panel municipal.");
  }
  if (!respuesta.ok) {
    throw new Error(`El panel municipal respondió con HTTP ${respuesta.status}`);
  }

  const datos = (await respuesta.json()) as TableroRespuesta;

  return {
    resumen: {
      ciudadanosRegistrados: datos.ciudadanos_registrados,
      ciudadanosNuevosSemana: datos.ciudadanos_nuevos_semana,
      incidenciasReportadas: datos.reportes_totales,
      incidenciasHoy: datos.reportes_hoy,
      alertasActivas: datos.alertas_activas,
      alertasCriticas: datos.alertas_criticas,
      alertasModeradas: datos.alertas_moderadas,
      riesgo: datos.nivel_riesgo,
    },
    alertas: datos.ultimas_alertas.map((a) => ({
      id: a.id,
      color: a.color,
      titulo: a.titulo,
      zona: a.zona,
      hora: formatearHora(a.hora),
    })),
    incidencias: datos.incidencias_recientes.map((r) => ({
      id: r.id,
      icono: ICONO_POR_TIPO[r.tipo] ?? "alert-triangle",
      titulo: r.titulo,
      ubicacion: r.ubicacion,
      hora: formatearHora(r.hora),
      estado: r.estado,
    })),
  };
}
