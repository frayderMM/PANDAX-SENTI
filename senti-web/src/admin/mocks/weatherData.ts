import type { ZonaId } from "../types";
import type { OpenMeteoCurrent, OpenMeteoHourlyPoint } from "../services/openMeteo";

interface ZonaWeatherMock {
  current: OpenMeteoCurrent;
  hourly: OpenMeteoHourlyPoint[];
  lluviaAcumulada24hEstimada: number;
  humedadSueloEstimada: number;
  caudalRiosEstimado: number;
  caudalRiosDetalleEstimado: string;
}

const HORAS = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"];

function pronosticoPorHora(
  temperaturas: number[],
  probabilidades: number[],
  codigos: number[],
): OpenMeteoHourlyPoint[] {
  return HORAS.map((time, i) => ({
    time,
    temperature_2m: temperaturas[i],
    precipitation_probability: probabilidades[i],
    weather_code: codigos[i],
  }));
}

export const OPEN_METEO_MOCK_POR_ZONA: Record<ZonaId, ZonaWeatherMock> = {
  centro: {
    current: {
      temperature_2m: 24.8,
      apparent_temperature: 26.2,
      precipitation: 8.6,
      precipitation_probability: 70,
      rain: 8.6,
      wind_speed_10m: 18,
      wind_gusts_10m: 32,
      visibility: 8.3,
      weather_code: 61,
    },
    hourly: pronosticoPorHora(
      [24, 25, 26, 26, 27, 26, 25, 24],
      [75, 80, 85, 70, 60, 65, 70, 75],
      [61, 61, 95, 3, 3, 61, 61, 61],
    ),
    lluviaAcumulada24hEstimada: 52.4,
    humedadSueloEstimada: 78,
    caudalRiosEstimado: 1.32,
    caudalRiosDetalleEstimado: "Moderado",
  },
  norte: {
    current: {
      temperature_2m: 26.1,
      apparent_temperature: 27.4,
      precipitation: 1.2,
      precipitation_probability: 30,
      rain: 1.2,
      wind_speed_10m: 14,
      wind_gusts_10m: 22,
      visibility: 9.6,
      weather_code: 2,
    },
    hourly: pronosticoPorHora(
      [26, 27, 28, 28, 28, 27, 26, 25],
      [25, 30, 35, 30, 25, 20, 20, 15],
      [2, 2, 3, 3, 2, 1, 1, 0],
    ),
    lluviaAcumulada24hEstimada: 6.8,
    humedadSueloEstimada: 54,
    caudalRiosEstimado: 0.71,
    caudalRiosDetalleEstimado: "Bajo",
  },
  sur: {
    current: {
      temperature_2m: 23.4,
      apparent_temperature: 24.6,
      precipitation: 12.4,
      precipitation_probability: 82,
      rain: 12.4,
      wind_speed_10m: 21,
      wind_gusts_10m: 38,
      visibility: 6.1,
      weather_code: 65,
    },
    hourly: pronosticoPorHora(
      [23, 23, 24, 24, 23, 23, 22, 22],
      [85, 88, 90, 85, 80, 78, 75, 70],
      [65, 65, 95, 63, 61, 61, 61, 51],
    ),
    lluviaAcumulada24hEstimada: 68.9,
    humedadSueloEstimada: 91,
    caudalRiosEstimado: 2.05,
    caudalRiosDetalleEstimado: "Alto",
  },
  este: {
    current: {
      temperature_2m: 25.2,
      apparent_temperature: 26.5,
      precipitation: 3.1,
      precipitation_probability: 45,
      rain: 3.1,
      wind_speed_10m: 16,
      wind_gusts_10m: 27,
      visibility: 8.9,
      weather_code: 51,
    },
    hourly: pronosticoPorHora(
      [25, 26, 27, 27, 26, 26, 25, 24],
      [45, 50, 55, 50, 45, 40, 40, 35],
      [51, 51, 61, 3, 2, 2, 3, 3],
    ),
    lluviaAcumulada24hEstimada: 18.3,
    humedadSueloEstimada: 63,
    caudalRiosEstimado: 0.94,
    caudalRiosDetalleEstimado: "Moderado",
  },
  oeste: {
    current: {
      temperature_2m: 27.3,
      apparent_temperature: 28.9,
      precipitation: 0,
      precipitation_probability: 10,
      rain: 0,
      wind_speed_10m: 11,
      wind_gusts_10m: 18,
      visibility: 10,
      weather_code: 0,
    },
    hourly: pronosticoPorHora(
      [27, 28, 29, 29, 28, 27, 26, 25],
      [10, 10, 15, 15, 10, 10, 5, 5],
      [0, 0, 1, 1, 0, 0, 0, 0],
    ),
    lluviaAcumulada24hEstimada: 0.4,
    humedadSueloEstimada: 38,
    caudalRiosEstimado: 0.48,
    caudalRiosDetalleEstimado: "Bajo",
  },
};
