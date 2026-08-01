/**
 * Iconos en línea (trazo, estilo lucide) del módulo de operador. Igual que en
 * `src/login/icons.ts`: se escriben a mano para no sumar una dependencia de
 * iconos por un puñado de glifos fijos.
 */
export const ICONS: Record<string, string> = {
  home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/><path d="M9.5 20v-6h5v6"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  "help-circle":
    '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.2a2.5 2.5 0 0 1 4.9.8c0 1.7-2.4 2-2.4 3.5"/><path d="M12 17h.01"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  "cloud-upload":
    '<path d="M7 18a4.5 4.5 0 0 1-.6-8.96 5.5 5.5 0 0 1 10.7-1.9A4.5 4.5 0 0 1 17 18H7Z"/><path d="M12 20v-8"/><path d="m9 15 3-3 3 3"/>',
  "file-pdf":
    '<path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z"/><path d="M15 2v5h5"/><path d="M8.5 17v-4h1.2a1.2 1.2 0 0 1 0 2.4H8.5"/><path d="M12.3 17v-4h1a1.5 1.5 0 0 1 0 4h-1Z"/><path d="M16.3 15h2M16.3 13v4"/>',
  "check-circle":
    '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.2 2.3 2.3 4.7-4.9"/>',
  sparkles:
    '<path d="M12 3v4M12 17v4M4 12h4M16 12h4M6.3 6.3l2.4 2.4M15.3 15.3l2.4 2.4M17.7 6.3l-2.4 2.4M8.7 15.3l-2.4 2.4"/>',
  type: '<path d="M5 5h14M12 5v14M9 19h6"/>',
  "map-pin":
    '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
  tag: '<path d="M12.6 2.6 21 11l-8.4 8.4a2 2 0 0 1-2.8 0L3 12.6V4a1.4 1.4 0 0 1 1.4-1.4h8.2Z"/><circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
  "align-left":
    '<path d="M4 6h16M4 12h10M4 18h13"/>',
  shield: '<path d="M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6l7-3Z"/>',
  "shield-check":
    '<path d="M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6l7-3Z"/><path d="m9 12 2 2 4-4"/>',
  "alert-triangle":
    '<path d="M12 4 2.5 20h19L12 4Z"/><path d="M12 10.5v4"/><path d="M12 17.2h.01"/>',
  "alert-octagon":
    '<path d="M8.3 3h7.4L21 8.3v7.4L15.7 21H8.3L3 15.7V8.3L8.3 3Z"/><path d="M12 8v5"/><path d="M12 16.2h.01"/>',
  flag: '<path d="M5 3v18"/><path d="M5 4h11l-2 4 2 4H5"/>',
  users:
    '<path d="M13.5 20v-1.7a3.5 3.5 0 0 0-3.5-3.5H6a3.5 3.5 0 0 0-3.5 3.5V20"/><circle cx="8" cy="8.5" r="3.2"/><path d="M16.5 20v-1.7a3.5 3.5 0 0 0-2.3-3.29"/><path d="M14.5 5.3a3.2 3.2 0 0 1 0 6.2"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  send: '<path d="M21 3 3 10.5l7.5 3M21 3l-7.5 18-3-7.5M21 3 10.5 13.5"/>',
  save: '<path d="M5 3h11l3 3v15H5V3Z"/><path d="M8 3v6h8V3"/><path d="M8 21v-7h8v7"/>',
  logout:
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
  thermometer:
    '<path d="M14 4a2 2 0 0 0-4 0v9.5a4 4 0 1 0 4 0V4Z"/><path d="M12 15v-5"/>',
  droplet:
    '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z"/>',
  percent: '<path d="M5 19 19 5"/><circle cx="7" cy="7" r="2.2"/><circle cx="17" cy="17" r="2.2"/>',
  wind: '<path d="M3 8h11a2.5 2.5 0 1 0-2.3-3.4"/><path d="M3 12h15a2.5 2.5 0 1 1-2.3 3.4"/><path d="M3 16h8a2 2 0 1 1-1.8 2.8"/>',
  sprout:
    '<path d="M12 21v-8"/><path d="M12 13c-4 0-7-2.5-7-7 4 0 7 2 7 5 0-3 3-5 7-5 0 4.5-3 7-7 7Z"/>',
  waves:
    '<path d="M2 8c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 3-1.5 4.5 0 3 1.5 4.5 0"/><path d="M2 14c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 3-1.5 4.5 0 3 1.5 4.5 0"/><path d="M2 20c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 3-1.5 4.5 0 3 1.5 4.5 0"/>',
  cloud:
    '<path d="M7 18a4.5 4.5 0 0 1-.6-8.96 5.5 5.5 0 0 1 10.7-1.9A4.5 4.5 0 0 1 17 18H7Z"/>',
  "cloud-rain":
    '<path d="M6.5 15.5a4.3 4.3 0 0 1-.6-8.55A5.3 5.3 0 0 1 16.2 5.4a4.3 4.3 0 0 1-.7 10.1"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/>',
  "cloud-lightning":
    '<path d="M6.5 14.5a4.3 4.3 0 0 1-.6-8.55A5.3 5.3 0 0 1 16.2 4.4a4.3 4.3 0 0 1-.7 10.1"/><path d="m13 13-3 4h3l-3 4"/>',
  "refresh-cw":
    '<path d="M3 12a9 9 0 0 1 15.4-6.4L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.4 6.4L3 16"/><path d="M3 21v-5h5"/>',
  "chevron-right": '<path d="m9 6 6 6-6 6"/>',
  tree: '<path d="M12 22v-6"/><path d="M12 16 7 11h3L7 7h3L8 3h8l-2 4h3l-3 4h3l-5 5Z"/>',
  mountain:
    '<path d="m3 20 6.5-11L13 15l2.5-4L21 20Z"/><path d="m12.5 12.5 1.8-3.2"/>',
  "file-text":
    '<path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z"/><path d="M15 2v5h5"/><path d="M8 13h8M8 17h8M8 9h3"/>',
};
