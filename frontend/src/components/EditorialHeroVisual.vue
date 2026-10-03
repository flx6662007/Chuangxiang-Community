<script setup>
defineProps({
  variant: { type: String, required: true },
})
</script>

<template>
  <div class="editorial-hero-visual" :class="`is-${variant}`" aria-hidden="true">
    <svg v-if="variant === 'competition'" viewBox="0 0 560 360" fill="none" focusable="false">
      <path class="visual-faint" d="M24 44H536M24 180H536M24 316H536" />
      <path class="visual-line" d="M76 76H174V126H278V180H392V180H494M76 126H174M76 234H174V234H278V180M76 284H174V234" />
      <path class="visual-line visual-dash" d="M278 126V72H392M392 72H494" />
      <circle class="visual-node" cx="76" cy="76" r="5" />
      <circle class="visual-node" cx="76" cy="126" r="5" />
      <circle class="visual-node" cx="76" cy="234" r="5" />
      <circle class="visual-node" cx="76" cy="284" r="5" />
      <circle class="visual-node visual-node-strong" cx="278" cy="180" r="7" />
      <circle class="visual-node visual-node-strong" cx="494" cy="180" r="7" />
    </svg>

    <svg v-else-if="variant === 'research'" viewBox="0 0 560 360" fill="none" focusable="false">
      <path class="visual-faint" d="M28 302C156 292 215 236 316 197S470 117 548 44M12 326C160 317 237 257 338 215S478 139 558 72" />
      <path class="visual-line" d="M16 258C138 251 196 206 284 166S442 89 540 35M30 211C154 208 210 169 295 129S436 66 524 20" />
      <path class="visual-line visual-dash" d="M42 166C147 161 212 124 286 92S421 31 484 18" />
      <circle class="visual-ring" cx="284" cy="166" r="42" />
      <circle class="visual-ring" cx="284" cy="166" r="70" />
      <circle class="visual-node visual-node-strong" cx="284" cy="166" r="6" />
      <circle class="visual-node" cx="171" cy="221" r="4" />
      <circle class="visual-node" cx="412" cy="103" r="4" />
    </svg>

    <svg v-else viewBox="0 0 560 360" fill="none" focusable="false">
      <path class="visual-line" d="M112 178L276 78L440 178L276 278L112 178ZM112 178H440M276 78V278" />
      <path class="visual-faint" d="M112 106A72 72 0 1 0 112 250A72 72 0 1 0 112 106ZM440 106A72 72 0 1 0 440 250A72 72 0 1 0 440 106Z" />
      <circle class="visual-ring" cx="276" cy="178" r="116" />
      <circle class="visual-node" cx="112" cy="178" r="8" />
      <circle class="visual-node" cx="276" cy="78" r="8" />
      <circle class="visual-node" cx="440" cy="178" r="8" />
      <circle class="visual-node" cx="276" cy="278" r="8" />
      <circle class="visual-node visual-node-strong" cx="276" cy="178" r="12" />
    </svg>
  </div>
</template>

<style scoped>
.editorial-hero-visual {
  position: absolute;
  top: 46px;
  right: 0;
  width: min(44vw, 560px);
  max-width: 46%;
  color: var(--text-secondary, #7a9dc3);
  opacity: .52;
  pointer-events: none;
  z-index: 0;
}
.editorial-hero-visual svg { display: block; width: 100%; height: auto; overflow: visible; }
.visual-line, .visual-faint, .visual-ring { stroke: currentColor; stroke-width: 1; vector-effect: non-scaling-stroke; }
.visual-line { opacity: .58; }
.visual-faint { opacity: .22; }
.visual-ring { opacity: .25; }
.visual-dash { stroke-dasharray: 3 9; opacity: .35; }
.visual-node { fill: var(--illustration, #83a9d3); opacity: .62; }
.visual-node-strong { fill: var(--illustration-soft, #a8c5e6); opacity: .86; }
.is-research { color: var(--text-secondary, #8aaac9); opacity: .45; }
.is-team { color: var(--text-secondary, #87a9c6); opacity: .4; }

@media (prefers-reduced-motion: no-preference) {
  .editorial-hero-visual { animation: visual-enter var(--motion-enter) var(--motion-ease-out) both; }
  .is-research svg, .is-team svg { animation: visual-breathe 12s ease-in-out 1s infinite alternate; }
}
@keyframes visual-enter { from { opacity: 0; transform: translateY(8px); } }
@keyframes visual-breathe { to { transform: translateY(-5px); } }
@media (max-width: 900px) { .editorial-hero-visual { display: none; } }
</style>
