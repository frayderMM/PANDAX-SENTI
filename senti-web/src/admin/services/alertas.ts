import type { AlertaForm, Gravedad } from "../types";

// Espejo de AlertaExtraida en senti-backend/app/llm/schemas.py.
export interface PropuestaAlerta {
  tipo_evento: string;
  titulo: string;
  nivel_detectado: string | null;
  entidad_emisora: string | null;
  zonas_mencionadas: string[];
  vigencia_inicio_texto: string | null;
  vigencia_fin_texto: string | null;
  numero_documento: string | null;
  recomendaciones: string[];
  resumen_ciudadano: string;
  terminos_tecnicos: Record<string, string>;
  datos_faltantes: string[];
}

export interface RespuestaInterpretar {
  propuesta: PropuestaAlerta;
  fragmentos_indexados: number;
  publicada: boolean;
  nota: string;
}

export interface ResultadoPublicacion {
  id: string;
  titulo: string;
  nivel_oficial: string;
  distrito: string;
  vigente: boolean;
  destinatarios_estimados: number;
  notificacion_whatsapp: "en curso" | "sin destinatarios" | "deshabilitada";
}

function tokenGuardado(): string | null {
  return localStorage.getItem("senti_access_token") || sessionStorage.getItem("senti_access_token");
}

function cabeceraAuth(): HeadersInit {
  const token = tokenGuardado();
  if (!token) {
    window.location.replace("/login.html");
    throw new Error("Sesión no iniciada.");
  }
  return { Authorization: `Bearer ${token}` };
}

async function manejarRespuesta<T>(respuesta: Response): Promise<T> {
  if (respuesta.status === 401 || respuesta.status === 403) {
    for (const almacenamiento of [localStorage, sessionStorage]) {
      almacenamiento.removeItem("senti_access_token");
      almacenamiento.removeItem("senti_role");
    }
    window.location.replace("/login.html");
    throw new Error("La sesión expiró o no tiene permiso para gestionar alertas.");
  }
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}) as { detail?: string });
    throw new Error(
      typeof cuerpo.detail === "string"
        ? cuerpo.detail
        : `El servidor respondió con HTTP ${respuesta.status}`,
    );
  }
  return respuesta.json() as Promise<T>;
}

export async function interpretarPdf(archivo: File): Promise<RespuestaInterpretar> {
  const formulario = new FormData();
  formulario.append("archivo", archivo);
  formulario.append("indexar_en_rag", "true");

  const respuesta = await fetch("/api/admin/alertas/interpretar-pdf", {
    method: "POST",
    headers: cabeceraAuth(),
    body: formulario,
  });
  return manejarRespuesta<RespuestaInterpretar>(respuesta);
}

export async function publicarAlerta(
  form: AlertaForm,
  opciones: { notificarWhatsapp: boolean },
): Promise<ResultadoPublicacion> {
  const respuesta = await fetch("/api/municipal/alertas", {
    method: "POST",
    headers: { ...cabeceraAuth(), "Content-Type": "application/json" },
    body: JSON.stringify({
      tipo_evento: form.tipoEvento,
      titulo: form.titulo,
      nivel_oficial: TEXTO_NIVEL[form.gravedad],
      descripcion: form.descripcion || null,
      recomendaciones: form.recomendacion
        ? form.recomendacion.split("\n").map((l) => l.trim()).filter(Boolean)
        : null,
      distrito: form.zona,
      notificar_whatsapp: opciones.notificarWhatsapp,
    }),
  });
  return manejarRespuesta<ResultadoPublicacion>(respuesta);
}

// Mismo criterio que `rules/municipal_dashboard.color_alerta` en el backend:
// Naranja/Roja se tratan como críticas, Amarilla como moderada, el resto verde.
const TEXTO_NIVEL: Record<Gravedad, string> = {
  rojo: "Roja",
  amarillo: "Amarilla",
  verde: "Verde",
};

export function gravedadDesdeNivel(nivelDetectado: string | null): Gravedad {
  const valor = (nivelDetectado || "").trim().toLowerCase();
  if (!valor || valor.includes("roja") || valor.includes("naranja")) return "rojo";
  if (valor.includes("amarilla")) return "amarillo";
  return "verde";
}
