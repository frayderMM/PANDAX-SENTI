<script setup lang="ts">
import { reactive, ref } from "vue";
import AdminHeader from "../AdminHeader.vue";
import DocumentUploadCard from "../components/DocumentUploadCard.vue";
import AlertFormCard from "../components/AlertFormCard.vue";
import SeverityCard from "../components/SeverityCard.vue";
import ZonaAfectadaCard from "../components/ZonaAfectadaCard.vue";
import InfoStatCard from "../components/InfoStatCard.vue";
import ActionsPanel from "../components/ActionsPanel.vue";
import { gravedadDesdeNivel, interpretarPdf, publicarAlerta } from "../services/alertas";
import type { AlertaForm, DocumentoAdjunto } from "../types";

const archivoSeleccionado = ref<File | null>(null);
const documento = ref<DocumentoAdjunto | null>(null);

const analizando = ref(false);
const autocompletado = ref(false);

const alerta = reactive<AlertaForm>({
  titulo: "",
  zona: "Lurigancho-Chosica",
  fechaHora: new Date().toISOString().slice(0, 16),
  tipoEvento: "inundacion",
  descripcion: "",
  recomendacion: "",
  gravedad: "amarillo",
});

const guardando = ref(false);
const enviando = ref(false);
const mensaje = ref("");
const mensajeEsError = ref(false);

// Antes de publicar no hay un número real todavía: se calcula recién al
// enviar, contra los suscriptores activos del distrito escrito arriba.
const destinatarios = ref<number | null>(null);
const ultimaNotificacion = ref<"en curso" | "sin destinatarios" | "deshabilitada" | null>(null);

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
  archivoSeleccionado.value = file;
  documento.value = formatearArchivo(file);
  autocompletado.value = false;
  mensaje.value = "";
}

async function analizarDocumento() {
  if (!archivoSeleccionado.value || analizando.value) return;
  analizando.value = true;
  mensaje.value = "";
  mensajeEsError.value = false;
  try {
    const resultado = await interpretarPdf(archivoSeleccionado.value);
    const propuesta = resultado.propuesta;
    alerta.titulo = propuesta.titulo;
    alerta.tipoEvento = propuesta.tipo_evento;
    alerta.descripcion = propuesta.resumen_ciudadano;
    alerta.recomendacion = propuesta.recomendaciones.join("\n");
    alerta.gravedad = gravedadDesdeNivel(propuesta.nivel_detectado);
    autocompletado.value = true;
    mensaje.value = propuesta.datos_faltantes.length
      ? `Documento analizado. El modelo no pudo confirmar: ${propuesta.datos_faltantes.join(", ")}.`
      : "Documento analizado: revisa los campos antes de enviar.";
  } catch (motivo) {
    mensajeEsError.value = true;
    mensaje.value = motivo instanceof Error ? motivo.message : "No se pudo analizar el documento.";
  } finally {
    analizando.value = false;
  }
}

async function guardarCambios() {
  if (guardando.value) return;
  guardando.value = true;
  mensaje.value = "";
  mensajeEsError.value = false;
  await new Promise((resolve) => setTimeout(resolve, 400));
  guardando.value = false;
  mensajeEsError.value = true;
  mensaje.value = "Guardar borrador todavía no está implementado: publica o descarta.";
}

async function enviarAlerta() {
  if (enviando.value) return;
  enviando.value = true;
  mensaje.value = "";
  mensajeEsError.value = false;
  try {
    const resultado = await publicarAlerta(alerta, { notificarWhatsapp: true });
    destinatarios.value = resultado.destinatarios_estimados;
    ultimaNotificacion.value = resultado.notificacion_whatsapp;
    mensaje.value =
      resultado.notificacion_whatsapp === "en curso"
        ? `Alerta publicada. Difundiéndose por WhatsApp a ${resultado.destinatarios_estimados} suscriptor(es) de ${resultado.distrito}.`
        : resultado.notificacion_whatsapp === "sin destinatarios"
          ? `Alerta publicada. Nadie tiene alertas de WhatsApp activas para ${resultado.distrito} todavía.`
          : "Alerta publicada. La difusión por WhatsApp no está configurada en este servidor.";
  } catch (motivo) {
    mensajeEsError.value = true;
    mensaje.value = motivo instanceof Error ? motivo.message : "No se pudo publicar la alerta.";
  } finally {
    enviando.value = false;
  }
}

function vistaPrevia() {
  mensajeEsError.value = false;
  mensaje.value = "Vista previa: pendiente de implementación.";
}
</script>

<template>
  <div>
    <AdminHeader
      title="Gestión de alertas"
      subtitle="Crea y envía alertas para mantener informada a la comunidad."
    />

    <p
      v-if="mensaje"
      class="alertas-view__mensaje"
      :class="{ 'alertas-view__mensaje--error': mensajeEsError }"
      role="status"
    >
      {{ mensaje }}
    </p>

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
        <ZonaAfectadaCard :nombre="alerta.zona || 'Sin distrito'" detalle="Distrito de la alerta" />
        <InfoStatCard
          icon="users"
          title="Ciudadanos a notificar"
          :value="destinatarios === null ? '—' : String(destinatarios)"
          :detail="destinatarios === null ? 'Se calcula al enviar' : `Suscritos por WhatsApp en ${alerta.zona}`"
          :badge="destinatarios === null ? 'Pendiente' : 'Real'"
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

.alertas-view__mensaje--error {
  background: var(--rojo-tenue);
  color: var(--rojo);
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
