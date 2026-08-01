import { MAPA_MUNICIPIO } from "../mocks/dashboardData";
import { ESTIMADO_HUMEDAD_Y_CAUDAL } from "../mocks/weatherData";
import type { ClimaActual, PronosticoHora } from "../types";

const BASE_URL = "https://api.open-meteo.com/v1/forecast";

// Solo se piden los campos que WeatherMetricsCard.vue realmente muestra.
const CAMPOS_ACTUALES = [
  "temperature_2m",
  "apparent_temperature",
  "precipitation",
  "weather_code",
  "wind_speed_10m",
  "wind_gusts_10m",
].join(",");

const CAMPOS_HORARIOS = [
  "temperature_2m",
  "precipitation_probability",
  "precipitation",
  "weather_code",
  "visibility",
].join(",");

interface OpenMeteoActual {
  time: string;
  temperature_2m: number;
  apparent_temperature: number;
  precipitation: number;
  weather_code: number;
  wind_speed_10m: number;
  wind_gusts_10m: number;
}

interface OpenMeteoHorario {
  time: string[];
  temperature_2m: number[];
  precipitation_probability: number[];
  precipitation: number[];
  weather_code: number[];
  visibility: number[];
}

interface OpenMeteoRespuesta {
  timezone: string;
  current: OpenMeteoActual;
  hourly: OpenMeteoHorario;
}

const TEXTO_CODIGO_METEOROLOGICO: Record<number, string> = {
  0: "Cielo despejado",
  1: "Mayormente despejado",
  2: "Parcialmente nublado",
  3: "Nublado",
  45: "Niebla",
  48: "Niebla con escarcha",
  51: "Llovizna ligera",
  53: "Llovizna moderada",
  55: "Llovizna intensa",
  61: "Lluvia ligera",
  63: "Lluvia moderada",
  65: "Lluvia intensa",
  80: "Chubascos ligeros",
  81: "Chubascos moderados",
  82: "Chubascos intensos",
  95: "Tormenta eléctrica",
  96: "Tormenta con granizo ligero",
  99: "Tormenta con granizo intenso",
};

// WMO weather codes, según la documentación de Open-Meteo.
function textoCodigoMeteorologico(codigo: number): string {
  return TEXTO_CODIGO_METEOROLOGICO[codigo] ?? `Código meteorológico ${codigo}`;
}

function condicionDesdeCodigo(codigo: number): PronosticoHora["condicion"] {
  if ([95, 96, 99].includes(codigo)) return "tormenta";
  if (codigo >= 51) return "lluvia";
  if (codigo >= 2) return "nublado";
  return "soleado";
}

// Deduplica: si `getCurrentWeather` y `getHourlyForecast` se llaman juntos
// (el caso normal, vía Promise.all), solo sale una petición HTTP.
let enVuelo: Promise<OpenMeteoRespuesta> | null = null;

async function consultarOpenMeteo(): Promise<OpenMeteoRespuesta> {
  if (enVuelo) return enVuelo;

  enVuelo = (async () => {
    // Mismo punto que el mapa (`mocks/dashboardData.ts`): el piloto es un
    // solo distrito, no hace falta una segunda tabla de coordenadas.
    const { lat, lng } = MAPA_MUNICIPIO.centro;
    const parametros = new URLSearchParams({
      latitude: lat.toFixed(4),
      longitude: lng.toFixed(4),
      current: CAMPOS_ACTUALES,
      hourly: CAMPOS_HORARIOS,
      timezone: "auto",
      forecast_days: "2",
      past_days: "1",
    });

    const respuesta = await fetch(`${BASE_URL}?${parametros}`);
    if (!respuesta.ok) {
      throw new Error(`Open-Meteo respondió con HTTP ${respuesta.status}`);
    }
    const datos = (await respuesta.json()) as OpenMeteoRespuesta;
    if (!datos.current || !datos.hourly) {
      throw new Error("La respuesta de Open-Meteo no trae condiciones actuales.");
    }
    return datos;
  })();

  try {
    return await enVuelo;
  } finally {
    enVuelo = null;
  }
}

function indiceHoraActual(horas: string[], horaActual: string): number {
  const exacto = horas.indexOf(horaActual);
  if (exacto !== -1) return exacto;
  const siguiente = horas.findIndex((h) => h >= horaActual);
  return siguiente === -1 ? horas.length - 1 : siguiente;
}

export async function getCurrentWeather(): Promise<ClimaActual> {
  const datos = await consultarOpenMeteo();
  const actual = datos.current;
  const horario = datos.hourly;
  const estimado = ESTIMADO_HUMEDAD_Y_CAUDAL;

  const indice = indiceHoraActual(horario.time, actual.time);
  const probabilidadLluvia = horario.precipitation_probability[indice] ?? 0;
  const visibilidadMetros = horario.visibility[indice];

  // `past_days=1` trae 24h previas, así que a partir de la hora actual
  // siempre hay al menos 24 lecturas horarias hacia atrás para sumar.
  const desde = Math.max(0, indice - 23);
  const lluviaAcumulada24h = horario.precipitation
    .slice(desde, indice + 1)
    .reduce((total, mm) => total + (mm || 0), 0);

  return {
    temperatura: actual.temperature_2m,
    sensacionTermica: actual.apparent_temperature,
    lluviaUltimaHora: actual.precipitation,
    probabilidadLluvia,
    lluviaAcumulada24h,
    vientoVelocidad: actual.wind_speed_10m,
    vientoRafagas: actual.wind_gusts_10m,
    humedadSuelo: estimado.humedadSuelo,
    caudalRios: estimado.caudalRios,
    caudalRiosDetalle: estimado.caudalRiosDetalle,
    visibilidad: typeof visibilidadMetros === "number" ? visibilidadMetros / 1000 : NaN,
    codigoMeteorologico: actual.weather_code,
    codigoMeteorologicoTexto: textoCodigoMeteorologico(actual.weather_code),
  };
}

export async function getHourlyForecast(): Promise<PronosticoHora[]> {
  const datos = await consultarOpenMeteo();
  const horario = datos.hourly;
  const inicio = indiceHoraActual(horario.time, datos.current.time);

  return horario.time.slice(inicio, inicio + 8).map((time, i) => {
    const indice = inicio + i;
    return {
      hora: time.slice(11, 16),
      temperatura: horario.temperature_2m[indice],
      probabilidadLluvia: horario.precipitation_probability[indice] ?? 0,
      condicion: condicionDesdeCodigo(horario.weather_code[indice]),
    };
  });
}
