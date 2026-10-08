<script setup>
import { useId } from 'vue'

const gradientId = useId()
</script>

<template>
  <svg class="brand-logo" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0" style="stop-color: var(--brand-logo-start, #9ac4f4)" />
        <stop offset=".55" style="stop-color: var(--brand-logo-middle, #76a7e8)" />
        <stop offset="1" style="stop-color: var(--brand-logo-end, #5e8dd0)" />
      </linearGradient>
    </defs>
    <path
      d="M39 12.5H21A8.5 8.5 0 0 0 12.5 21v22a8.5 8.5 0 0 0 8.5 8.5h22a8.5 8.5 0 0 0 8.5-8.5V33"
      fill="none"
      :stroke="`url(#${gradientId})`"
      stroke-width="6.5"
      stroke-linecap="round"
    />
    <rect x="46.5" y="11" width="8" height="8" rx="1.8" style="fill: var(--brand-logo-tile, #a9cefa)" />
  </svg>
</template>
