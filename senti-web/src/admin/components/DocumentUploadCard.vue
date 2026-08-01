<script setup lang="ts">
import { ref } from "vue";
import Icon from "../Icon.vue";

defineProps<{
  archivo: { nombre: string; tamanoTexto: string; fechaTexto: string } | null;
  analizando: boolean;
}>();

const emit = defineEmits<{
  (e: "archivo-seleccionado", file: File): void;
  (e: "analizar"): void;
}>();

const inputRef = ref<HTMLInputElement | null>(null);
const arrastrando = ref(false);
const errorArchivo = ref("");

function abrirSelector() {
  inputRef.value?.click();
}

function manejarArchivos(files: FileList | null) {
  errorArchivo.value = "";
  const file = files?.[0];
  if (!file) return;
  if (file.type !== "application/pdf") {
    errorArchivo.value = "Solo se aceptan archivos PDF.";
    return;
  }
  emit("archivo-seleccionado", file);
}

function onDrop(event: DragEvent) {
  arrastrando.value = false;
  manejarArchivos(event.dataTransfer?.files ?? null);
}

function onInputChange(event: Event) {
  const input = event.target as HTMLInputElement;
  manejarArchivos(input.files);
  input.value = "";
}
</script>

<template>
  <section class="upload-card">
    <div class="upload-card__row">
      <div
        class="dropzone"
        :class="{ 'dropzone--active': arrastrando }"
        @dragover.prevent="arrastrando = true"
        @dragleave.prevent="arrastrando = false"
        @drop.prevent="onDrop"
      >
        <Icon name="cloud-upload" :size="32" class="dropzone__icon" />
        <p class="dropzone__text">
          Arrastra y suelta tu archivo aquí<br />
          o
          <button type="button" class="dropzone__link" @click="abrirSelector">
            selecciona un archivo
          </button>
        </p>
        <p class="dropzone__meta">Formatos soportados: PDF</p>
        <p class="dropzone__meta">Tamaño máximo: 50 MB</p>
        <input
          ref="inputRef"
          type="file"
          accept="application/pdf"
          class="dropzone__input"
          aria-label="Seleccionar archivo PDF"
          @change="onInputChange"
        />
      </div>

      <div class="attachment">
        <p class="attachment__label">Documento adjunto</p>
        <div v-if="archivo" class="attachment__file">
          <span class="attachment__icon"><Icon name="file-pdf" :size="20" /></span>
          <div class="attachment__info">
            <p class="attachment__name">{{ archivo.nombre }}</p>
            <p class="attachment__meta">{{ archivo.tamanoTexto }} · {{ archivo.fechaTexto }}</p>
          </div>
          <Icon name="check-circle" :size="20" class="attachment__check" />
        </div>
        <p v-else class="attachment__empty">Ningún archivo seleccionado todavía.</p>
        <p v-if="errorArchivo" class="attachment__error" role="alert">{{ errorArchivo }}</p>
      </div>
    </div>

    <button
      type="button"
      class="analyze-button"
      :disabled="!archivo || analizando"
      @click="emit('analizar')"
    >
      <span v-if="analizando" class="analyze-button__spinner" aria-hidden="true"></span>
      <Icon v-else name="sparkles" :size="18" />
      <span>{{ analizando ? "Analizando documento…" : "Analizar documento" }}</span>
    </button>
  </section>
</template>

<style scoped>
.upload-card {
  padding: 24px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
}

.upload-card__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 28px 20px;
  text-align: center;
  border: 1.5px dashed var(--azul);
  border-radius: 14px;
  background: #f8faff;
  transition: background-color 0.15s ease;
}

.dropzone--active {
  background: var(--azul-tenue);
}

.dropzone__icon {
  color: var(--azul);
  margin-bottom: 4px;
}

.dropzone__text {
  font-size: 13.5px;
  color: var(--azul-oscuro);
  line-height: 1.5;
}

.dropzone__link {
  border: none;
  background: none;
  padding: 0;
  color: var(--azul);
  font-weight: 700;
  font-size: 13.5px;
  text-decoration: underline;
}

.dropzone__meta {
  font-size: 11.5px;
  color: var(--texto-secundario);
}

.dropzone__input {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
}

.attachment {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  border: 1px solid var(--borde);
  border-radius: 14px;
}

.attachment__label {
  font-size: 13px;
  font-weight: 700;
  color: var(--azul-oscuro);
}

.attachment__file {
  display: flex;
  align-items: center;
  gap: 12px;
}

.attachment__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 10px;
  background: var(--rojo-tenue);
  color: var(--rojo);
}

.attachment__info {
  min-width: 0;
  flex: 1;
}

.attachment__name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--azul-oscuro);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment__meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--texto-secundario);
}

.attachment__check {
  color: var(--verde);
  flex-shrink: 0;
}

.attachment__empty {
  font-size: 13px;
  color: var(--texto-secundario);
}

.attachment__error {
  margin: 0;
  font-size: 12px;
  color: var(--rojo);
}

.analyze-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  height: 46px;
  margin-top: 18px;
  border: none;
  border-radius: 12px;
  background: var(--azul);
  color: #fff;
  font-size: 14.5px;
  font-weight: 700;
}

.analyze-button:hover:not(:disabled) {
  background: #0a49d1;
}

.analyze-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.analyze-button:focus-visible,
.dropzone__link:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}

.analyze-button__spinner {
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 900px) {
  .upload-card__row {
    grid-template-columns: 1fr;
  }
}
</style>
