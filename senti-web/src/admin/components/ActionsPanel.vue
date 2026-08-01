<script setup lang="ts">
import Icon from "../Icon.vue";

defineProps<{ enviando: boolean }>();

const emit = defineEmits<{
  (e: "vista-previa"): void;
  (e: "enviar"): void;
}>();
</script>

<template>
  <section class="actions-panel">
    <p class="actions-panel__hint">
      <Icon name="sparkles" :size="15" />
      <span>
        Los datos se actualizan automáticamente con base en el análisis del
        documento y la información de monitoreo.
      </span>
    </p>

    <div class="actions-panel__buttons">
      <button type="button" class="btn btn--ghost" @click="emit('vista-previa')">
        <Icon name="eye" :size="16" />
        <span>Vista previa</span>
      </button>
      <button
        type="button"
        class="btn btn--primary btn--split"
        :disabled="enviando"
        @click="emit('enviar')"
      >
        <span v-if="enviando" class="btn__spinner btn__spinner--light" aria-hidden="true"></span>
        <Icon v-else name="send" :size="16" />
        <span>{{ enviando ? "Enviando…" : "Enviar alerta" }}</span>
        <span class="btn__divider" aria-hidden="true"></span>
        <Icon name="chevron-down" :size="14" />
      </button>
    </div>
  </section>
</template>

<style scoped>
.actions-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  background: var(--azul-tenue);
  border-radius: 16px;
}

.actions-panel__hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  color: var(--azul);
  font-size: 12px;
  line-height: 1.5;
}

.actions-panel__buttons {
  display: flex;
  gap: 10px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 700;
  border: 1px solid transparent;
  white-space: nowrap;
}

.btn--ghost {
  flex: 1;
  border-color: var(--borde);
  background: var(--superficie);
  color: var(--azul-oscuro);
}

.btn--ghost:hover {
  background: var(--fondo);
}

.btn--primary {
  flex: 1.4;
  background: var(--azul);
  color: #fff;
}

.btn--primary:hover:not(:disabled) {
  background: #0a49d1;
}

.btn--split {
  padding-right: 12px;
}

.btn__divider {
  width: 1px;
  height: 16px;
  margin: 0 2px;
  background: rgba(255, 255, 255, 0.35);
}

.btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn:focus-visible {
  outline: 2px solid var(--azul-oscuro);
  outline-offset: 2px;
}

.btn__spinner {
  width: 14px;
  height: 14px;
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

@media (max-width: 380px) {
  .actions-panel__buttons {
    flex-direction: column;
  }
}
</style>
