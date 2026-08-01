import type { ZonaMapaConfig } from "../types";

// Mismas coordenadas que usa el backend para el distrito piloto
// (`senti-backend/app/db/seeds.py`, CHOSICA_LAT/CHOSICA_LON): no hay
// subdivisión real en zonas, el piloto es un solo distrito.
const CHOSICA = { lat: -11.9404, lng: -76.7006 };

/**
 * Config del mapa de la zona. Sigue siendo un mock — el polígono y los
 * marcadores son ilustrativos, no vienen de `AlertZone` — porque conectar
 * el mapa a datos reales requiere primero exponer coordenadas por alerta
 * en `GET /municipal/tablero`, que hoy solo da el nombre del distrito.
 */
export const MAPA_MUNICIPIO: ZonaMapaConfig = {
  centro: CHOSICA,
  zoom: 13,
  poligono: [
    { lat: CHOSICA.lat + 0.01, lng: CHOSICA.lng - 0.012 },
    { lat: CHOSICA.lat + 0.009, lng: CHOSICA.lng + 0.011 },
    { lat: CHOSICA.lat - 0.006, lng: CHOSICA.lng + 0.014 },
    { lat: CHOSICA.lat - 0.011, lng: CHOSICA.lng + 0.001 },
    { lat: CHOSICA.lat - 0.004, lng: CHOSICA.lng - 0.013 },
  ],
  marcadores: [
    { lat: CHOSICA.lat + 0.004, lng: CHOSICA.lng + 0.004, tipo: "roja" },
    { lat: CHOSICA.lat + 0.002, lng: CHOSICA.lng - 0.006, tipo: "amarilla" },
  ],
};
