<script setup lang="ts">
import { reactive, ref } from "vue";
import Icon from "./Icon.vue";
import PasswordInput from "./PasswordInput.vue";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const form = reactive({ email: "", password: "" });
const errors = reactive({ email: "", password: "" });
const remember = ref(true);
const submitting = ref(false);
const successMessage = ref("");
const forgotMessage = ref("");

function validate() {
  const email = form.email.trim();
  errors.email = !email
    ? "Ingresa tu correo institucional."
    : !EMAIL_RE.test(email)
      ? "Ingresa un correo con formato válido."
      : "";

  errors.password = !form.password
    ? "Ingresa tu contraseña."
    : form.password.length < 6
      ? "La contraseña debe tener al menos 6 caracteres."
      : "";

  return !errors.email && !errors.password;
}

async function handleSubmit() {
  successMessage.value = "";
  if (!validate() || submitting.value) return;

  submitting.value = true;
  await new Promise((resolve) => setTimeout(resolve, 800));
  submitting.value = false;
  successMessage.value = "Inicio de sesión simulado correctamente";
}

// Pantalla de recuperación aún no implementada; se deja explícito en vez de
// simular una navegación que no existe.
function handleForgotPassword() {
  forgotMessage.value = "Recuperación de contraseña: pendiente de implementación.";
}
</script>

<template>
  <div class="login-card">
    <span class="login-card__icon">
      <Icon name="lock-keyhole" :size="26" />
    </span>
    <h2 class="login-card__title">Ingreso al sistema</h2>
    <p class="login-card__subtitle">Acceso exclusivo para personal municipal autorizado.</p>

    <form novalidate @submit.prevent="handleSubmit">
      <div class="field">
        <label for="email" class="field__label">Correo institucional</label>
        <div class="field__control" :class="{ 'field__control--error': !!errors.email }">
          <Icon name="mail" :size="18" class="field__icon" />
          <input
            id="email"
            v-model="form.email"
            type="email"
            class="field__input"
            placeholder="nombre@municipio.gob.pe"
            autocomplete="email"
            :aria-invalid="!!errors.email"
            :aria-describedby="errors.email ? 'email-error' : undefined"
            @blur="validate"
          />
        </div>
        <p v-if="errors.email" id="email-error" class="field__error" role="alert">
          {{ errors.email }}
        </p>
      </div>

      <PasswordInput
        id="password"
        v-model="form.password"
        :error="errors.password"
        @blur="validate"
      />

      <div class="login-card__options">
        <label class="checkbox">
          <input v-model="remember" type="checkbox" />
          <span>Recordarme</span>
        </label>
        <button type="button" class="link-button" @click="handleForgotPassword">
          ¿Olvidaste tu contraseña?
        </button>
      </div>
      <p v-if="forgotMessage" class="login-card__hint" role="status">{{ forgotMessage }}</p>

      <button type="submit" class="submit-button" :disabled="submitting">
        <span v-if="submitting" class="spinner" aria-hidden="true"></span>
        <span>{{ submitting ? "Ingresando…" : "Ingresar" }}</span>
        <Icon v-if="!submitting" name="arrow-right" :size="18" />
      </button>

      <p v-if="successMessage" class="login-card__success" role="status">
        {{ successMessage }}
      </p>
    </form>

    <div class="login-card__footer">
      <Icon name="shield-check" :size="16" />
      <span>Acceso restringido a personal autorizado.</span>
    </div>
  </div>
</template>

<style scoped>
.login-card {
  width: 100%;
  max-width: 580px;
  padding: 48px;
  background: var(--superficie);
  border-radius: 28px;
  box-shadow: 0 24px 60px rgba(7, 27, 74, 0.1);
}

.login-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 20px;
  border-radius: 50%;
  background: var(--azul-tenue);
  color: var(--azul);
}

.login-card__title {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 800;
  text-align: center;
  color: var(--azul-oscuro);
}

.login-card__subtitle {
  margin: 0 0 32px;
  font-size: 14px;
  text-align: center;
  color: var(--tinta-suave);
}

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

.field__error {
  margin: 0;
  font-size: 12.5px;
  color: var(--rojo);
}

.login-card__options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 24px;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  color: var(--azul-oscuro);
}

.checkbox input {
  width: 17px;
  height: 17px;
  accent-color: var(--azul);
}

.link-button {
  border: none;
  background: none;
  padding: 2px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--azul);
  text-decoration: none;
}

.link-button:hover {
  text-decoration: underline;
}

.login-card__hint {
  margin: -12px 0 20px;
  font-size: 13px;
  color: var(--tinta-suave);
}

.submit-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  height: 52px;
  border: none;
  border-radius: 12px;
  background: var(--azul);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  transition: background-color 0.15s ease, transform 0.05s ease;
}

.submit-button:hover:not(:disabled) {
  background: var(--azul-oscuro-hover);
}

.submit-button:active:not(:disabled) {
  transform: scale(0.99);
}

.submit-button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.submit-button:focus-visible,
.link-button:focus-visible {
  outline: 2px solid var(--azul);
  outline-offset: 2px;
}

.spinner {
  width: 16px;
  height: 16px;
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

.login-card__success {
  margin: 16px 0 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: #e7f3ea;
  color: #1c6b3a;
  font-size: 13.5px;
  text-align: center;
}

.login-card__footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid var(--borde);
  font-size: 12.5px;
  color: var(--tinta-suave);
}

@media (max-width: 767px) {
  .login-card {
    padding: 28px 20px;
    border-radius: 20px;
  }

  .login-card__title {
    font-size: 22px;
  }
}
</style>
