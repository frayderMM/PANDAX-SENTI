import type { DatosZona, ZonaId } from "../types";

export const ZONAS: { id: ZonaId; nombre: string }[] = [
  { id: "centro", nombre: "Centro" },
  { id: "norte", nombre: "Norte" },
  { id: "sur", nombre: "Sur" },
  { id: "este", nombre: "Este" },
  { id: "oeste", nombre: "Oeste" },
];

// Centro aproximado tomado del mapa público (App.vue) para mantener un
// mismo punto de referencia; el resto son offsets de mock, no coordenadas
// reales de deslinde municipal.
const CENTRO_BASE = { lat: -11.935, lng: -76.696 };

/**
 * Todo lo que no es clima vive centralizado aquí, por zona, para que el
 * selector de la cabecera cambie el dashboard completo con un solo lookup.
 * El clima vive aparte en `services/openMeteo.ts` porque tiene su propio
 * mapeo de campos (ver ese archivo).
 */
export const DASHBOARD_MOCK_POR_ZONA: Record<ZonaId, DatosZona> = {
  centro: {
    id: "centro",
    nombre: "Centro",
    resumen: {
      ciudadanosRegistrados: 12450,
      ciudadanosNuevosSemana: 245,
      incidenciasReportadas: 87,
      incidenciasHoy: 12,
      alertasActivas: 6,
      alertasCriticas: 2,
      alertasModeradas: 4,
      riesgo: { etiqueta: "Medio", detalle: "Precaución y monitoreo continuo" },
    },
    alertas: [
      {
        id: "a1",
        color: "roja",
        titulo: "Inundación en zona Centro por lluvias intensas",
        zona: "Centro",
        hora: "Hoy, 10:28 a. m.",
      },
      {
        id: "a2",
        color: "amarilla",
        titulo: "Crecida de río en nivel preventivo",
        zona: "Ribera del río Rímac",
        hora: "Hoy, 09:45 a. m.",
      },
      {
        id: "a3",
        color: "amarilla",
        titulo: "Vientos fuertes en zonas abiertas",
        zona: "Centro",
        hora: "Hoy, 08:30 a. m.",
      },
      {
        id: "a4",
        color: "verde",
        titulo: "Condiciones estables en la zona",
        zona: "Centro",
        hora: "Ayer, 07:15 p. m.",
      },
    ],
    incidencias: [
      {
        id: "i1",
        icono: "droplet",
        titulo: "Encharcamiento en vía principal",
        ubicacion: "Av. Principal y Jr. Los Álamos",
        hora: "Hoy, 10:15 a. m.",
        estado: "En proceso",
      },
      {
        id: "i2",
        icono: "tree",
        titulo: "Árbol caído sobre banqueta",
        ubicacion: "Calle Las Magnolias",
        hora: "Hoy, 09:40 a. m.",
        estado: "Atendida",
      },
      {
        id: "i3",
        icono: "mountain",
        titulo: "Riesgo de deslave en talud",
        ubicacion: "Asoc. Vecinal Gaviotas Norte",
        hora: "Hoy, 08:55 a. m.",
        estado: "En proceso",
      },
      {
        id: "i4",
        icono: "droplet",
        titulo: "Inundación en vivienda",
        ubicacion: "Col. Centro",
        hora: "Hoy, 08:20 a. m.",
        estado: "Atendida",
      },
    ],
    mapa: {
      centro: CENTRO_BASE,
      zoom: 14,
      poligono: [
        { lat: CENTRO_BASE.lat + 0.01, lng: CENTRO_BASE.lng - 0.012 },
        { lat: CENTRO_BASE.lat + 0.009, lng: CENTRO_BASE.lng + 0.011 },
        { lat: CENTRO_BASE.lat - 0.006, lng: CENTRO_BASE.lng + 0.014 },
        { lat: CENTRO_BASE.lat - 0.011, lng: CENTRO_BASE.lng + 0.001 },
        { lat: CENTRO_BASE.lat - 0.004, lng: CENTRO_BASE.lng - 0.013 },
      ],
      marcadores: [
        { lat: CENTRO_BASE.lat + 0.004, lng: CENTRO_BASE.lng + 0.004, tipo: "roja" },
        { lat: CENTRO_BASE.lat + 0.002, lng: CENTRO_BASE.lng - 0.006, tipo: "amarilla" },
        { lat: CENTRO_BASE.lat - 0.005, lng: CENTRO_BASE.lng - 0.002, tipo: "amarilla" },
        { lat: CENTRO_BASE.lat - 0.003, lng: CENTRO_BASE.lng + 0.007, tipo: "roja" },
      ],
    },
  },
  norte: {
    id: "norte",
    nombre: "Norte",
    resumen: {
      ciudadanosRegistrados: 8930,
      ciudadanosNuevosSemana: 118,
      incidenciasReportadas: 34,
      incidenciasHoy: 4,
      alertasActivas: 1,
      alertasCriticas: 0,
      alertasModeradas: 1,
      riesgo: { etiqueta: "Bajo", detalle: "Condiciones estables, sin acción requerida" },
    },
    alertas: [
      {
        id: "a1",
        color: "verde",
        titulo: "Condiciones estables en la zona",
        zona: "Norte",
        hora: "Hoy, 07:10 a. m.",
      },
      {
        id: "a2",
        color: "amarilla",
        titulo: "Calor elevado en horas de la tarde",
        zona: "Norte",
        hora: "Ayer, 03:20 p. m.",
      },
    ],
    incidencias: [
      {
        id: "i1",
        icono: "tree",
        titulo: "Rama caída en vía secundaria",
        ubicacion: "Jr. Las Palmeras",
        hora: "Hoy, 09:05 a. m.",
        estado: "Atendida",
      },
      {
        id: "i2",
        icono: "droplet",
        titulo: "Fuga de agua menor",
        ubicacion: "Av. Los Pinos",
        hora: "Ayer, 06:40 p. m.",
        estado: "Atendida",
      },
    ],
    mapa: {
      centro: { lat: CENTRO_BASE.lat + 0.028, lng: CENTRO_BASE.lng + 0.006 },
      zoom: 13,
      poligono: [
        { lat: CENTRO_BASE.lat + 0.036, lng: CENTRO_BASE.lng - 0.008 },
        { lat: CENTRO_BASE.lat + 0.034, lng: CENTRO_BASE.lng + 0.018 },
        { lat: CENTRO_BASE.lat + 0.02, lng: CENTRO_BASE.lng + 0.02 },
        { lat: CENTRO_BASE.lat + 0.019, lng: CENTRO_BASE.lng - 0.006 },
      ],
      marcadores: [{ lat: CENTRO_BASE.lat + 0.027, lng: CENTRO_BASE.lng + 0.006, tipo: "amarilla" }],
    },
  },
  sur: {
    id: "sur",
    nombre: "Sur",
    resumen: {
      ciudadanosRegistrados: 15680,
      ciudadanosNuevosSemana: 302,
      incidenciasReportadas: 121,
      incidenciasHoy: 19,
      alertasActivas: 9,
      alertasCriticas: 4,
      alertasModeradas: 5,
      riesgo: { etiqueta: "Alto", detalle: "Riesgo de inundación, evaluar evacuación preventiva" },
    },
    alertas: [
      {
        id: "a1",
        color: "roja",
        titulo: "Desborde de canal pluvial",
        zona: "Sur",
        hora: "Hoy, 11:02 a. m.",
      },
      {
        id: "a2",
        color: "roja",
        titulo: "Deslizamiento activo en ladera",
        zona: "Asentamiento Sur Alto",
        hora: "Hoy, 10:10 a. m.",
      },
      {
        id: "a3",
        color: "amarilla",
        titulo: "Suelo saturado, riesgo de deslave",
        zona: "Sur",
        hora: "Hoy, 08:50 a. m.",
      },
    ],
    incidencias: [
      {
        id: "i1",
        icono: "mountain",
        titulo: "Deslizamiento sobre vía de acceso",
        ubicacion: "Km 4 vía Sur",
        hora: "Hoy, 11:00 a. m.",
        estado: "En proceso",
      },
      {
        id: "i2",
        icono: "droplet",
        titulo: "Vivienda anegada",
        ubicacion: "Sector Sur Alto",
        hora: "Hoy, 09:30 a. m.",
        estado: "En proceso",
      },
      {
        id: "i3",
        icono: "droplet",
        titulo: "Calle intransitable por acumulación de agua",
        ubicacion: "Av. Los Sauces",
        hora: "Hoy, 08:15 a. m.",
        estado: "Atendida",
      },
    ],
    mapa: {
      centro: { lat: CENTRO_BASE.lat - 0.03, lng: CENTRO_BASE.lng - 0.004 },
      zoom: 13,
      poligono: [
        { lat: CENTRO_BASE.lat - 0.02, lng: CENTRO_BASE.lng - 0.02 },
        { lat: CENTRO_BASE.lat - 0.021, lng: CENTRO_BASE.lng + 0.014 },
        { lat: CENTRO_BASE.lat - 0.038, lng: CENTRO_BASE.lng + 0.012 },
        { lat: CENTRO_BASE.lat - 0.04, lng: CENTRO_BASE.lng - 0.018 },
      ],
      marcadores: [
        { lat: CENTRO_BASE.lat - 0.028, lng: CENTRO_BASE.lng - 0.006, tipo: "roja" },
        { lat: CENTRO_BASE.lat - 0.033, lng: CENTRO_BASE.lng + 0.002, tipo: "roja" },
        { lat: CENTRO_BASE.lat - 0.031, lng: CENTRO_BASE.lng - 0.011, tipo: "amarilla" },
      ],
    },
  },
  este: {
    id: "este",
    nombre: "Este",
    resumen: {
      ciudadanosRegistrados: 10210,
      ciudadanosNuevosSemana: 176,
      incidenciasReportadas: 52,
      incidenciasHoy: 7,
      alertasActivas: 3,
      alertasCriticas: 1,
      alertasModeradas: 2,
      riesgo: { etiqueta: "Medio", detalle: "Monitorear evolución de lluvias" },
    },
    alertas: [
      {
        id: "a1",
        color: "amarilla",
        titulo: "Llovizna persistente, calles resbalosas",
        zona: "Este",
        hora: "Hoy, 09:15 a. m.",
      },
      {
        id: "a2",
        color: "amarilla",
        titulo: "Visibilidad reducida por neblina",
        zona: "Este",
        hora: "Hoy, 06:40 a. m.",
      },
      {
        id: "a3",
        color: "verde",
        titulo: "Condiciones estables en la zona",
        zona: "Este",
        hora: "Ayer, 08:00 p. m.",
      },
    ],
    incidencias: [
      {
        id: "i1",
        icono: "droplet",
        titulo: "Encharcamiento leve en cruce vial",
        ubicacion: "Av. Oriente y Jr. Las Flores",
        hora: "Hoy, 09:20 a. m.",
        estado: "Atendida",
      },
      {
        id: "i2",
        icono: "tree",
        titulo: "Rama sobre línea eléctrica",
        ubicacion: "Calle Los Cedros",
        hora: "Hoy, 07:50 a. m.",
        estado: "En proceso",
      },
    ],
    mapa: {
      centro: { lat: CENTRO_BASE.lat - 0.002, lng: CENTRO_BASE.lng + 0.03 },
      zoom: 13,
      poligono: [
        { lat: CENTRO_BASE.lat + 0.008, lng: CENTRO_BASE.lng + 0.022 },
        { lat: CENTRO_BASE.lat + 0.006, lng: CENTRO_BASE.lng + 0.042 },
        { lat: CENTRO_BASE.lat - 0.012, lng: CENTRO_BASE.lng + 0.04 },
        { lat: CENTRO_BASE.lat - 0.011, lng: CENTRO_BASE.lng + 0.02 },
      ],
      marcadores: [{ lat: CENTRO_BASE.lat - 0.001, lng: CENTRO_BASE.lng + 0.03, tipo: "amarilla" }],
    },
  },
  oeste: {
    id: "oeste",
    nombre: "Oeste",
    resumen: {
      ciudadanosRegistrados: 7040,
      ciudadanosNuevosSemana: 61,
      incidenciasReportadas: 15,
      incidenciasHoy: 1,
      alertasActivas: 0,
      alertasCriticas: 0,
      alertasModeradas: 0,
      riesgo: { etiqueta: "Bajo", detalle: "Sin incidencias relevantes en curso" },
    },
    alertas: [
      {
        id: "a1",
        color: "verde",
        titulo: "Condiciones estables en la zona",
        zona: "Oeste",
        hora: "Hoy, 06:00 a. m.",
      },
    ],
    incidencias: [
      {
        id: "i1",
        icono: "tree",
        titulo: "Poda pendiente de árbol en riesgo",
        ubicacion: "Parque Oeste",
        hora: "Ayer, 04:10 p. m.",
        estado: "En proceso",
      },
    ],
    mapa: {
      centro: { lat: CENTRO_BASE.lat + 0.004, lng: CENTRO_BASE.lng - 0.032 },
      zoom: 13,
      poligono: [
        { lat: CENTRO_BASE.lat + 0.014, lng: CENTRO_BASE.lng - 0.022 },
        { lat: CENTRO_BASE.lat + 0.012, lng: CENTRO_BASE.lng - 0.042 },
        { lat: CENTRO_BASE.lat - 0.006, lng: CENTRO_BASE.lng - 0.044 },
        { lat: CENTRO_BASE.lat - 0.005, lng: CENTRO_BASE.lng - 0.02 },
      ],
      marcadores: [],
    },
  },
};
