<script setup lang="ts">
import FeatureCard from "./FeatureCard.vue";

const features = [
  { icon: "bell", title: "Alertas", description: "Notificaciones en tiempo real" },
  { icon: "radar", title: "Monitoreo", description: "Situación en tiempo real" },
  { icon: "map-pin", title: "Zonas", description: "Áreas prioritarias" },
  { icon: "clipboard-check", title: "Seguimiento", description: "Acciones y reportes" },
];
</script>

<template>
  <div class="brand-intro">
    <div class="brand-intro__header">
      <img class="brand-intro__logo" src="/senti-icono.png" alt="Senti" />
      <div>
        <p class="brand-intro__name">Senti</p>
        <p class="brand-intro__tagline">Portal municipal inteligente</p>
      </div>
    </div>

    <h1 class="brand-intro__headline">
      Gestiona alertas<br />
      y monitoreo <span class="brand-intro__accent">frente<br />a desastres</span>
    </h1>
  </div>

  <div class="brand-features">
    <FeatureCard
      v-for="feature in features"
      :key="feature.title"
      :icon="feature.icon"
      :title="feature.title"
      :description="feature.description"
    />
    <img class="brand-features__watermark" src="/senti-icono.png" alt="" aria-hidden="true" />
  </div>
</template>

<style scoped>
.brand-intro__header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 40px;
}

.brand-intro__logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  object-fit: cover;
  box-shadow: 0 6px 16px rgba(8, 102, 245, 0.25);
}

.brand-intro__name {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: var(--azul-oscuro);
}

.brand-intro__tagline {
  margin: 2px 0 0;
  font-size: 13.5px;
  color: var(--tinta-suave);
}

.brand-intro__headline {
  margin: 0;
  font-size: 44px;
  line-height: 1.15;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--azul-oscuro);
}

.brand-intro__accent {
  color: var(--azul);
}

.brand-features {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-top: 40px;
  align-items: stretch;
}

.brand-features__watermark {
  position: absolute;
  left: -12px;
  bottom: -64px;
  width: 180px;
  height: 180px;
  object-fit: contain;
  opacity: 0.05;
  pointer-events: none;
  user-select: none;
}

@media (max-width: 1100px) {
  .brand-intro__headline {
    font-size: 34px;
  }

  .brand-intro__header {
    margin-bottom: 28px;
  }

  .brand-features {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin-top: 28px;
  }
}

@media (max-width: 767px) {
  .brand-intro__header {
    margin-bottom: 20px;
  }

  .brand-intro__logo {
    width: 46px;
    height: 46px;
    border-radius: 13px;
  }

  .brand-intro__headline {
    font-size: 26px;
  }

  .brand-features {
    margin-top: 8px;
  }

  .brand-features__watermark {
    display: none;
  }
}

@media (max-width: 380px) {
  .brand-features {
    grid-template-columns: 1fr;
  }
}
</style>
