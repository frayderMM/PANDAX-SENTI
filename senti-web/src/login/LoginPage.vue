<script setup lang="ts">
import BrandSection from "./BrandSection.vue";
import LoginForm from "./LoginForm.vue";
</script>

<template>
  <main class="login-page">
    <header class="login-page__topbar">
      <a class="login-page__brand" href="/" aria-label="SENTI, página de inicio">
        <img src="/senti-icono.png" alt="" />
        <span>SENTI</span>
      </a>
      <nav class="login-page__nav" aria-label="Navegación del portal">
        <a href="/">Inicio</a>
        <a href="/#actividad">Mapa</a>
        <a href="/info-general.html">Información general</a>
        <a href="/#reportes">Reportes</a>
        <a class="login-page__nav-active" href="/login.html" aria-current="page">
          Acceso municipal
        </a>
      </nav>
    </header>
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

.login-page__topbar {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 6vw;
}

.login-page__brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--azul-oscuro);
  font-size: 18px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-decoration: none;
}

.login-page__brand img {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  box-shadow: 0 5px 14px rgba(8, 102, 245, 0.2);
}

.login-page__nav {
  display: flex;
  align-items: center;
  gap: clamp(14px, 2.2vw, 30px);
}

.login-page__nav a {
  color: var(--tinta-suave);
  font-size: 12px;
  font-weight: 750;
  text-decoration: none;
  white-space: nowrap;
}

.login-page__nav a:hover { color: var(--azul); }

.login-page__nav-active {
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--azul-oscuro);
  color: #fff !important;
  box-shadow: 0 7px 16px rgba(7, 27, 74, 0.16);
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
    padding: 92px 16px 28px;
  }

  .login-page__topbar {
    align-items: flex-start;
    padding: 16px;
  }

  .login-page__nav {
    gap: 10px;
  }

  .login-page__nav a:not(.login-page__nav-active) {
    display: none;
  }

  .login-page__nav-active { padding: 9px 11px; }

  .login-page :deep(.brand-intro),
  .login-page :deep(.brand-features) {
    align-self: auto;
  }
}
</style>
