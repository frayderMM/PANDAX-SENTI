import { createRouter, createWebHashHistory } from "vue-router";

/**
 * Hash history a propósito: `admin.html` es una entrada Vite separada de la
 * vista pública (`index.html`) y no hay reescritura de rutas en nginx para
 * servir este archivo en `/dashboard` o `/alertas`. Con hash, todas las
 * rutas resuelven al mismo `admin.html` sin tocar la configuración del
 * servidor (§8 de CLAUDE.md: nada que solo funcione con un parche fuera de
 * este repo).
 */
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/alertas" },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("./views/DashboardView.vue"),
    },
    {
      path: "/alertas",
      name: "alertas",
      component: () => import("./views/AlertasView.vue"),
    },
  ],
});
