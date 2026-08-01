/**
 * Lo único que sigue siendo mock tras conectar Open-Meteo: humedad de suelo
 * y caudal de ríos no están en el endpoint base (harían falta
 * `soil_moisture_*` y un servicio hidrológico aparte), así que se marcan
 * como estimados en vez de simular una precisión que el sistema no tiene.
 */
export const ESTIMADO_HUMEDAD_Y_CAUDAL = {
  humedadSuelo: 78,
  caudalRios: 1.32,
  caudalRiosDetalle: "Moderado",
};
