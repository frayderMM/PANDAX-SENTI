<script setup lang="ts">
import Icon from "../Icon.vue";
import type { AlertaForm } from "../types";

defineProps<{
  autocompletado: boolean;
  guardando: boolean;
  enviando: boolean;
}>();

const emit = defineEmits<{
  (e: "guardar"): void;
  (e: "enviar"): void;
}>();

const form = defineModel<AlertaForm>({ required: true });

// Mismo enum que HazardType en senti-backend/app/domain.py, completo: si le
// falta un valor, la propuesta de Gemma puede traer un tipo que no está en
// esta lista y el <select> se queda sin nada seleccionado, en silencio.
const TIPOS_EVENTO = [
  { value: "inundacion", label: "Inundación" },
  { value: "huaico", label: "Huaico" },
  { value: "deslizamiento", label: "Deslizamiento" },
  { value: "lluvia", label: "Lluvia intensa" },
  { value: "sismo", label: "Sismo" },
  { value: "tsunami", label: "Tsunami" },
  { value: "incendio", label: "Incendio" },
  { value: "via_bloqueada", label: "Vía bloqueada" },
  { value: "puente_afectado", label: "Puente afectado" },
  { value: "acumulacion_agua", label: "Acumulación de agua" },
  { value: "caida_poste", label: "Caída de poste" },
  { value: "otro", label: "Otro" },
];

const GRAVEDADES = [
  { value: "verde", label: "Verde (Bajo)" },
  { value: "amarillo", label: "Amarillo (Medio)" },
  { value: "rojo", label: "Rojo (Alto)" },
];
</script>

<template>
  <section class="form-card">
    <header class="form-card__header">
      <h2 class="form-card__title">Datos de la alerta</h2>
      <span v-if="autocompletado" class="form-card__badge">
        <Icon name="sparkles" :size="13" />
        Autocompletado por análisis
      </span>
    </header>

    <form class="form-card__body" @submit.prevent="emit('enviar')">
      <label class="field">
        <span class="field__label">Título de alerta</span>
        <span class="field__control">
          <Icon name="type" :size="17" class="field__icon" />
          <input v-model="form.titulo" type="text" class="field__input" required />
        </span>
      </label>

      <div class="field-row">
        <label class="field">
          <span class="field__label">Distrito</span>
          <span class="field__control">
            <Icon name="map-pin" :size="17" class="field__icon" />
            <input
              v-model="form.zona"
              type="text"
              class="field__input"
              placeholder="Lurigancho-Chosica"
              required
            />
          </span>
        </label>

        <label class="field">
          <span class="field__label">Fecha y hora</span>
          <span class="field__control">
            <Icon name="calendar" :size="17" class="field__icon" />
            <input v-model="form.fechaHora" type="datetime-local" class="field__input" />
          </span>
        </label>
      </div>

      <label class="field">
        <span class="field__label">Tipo de evento</span>
        <span class="field__control">
          <Icon name="tag" :size="17" class="field__icon" />
          <select v-model="form.tipoEvento" class="field__input field__input--select">
            <option v-for="t in TIPOS_EVENTO" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
          <Icon name="chevron-down" :size="15" class="field__chevron" />
        </span>
      </label>

      <label class="field">
        <span class="field__label">Descripción</span>
        <span class="field__control field__control--textarea">
          <Icon name="align-left" :size="17" class="field__icon field__icon--top" />
          <textarea
            v-model="form.descripcion"
            rows="3"
            class="field__input field__input--textarea"
          ></textarea>
        </span>
      </label>

      <label class="field">
        <span class="field__label">Recomendación</span>
        <span class="field__control field__control--textarea">
          <Icon name="shield" :size="17" class="field__icon field__icon--top" />
          <textarea
            v-model="form.recomendacion"
            rows="3"
            class="field__input field__input--textarea"
          ></textarea>
        </span>
      </label>

      <label class="field">
        <span class="field__label">Nivel de gravedad</span>
        <span class="field__control">
          <span class="field__dot" :class="`field__dot--${form.gravedad}`" aria-hidden="true"></span>
          <select v-model="form.gravedad" class="field__input field__input--select field__input--dot">
            <option v-for="g in GRAVEDADES" :key="g.value" :value="g.value">{{ g.label }}</option>
          </select>
          <Icon name="chevron-down" :size="15" class="field__chevron" />
        </span>
      </label>

      <div class="form-card__actions">
        <button
          type="button"
          class="btn btn--ghost"
          :disabled="guardando"
          @click="emit('guardar')"
        >
          <span v-if="guardando" class="btn__spinner" aria-hidden="true"></span>
          <Icon v-else name="save" :size="16" />
          <span>{{ guardando ? "Guardando…" : "Guardar cambios" }}</span>
        </button>
        <button type="submit" class="btn btn--primary" :disabled="enviando">
          <span v-if="enviando" class="btn__spinner btn__spinner--light" aria-hidden="true"></span>
          <Icon v-else name="send" :size="16" />
          <span>{{ enviando ? "Enviando…" : "Enviar alerta" }}</span>
        </button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.form-card {
  margin-top: 20px;
  padding: 24px;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 16px;
  box-shadow: 0 2px 10px rgba(7, 27, 74, 0.04);
}

.form-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.form-card__title {
  font-size: 16px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.form-card__badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--azul-tenue);
  color: var(--azul);
  font-size: 11.5px;
  font-weight: 700;
}

.form-card__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--azul-oscuro);
}

.field__control {
  position: relative;
  display: flex;
  align-items: center;
  border: 1px solid var(--borde);
  border-radius: 10px;
  background: var(--superficie);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field__control:focus-within {
  border-color: var(--azul);
  box-shadow: 0 0 0 3px var(--azul-tenue);
}

.field__control--textarea {
  align-items: flex-start;
}

.field__icon {
  position: absolute;
  left: 12px;
  color: var(--texto-secundario);
}

.field__icon--top {
  top: 12px;
}

.field__input {
  width: 100%;
  height: 42px;
  padding: 0 14px 0 40px;
  border: none;
  outline: none;
  background: transparent;
  border-radius: inherit;
  font-size: 13.5px;
  color: var(--azul-oscuro);
}

.field__input--select {
  padding-right: 32px;
  appearance: none;
  -webkit-appearance: none;
}

.field__input--dot {
  padding-left: 38px;
}

.field__input--textarea {
  height: auto;
  padding-top: 11px;
  padding-bottom: 11px;
  resize: vertical;
  line-height: 1.5;
}

.field__chevron {
  position: absolute;
  right: 12px;
  color: var(--texto-secundario);
  pointer-events: none;
}

.field__dot {
  position: absolute;
  left: 15px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.field__dot--verde {
  background: var(--verde);
}

.field__dot--amarillo {
  background: var(--amarillo);
}

.field__dot--rojo {
  background: var(--rojo);
}

.form-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 4px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  padding: 0 18px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 700;
  border: 1px solid transparent;
}

.btn--ghost {
  border-color: var(--borde);
  background: var(--superficie);
  color: var(--azul-oscuro);
}

.btn--ghost:hover:not(:disabled) {
  background: var(--fondo);
}

.btn--primary {
  background: var(--azul);
  color: #fff;
}

.btn--primary:hover:not(:disabled) {
  background: #0a49d1;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}

.btn__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(7, 27, 74, 0.25);
  border-top-color: var(--azul-oscuro);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.btn__spinner--light {
  border-color: rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 560px) {
  .field-row {
    grid-template-columns: 1fr;
  }

  .form-card__actions {
    flex-direction: column-reverse;
    align-items: stretch;
  }
}
</style>
