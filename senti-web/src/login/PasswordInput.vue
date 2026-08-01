<script setup lang="ts">
import { ref } from "vue";
import Icon from "./Icon.vue";

const props = defineProps<{
  id: string;
  modelValue: string;
  error?: string;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "blur"): void;
}>();

const visible = ref(false);

function onInput(event: Event) {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}
</script>

<template>
  <div class="field">
    <label :for="id" class="field__label">Contraseña</label>
    <div class="field__control" :class="{ 'field__control--error': !!error }">
      <Icon name="lock-keyhole" :size="18" class="field__icon" />
      <input
        :id="id"
        :type="visible ? 'text' : 'password'"
        class="field__input"
        :value="modelValue"
        placeholder="••••••••••••"
        autocomplete="current-password"
        :aria-invalid="!!error"
        :aria-describedby="error ? `${id}-error` : undefined"
        @input="onInput"
        @blur="emit('blur')"
      />
      <button
        type="button"
        class="field__toggle"
        :aria-label="visible ? 'Ocultar contraseña' : 'Mostrar contraseña'"
        @click="visible = !visible"
      >
        <Icon :name="visible ? 'eye-off' : 'eye'" :size="18" />
      </button>
    </div>
    <p v-if="error" :id="`${id}-error`" class="field__error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 18px;
}

.field__label {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--azul-oscuro);
}

.field__control {
  position: relative;
  display: flex;
  align-items: center;
  border: 1px solid var(--borde);
  border-radius: 12px;
  background: var(--superficie);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field__control:focus-within {
  border-color: var(--azul);
  box-shadow: 0 0 0 4px var(--azul-tenue);
}

.field__control--error {
  border-color: var(--rojo);
}

.field__icon {
  position: absolute;
  left: 14px;
  color: var(--tinta-suave);
}

.field__input {
  width: 100%;
  height: 50px;
  padding: 0 44px;
  border: none;
  outline: none;
  background: transparent;
  border-radius: inherit;
  font-size: 14.5px;
  color: var(--azul-oscuro);
}

.field__input::placeholder {
  color: var(--tinta-tenue);
}

.field__toggle {
  position: absolute;
  right: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--tinta-suave);
}

.field__toggle:hover {
  background: var(--azul-tenue);
  color: var(--azul);
}

.field__toggle:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}

.field__error {
  margin: 0;
  font-size: 12.5px;
  color: var(--rojo);
}
</style>
