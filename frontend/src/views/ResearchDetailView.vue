<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getResearch } from '../api/editorial'
import ProjectOpportunityCard from '../components/ProjectOpportunityCard.vue'

const route = useRoute()
const item = ref(null)
const loading = ref(true)
const error = ref('')
let controller

async function load(id) {
  controller?.abort()
  controller = new AbortController()
  const pending = controller
  item.value = null
  error.value = ''
  loading.value = true
  try {
    const result = await getResearch(id, pending.signal)
    if (!pending.signal.aborted) item.value = result
  } catch (caught) {
    if (!pending.signal.aborted && caught.code !== 'ERR_CANCELED') error.value = caught.response?.status === 404 ? '没有找到这条科研资料。' : '科研资料暂时无法加载。'
  } finally {
    if (!pending.signal.aborted) loading.value = false
  }
}

watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="project-page" aria-label="科研资料详情">
    <RouterLink class="back-link" :to="{ name: 'research-projects' }">返回科研资料</RouterLink>
    <div v-if="loading" class="state-panel compact-state" role="status">正在加载科研资料…</div>
    <div v-else-if="error" class="state-panel compact-state" role="alert">{{ error }}</div>
    <ProjectOpportunityCard v-else-if="item" :item="item" />
  </section>
</template>
