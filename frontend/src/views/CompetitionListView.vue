<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listCompetitions } from '../api/competitions'
import CompetitionCard from '../components/CompetitionCard.vue'

const route = useRoute()
const router = useRouter()
const items = ref([])
const count = ref(0)
const loading = ref(false)
const error = ref('')
const searchInput = ref('')
const pageSize = 20
const search = computed(() => typeof route.query.search === 'string' ? route.query.search.trim() : '')
const page = computed(() => {
  const value = Number(route.query.page)
  return Number.isSafeInteger(value) && value > 0 ? value : 1
})
let requestNumber = 0
let controller

async function load() {
  const request = ++requestNumber
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  items.value = []
  count.value = 0
  try {
    const data = await listCompetitions({ page: page.value, page_size: pageSize, search: search.value || undefined }, controller.signal)
    if (request !== requestNumber) return
    if (!Array.isArray(data.results) || !Number.isInteger(data.count) || data.count < 0) throw new Error('Invalid response')
    items.value = data.results
    count.value = data.count
  } catch (err) {
    if (request !== requestNumber || err.code === 'ERR_CANCELED') return
    error.value = err.response?.status === 404 ? '这一页不存在，请返回第一页。' : '暂时无法加载赛事，请稍后重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

function changePage(next) {
  router.push({ name: 'competitions', query: { ...(search.value ? { search: search.value } : {}), ...(next > 1 ? { page: next } : {}) } })
}

function submitSearch() {
  const nextSearch = searchInput.value.trim()
  if (nextSearch === search.value && page.value === 1) return load()
  router.push({ name: 'competitions', query: nextSearch ? { search: nextSearch } : {} })
}

watch(() => [page.value, search.value], () => {
  searchInput.value = search.value
  load()
}, { immediate: true })
onBeforeUnmount(() => { requestNumber++; controller?.abort() })
</script>

<template>
  <section class="competition-page" aria-labelledby="competition-title">
    <header class="page-heading">
      <h1 id="competition-title">赛事列表</h1>
      <p>查看赛事安排与报名要求，具体规则以赛事官方通知为准。</p>
    </header>
    <form class="search-bar" role="search" @submit.prevent="submitSearch">
      <label for="competition-search">搜索赛事</label>
      <input id="competition-search" v-model="searchInput" type="search" maxlength="200" placeholder="输入赛事名称或关键词" />
      <button class="action-button" type="submit">搜索</button>
    </form>
    <div class="list-summary"><span>按最新发布排序</span><span v-if="!loading && !error">共 {{ count }} 项赛事</span></div>
    <div v-if="loading" class="state-panel" role="status" aria-live="polite">正在加载赛事…</div>
    <div v-else-if="error" class="state-panel" role="alert">
      <p>{{ error }}</p>
      <button class="action-button secondary" @click="load">重新加载</button>
      <button v-if="page > 1" class="action-button secondary" @click="changePage(1)">返回第一页</button>
    </div>
    <div v-else-if="!items.length" class="state-panel" role="status">
      <h2>{{ search ? '没有找到相关赛事' : '暂时没有公开赛事' }}</h2>
      <p>{{ search ? '换个关键词试试，或清空搜索查看全部赛事。' : '新赛事发布后会显示在这里。' }}</p>
    </div>
    <div v-else class="competition-grid">
      <CompetitionCard v-for="item in items" :key="item.id" :competition="item" :detail-query="route.query" />
    </div>
    <el-pagination
      v-if="!loading && !error && count > pageSize"
      class="competition-pagination"
      :current-page="page"
      :page-size="pageSize"
      :total="count"
      layout="prev, pager, next"
      prev-text="上一页"
      next-text="下一页"
      background
      aria-label="赛事列表分页"
      @update:current-page="changePage"
    />
  </section>
</template>
