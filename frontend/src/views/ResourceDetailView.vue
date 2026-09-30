<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { formatDate, safeExternalUrl } from '../utils/competition'
import { getResource, resourceCategories, resourceDirections } from '../services/resources'

const route = useRoute()
const item = ref(null)
const loading = ref(true)
const error = ref('')
let requestNumber = 0

const category = computed(() => resourceCategories.find((option) => option.value === item.value?.category))
const direction = computed(() => resourceDirections.find((option) => option.value === item.value?.direction))
const sourceUrl = computed(() => safeExternalUrl(item.value?.url))

async function load() {
  const request = ++requestNumber
  loading.value = true
  error.value = ''
  item.value = null
  try {
    const data = await getResource(route.params.id)
    if (request === requestNumber) item.value = data
  } catch {
    if (request === requestNumber) error.value = '暂时无法加载资源详情，请稍后重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => { requestNumber++ })
</script>

<template>
  <section class="detail-page resource-detail" aria-labelledby="resource-detail-title">
    <RouterLink class="back-link" :to="{ name: 'resources', query: route.query }">
      ← 资源中心<span>/</span>返回资源列表
    </RouterLink>

    <div v-if="loading" class="state-panel compact-state" role="status">正在加载资源详情…</div>
    <div v-else-if="error" class="state-panel compact-state" role="alert">
      <p>{{ error }}</p>
      <button class="action-button secondary" type="button" @click="load">重新加载</button>
    </div>
    <div v-else-if="!item" class="state-panel compact-state">
      <h2 id="resource-detail-title">没有找到这条资源</h2>
      <p>链接可能已失效，请返回资源列表继续查找。</p>
      <RouterLink class="action-button secondary" :to="{ name: 'resources', query: route.query }">返回资源列表</RouterLink>
    </div>
    <template v-else>
      <header class="detail-hero">
        <span class="detail-emblem"><AppIcon :name="category?.icon || 'book'" :size="36" /></span>
        <div class="detail-hero-copy">
          <p class="editorial-meta">资源中心 · {{ category?.label }}</p>
          <h2 id="resource-detail-title" class="resource-detail-title">{{ item.title }}</h2>
          <div class="tag-row">
            <span class="tag">{{ direction?.label }}</span>
            <span v-for="tag in item.tags" :key="tag" class="tag neutral">{{ tag }}</span>
          </div>
          <p>{{ item.description }}</p>
        </div>
      </header>

      <div class="detail-layout">
        <div class="detail-main">
          <el-card class="detail-section" shadow="never">
            <h2>资源介绍</h2>
            <p class="preserve-lines">{{ item.content || item.description }}</p>
            <p class="notice-text">这是前端 Mock 示例内容；具体赛事、科研或学习安排请以相应原文为准。</p>
          </el-card>
        </div>
        <aside class="detail-sidebar">
          <el-card class="detail-section" shadow="never">
            <h2>资源信息</h2>
            <dl class="detail-facts">
              <div><dt>资源类型</dt><dd>{{ category?.label }}</dd></div>
              <div><dt>方向</dt><dd>{{ direction?.label }}</dd></div>
              <div><dt>来源</dt><dd>{{ item.source }}</dd></div>
              <div><dt>整理时间</dt><dd>{{ formatDate(item.updatedAt) }}</dd></div>
            </dl>
            <a
              v-if="sourceUrl"
              class="action-button resource-source-link"
              :href="sourceUrl"
              target="_blank"
              rel="noopener noreferrer"
            >查看原文 ↗</a>
            <p v-else class="muted">此示例暂无可访问的原文链接。</p>
          </el-card>
        </aside>
      </div>
    </template>
  </section>
</template>
