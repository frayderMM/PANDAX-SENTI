export type Gravedad = "verde" | "amarillo" | "rojo";

export interface AlertaForm {
  titulo: string;
  zona: string;
  fechaHora: string;
  tipoEvento: string;
  descripcion: string;
  recomendacion: string;
  gravedad: Gravedad;
}

export interface DocumentoAdjunto {
  nombre: string;
  tamanoTexto: string;
  fechaTexto: string;
}

// ---------------------------------------------------------------- dashboard

export type ZonaId = "centro" | "norte" | "sur" | "este" | "oeste";

export interface NivelRiesgo {
  etiqueta: "Bajo" | "Medio" | "Alto";
  detalle: string;
}

export interface ResumenZona {
  ciudadanosRegistrados: number;
  ciudadanosNuevosSemana: number;
  incidenciasReportadas: number;
  incidenciasHoy: number;
  alertasActivas: number;
  alertasCriticas: number;
  alertasModeradas: number;
  riesgo: NivelRiesgo;
}

/**
 * Forma "amigable" que consume la UI. `services/openMeteo.ts` es quien
 * traduce la respuesta cruda de Open-Meteo (u hoy, el mock) a esto.
 */
export interface ClimaActual {
  temperatura: number;
  sensacionTermica: number;
  lluviaUltimaHora: number;
  probabilidadLluvia: number;
  lluviaAcumulada24h: number;
  vientoVelocidad: number;
  vientoRafagas: number;
  /** Estimado: Open-Meteo base no expone humedad de suelo por zona. */
  humedadSuelo: number;
  /** Estimado: requeriría un servicio hidrológico aparte. */
  caudalRios: number;
  caudalRiosDetalle: string;
  visibilidad: number;
  codigoMeteorologico: number;
  codigoMeteorologicoTexto: string;
}

export type CondicionHora = "soleado" | "nublado" | "lluvia" | "tormenta";

export interface PronosticoHora {
  hora: string;
  temperatura: number;
  probabilidadLluvia: number;
  condicion: CondicionHora;
}

export type ColorAlerta = "roja" | "amarilla" | "verde";

export interface AlertaResumen {
  id: string;
  color: ColorAlerta;
  titulo: string;
  zona: string;
  hora: string;
}

export type EstadoIncidencia = "En proceso" | "Atendida";

export interface Incidencia {
  id: string;
  icono: string;
  titulo: string;
  ubicacion: string;
  hora: string;
  estado: EstadoIncidencia;
}

export interface CoordenadaMapa {
  lat: number;
  lng: number;
}

export interface MarcadorMapa extends CoordenadaMapa {
  tipo: ColorAlerta;
}

export interface ZonaMapaConfig {
  centro: CoordenadaMapa;
  zoom: number;
  poligono: CoordenadaMapa[];
  marcadores: MarcadorMapa[];
}

export interface DatosZona {
  id: ZonaId;
  nombre: string;
  resumen: ResumenZona;
  alertas: AlertaResumen[];
  incidencias: Incidencia[];
  mapa: ZonaMapaConfig;
}
