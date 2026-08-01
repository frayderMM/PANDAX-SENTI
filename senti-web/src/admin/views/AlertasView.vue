<script setup lang="ts">
import { reactive, ref } from "vue";
import AdminHeader from "../AdminHeader.vue";
import DocumentUploadCard from "../components/DocumentUploadCard.vue";
import AlertFormCard from "../components/AlertFormCard.vue";
import SeverityCard from "../components/SeverityCard.vue";
import ZonaAfectadaCard from "../components/ZonaAfectadaCard.vue";
import InfoStatCard from "../components/InfoStatCard.vue";
import ActionsPanel from "../components/ActionsPanel.vue";
import type { AlertaForm, DocumentoAdjunto } from "../types";

const documento = ref<DocumentoAdjunto | null>({
  nombre: "Reporte_inundacion_Centro.pdf",
  tamanoTexto: "1.2 MB",
  fechaTexto: "12 may 2025 10:32 a. m.",
});

const analizando = ref(false);
const autocompletado = ref(true);

const alerta = reactive<AlertaForm>({
  titulo: "Inundación en zona centro por lluvias intensas",
  zona: "centro",
  fechaHora: "2025-05-12T10:30",
  tipoEvento: "inundacion",
  descripcion:
    "Se registran lluvias intensas desde la madrugada provocando anegaciones en calles principales del centro. Nivel de agua entre 20 y 40 cm en vialidades. Tránsito afectado y riesgo para peatones en pasos a desnivel.",
  recomendacion:
    "Evitar transitar por zonas bajas y calles anegadas. No intentar cruzar corrientes de agua. Seguir indicaciones de Protección Civil.",
  gravedad: "amarillo",
});

// Resumen de la derecha: en un análisis real vendría de Gemma + monitoreo.
// Aquí es un mock fijo, no se recalcula a partir del formulario.
const resumen = {
  zonaNombre: "Centro",
  zonaDetalle: "Colonias del centro y zonas aledañas",
  prioridad: "Media",
  prioridadDetalle: "Requiere atención y monitoreo",
  ciudadanos: "12,450",
};

const guardando = ref(false);
const enviando = ref(false);
const mensaje = ref("");

function formatearArchivo(file: File): DocumentoAdjunto {
  const mb = file.size / (1024 * 1024);
  return {
    nombre: file.name,
    tamanoTexto: mb < 0.1 ? "< 0.1 MB" : `${mb.toFixed(1)} MB`,
    fechaTexto: new Intl.DateTimeFormat("es-PE", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date()),
  };
}

function onArchivoSeleccionado(file: File) {
  documento.value = formatearArchivo(file);
  autocompletado.value = false;
  mensaje.value = "";
}

async function analizarDocumento() {
  if (!documento.value || analizando.value) return;
  analizando.value = true;
  mensaje.value = "";
  await new Promise((resolve) => setTimeout(resolve, 900));
  analizando.value = false;
  autocompletado.value = true;
  mensaje.value = "Documento analizado: se completaron los datos de la alerta.";
}

async function guardarCambios() {
  if (guardando.value) return;
  guardando.value = true;
  mensaje.value = "";
  await new Promise((resolve) => setTimeout(resolve, 500));
  guardando.value = false;
  mensaje.value = "Cambios guardados (simulado).";
}

async function enviarAlerta() {
  if (enviando.value) return;
  enviando.value = true;
  mensaje.value = "";
  await new Promise((resolve) => setTimeout(resolve, 900));
  enviando.value = false;
  mensaje.value = "Alerta enviada (simulado). Todavía no se conecta a ningún canal real.";
}

function vistaPrevia() {
  mensaje.value = "Vista previa: pendiente de implementación.";
}
</script>

<template>
  <div>
    <AdminHeader
      title="Gestión de alertas"
      subtitle="Crea y envía alertas para mantener informada a la comunidad."
    />

    <p v-if="mensaje" class="alertas-view__mensaje" role="status">{{ mensaje }}</p>

    <div class="alertas-view__grid">
      <div class="alertas-view__main">
        <DocumentUploadCard
          :archivo="documento"
          :analizando="analizando"
          @archivo-seleccionado="onArchivoSeleccionado"
          @analizar="analizarDocumento"
        />
        <AlertFormCard
          v-model="alerta"
          :autocompletado="autocompletado"
          :guardando="guardando"
          :enviando="enviando"
          @guardar="guardarCambios"
          @enviar="enviarAlerta"
        />
      </div>

      <aside class="alertas-view__aside">
        <SeverityCard v-model="alerta.gravedad" />
        <ZonaAfectadaCard :nombre="resumen.zonaNombre" :detalle="resumen.zonaDetalle" />
        <InfoStatCard
          icon="flag"
          title="Prioridad estimada"
          :value="resumen.prioridad"
          :detail="resumen.prioridadDetalle"
          badge="Automática"
        />
        <InfoStatCard
          icon="users"
          title="Ciudadanos a notificar"
          :value="resumen.ciudadanos"
          detail="Personas en la zona"
          badge="Estimado"
        />
        <ActionsPanel :enviando="enviando" @vista-previa="vistaPrevia" @enviar="enviarAlerta" />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.alertas-view__mensaje {
  margin: -8px 0 16px;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--verde-tenue);
  color: #1c6b3a;
  font-size: 13px;
}

.alertas-view__grid {
  display: grid;
  grid-template-columns: 2.1fr 1fr;
  align-items: start;
  gap: 24px;
}

.alertas-view__main {
  min-width: 0;
}

.alertas-view__aside {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

@media (max-width: 1100px) {
  .alertas-view__grid {
    grid-template-columns: 1fr;
  }
}
</style>
