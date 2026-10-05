<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { formatUpdatedAt, safeExternalUrl } from '../utils/competition'
import { getResource } from '../services/resources'
import { resourceIcon } from '../utils/library'

const route = useRoute()
const item = ref(null)
const loading = ref(true)
const error = ref('')
let requestNumber = 0
let controller

const sourceUrl = computed(() => safeExternalUrl(item.value?.source_url))

async function load() {
  const request = ++requestNumber
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  item.value = null
  try {
    const data = await getResource(route.params.id, {}, controller.signal)
    if (request === requestNumber) item.value = data
  } catch (err) {
    if (request !== requestNumber || err.code === 'ERR_CANCELED') return
    if (err.response?.status === 404) return
    error.value = '暂时无法加载资源详情，请稍后重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => { requestNumber++; controller?.abort() })
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
      <p>请返回资源列表查找其他资料。</p>
      <RouterLink class="action-button secondary" :to="{ name: 'resources', query: route.query }">返回资源列表</RouterLink>
    </div>
    <template v-else>
      <header class="detail-hero">
        <span class="detail-emblem"><AppIcon :name="resourceIcon(item.category)" :size="36" /></span>
        <div class="detail-hero-copy">
          <p class="editorial-meta">资源中心 · {{ item.facts?.kind || item.category?.name || '学习资料' }}</p>
          <h2 id="resource-detail-title" class="resource-detail-title">{{ item.title }}</h2>
          <div class="tag-row">
            <span v-if="item.facts?.difficulty" class="tag">{{ item.facts.difficulty }}</span>
            <span v-if="item.facts?.language" class="tag neutral">{{ item.facts.language }}</span>
            <span v-if="item.facts?.access" class="tag neutral">{{ item.facts.access }}</span>
            <span v-for="direction in item.directions" :key="direction.code" class="tag">{{ direction.name }}</span>
            <span v-for="tag in item.tags" :key="tag.code" class="tag neutral">{{ tag.name }}</span>
          </div>
        </div>
        <a v-if="sourceUrl" class="action-button detail-hero-action" :href="sourceUrl" target="_blank" rel="noopener noreferrer">打开学习资料 ↗</a>
      </header>

      <div class="detail-layout">
        <div class="detail-main">
          <el-card class="detail-section" shadow="never">
            <h2>资源介绍</h2>
            <p class="preserve-lines">{{ item.content || item.description }}</p>
            <dl class="detail-facts resource-learning-facts">
              <div v-if="item.facts?.audience"><dt>适合谁</dt><dd>{{ item.facts.audience }}</dd></div>
              <div v-if="item.facts?.scope"><dt>适用范围</dt><dd>{{ item.facts.scope }}</dd></div>
              <div v-if="item.facts?.prerequisites"><dt>基础要求</dt><dd>{{ item.facts.prerequisites }}</dd></div>
              <div v-if="item.facts?.learning_path"><dt>怎么学</dt><dd>{{ item.facts.learning_path }}</dd></div>
            </dl>
          </el-card>
        </div>
        <aside class="detail-sidebar">
          <el-card class="detail-section" shadow="never">
            <h2>资源信息</h2>
            <dl class="detail-facts">
              <div><dt>资源类型</dt><dd>{{ item.facts?.kind || item.category?.name || '学习资料' }}</dd></div>
              <div v-if="item.directions?.length"><dt>方向</dt><dd>{{ item.directions.map(value => value.name).join('、') }}</dd></div>
              <div v-if="item.provider"><dt>来源</dt><dd>{{ item.provider }}</dd></div>
              <div><dt>整理时间</dt><dd>{{ formatUpdatedAt(item.updated_at) }}</dd></div>
            </dl>
            <a
              v-if="sourceUrl"
              class="action-button resource-source-link"
              :href="sourceUrl"
              target="_blank"
              rel="noopener noreferrer"
            >查看原文 ↗</a>
            <p v-else class="muted">暂无可访问的原文链接。</p>
            <template v-if="item.catalogs?.length">
              <h3>关联赛事目录</h3>
              <ul class="source-list"><li v-for="catalog in item.catalogs" :key="catalog.code"><RouterLink :to="{ name: 'catalog-detail', params: { code: catalog.code } }">{{ catalog.name }}</RouterLink></li></ul>
            </template>
          </el-card>
        </aside>
      </div>
    </template>
  </section>
</template>
