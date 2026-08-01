<script setup lang="ts">
import { computed } from "vue";
import { ICONS } from "./icons";

const props = withDefaults(defineProps<{ name: string; size?: number }>(), {
  size: 20,
});

const markup = computed(() => ICONS[props.name] ?? "");
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="markup"
  ></svg>
</template>
