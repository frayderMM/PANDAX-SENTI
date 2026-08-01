<script setup lang="ts">
import BrandSection from "./BrandSection.vue";
import LoginForm from "./LoginForm.vue";
</script>

<template>
  <main class="login-page">
    <BrandSection />
    <section class="login-page__panel" aria-label="Ingreso al sistema">
      <LoginForm />
    </section>
  </main>
</template>

<style scoped>
.login-page {
  --superficie: #ffffff;
  --borde: #e2e7f3;
  --azul: #0866f5;
  --azul-oscuro: #071b4a;
  --azul-oscuro-hover: #0655d1;
  --azul-tenue: #eaf1fe;
  --tinta-suave: #5b6b8c;
  --tinta-tenue: #9aa6c0;
  --rojo: #d0342c;

  display: grid;
  grid-template-columns: 1.1fr 1fr;
  grid-template-areas: "intro panel" "features panel";
  align-content: center;
  gap: 24px 56px;
  min-height: 100vh;
  padding: 56px 6vw;
  background:
    radial-gradient(circle at 90% 0%, #eaf1fe 0%, transparent 45%),
    radial-gradient(circle at 0% 100%, #f2f6fe 0%, transparent 50%),
    #ffffff;
  font-family: Inter, Manrope, system-ui, -apple-system, "Segoe UI", sans-serif;
  color: var(--azul-oscuro);
  box-sizing: border-box;
}

.login-page :deep(.brand-intro) {
  grid-area: intro;
  align-self: end;
}

.login-page :deep(.brand-features) {
  grid-area: features;
  align-self: start;
}

.login-page__panel {
  grid-area: panel;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 1100px) {
  .login-page {
    grid-template-columns: 1fr 1fr;
    gap: 20px 32px;
    padding: 40px 4vw;
  }
}

@media (max-width: 767px) {
  .login-page {
    grid-template-columns: 1fr;
    grid-template-areas: "intro" "panel" "features";
    gap: 28px;
    padding: 28px 16px;
  }

  .login-page :deep(.brand-intro),
  .login-page :deep(.brand-features) {
    align-self: auto;
  }
}
</style>
