import type { ClimaActual, PronosticoHora, ZonaId } from "../types";
import { OPEN_METEO_MOCK_POR_ZONA } from "../mocks/weatherData";

/**
 * Subconjunto de la respuesta de Open-Meteo que este dashboard consume
 * (no es el contrato completo del API). Cuando exista la integración real,
 * `fetch("https://api.open-meteo.com/v1/forecast?...")` debe devolver algo
 * que encaje en esta forma para los bloques `current` y cada punto de
 * `hourly`.
 */
export interface OpenMeteoCurrent {
  temperature_2m: number;
  apparent_temperature: number;
  precipitation: number;
  precipitation_probability: number;
  rain: number;
  wind_speed_10m: number;
  wind_gusts_10m: number;
  visibility: number;
  weather_code: number;
}

export interface OpenMeteoHourlyPoint {
  time: string;
  temperature_2m: number;
  precipitation_probability: number;
  weather_code: number;
}

const TEXTO_CODIGO_METEOROLOGICO: Record<number, string> = {
  0: "Despejado",
  1: "Mayormente despejado",
  2: "Parcialmente nublado",
  3: "Nublado",
  45: "Niebla",
  51: "Llovizna",
  61: "Lluvia",
  63: "Lluvia moderada",
  65: "Lluvia intensa",
  80: "Chubascos",
  95: "Tormenta",
};

function textoCodigoMeteorologico(codigo: number): string {
  return TEXTO_CODIGO_METEOROLOGICO[codigo] ?? "Sin dato";
}

function condicionDesdeCodigo(codigo: number): PronosticoHora["condicion"] {
  if (codigo >= 95) return "tormenta";
  if (codigo >= 51) return "lluvia";
  if (codigo >= 2) return "nublado";
  return "soleado";
}

/**
 * `humedad_suelo` y `caudal_rios` no vienen del endpoint base de Open-Meteo
 * (harían falta `soil_moisture_*` y un servicio hidrológico aparte, fuera de
 * alcance hoy). Se devuelven como estimados explícitos en vez de simular una
 * precisión que el sistema no tiene — el mismo criterio que ya sigue el
 * backend con las fuentes oficiales (ver README, "no presentar el silencio
 * de una fuente como ausencia de peligro").
 */
export async function getCurrentWeatherByZone(zona: ZonaId): Promise<ClimaActual> {
  const mock = OPEN_METEO_MOCK_POR_ZONA[zona];
  const actual = mock.current;
  return {
    temperatura: actual.temperature_2m,
    sensacionTermica: actual.apparent_temperature,
    lluviaUltimaHora: actual.precipitation,
    probabilidadLluvia: actual.precipitation_probability,
    lluviaAcumulada24h: mock.lluviaAcumulada24hEstimada,
    vientoVelocidad: actual.wind_speed_10m,
    vientoRafagas: actual.wind_gusts_10m,
    humedadSuelo: mock.humedadSueloEstimada,
    caudalRios: mock.caudalRiosEstimado,
    caudalRiosDetalle: mock.caudalRiosDetalleEstimado,
    visibilidad: actual.visibility,
    codigoMeteorologico: actual.weather_code,
    codigoMeteorologicoTexto: textoCodigoMeteorologico(actual.weather_code),
  };
}

export async function getHourlyForecastByZone(zona: ZonaId): Promise<PronosticoHora[]> {
  const mock = OPEN_METEO_MOCK_POR_ZONA[zona];
  return mock.hourly.map((punto) => ({
    hora: punto.time,
    temperatura: punto.temperature_2m,
    probabilidadLluvia: punto.precipitation_probability,
    condicion: condicionDesdeCodigo(punto.weather_code),
  }));
}
