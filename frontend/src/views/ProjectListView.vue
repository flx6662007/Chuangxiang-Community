<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listResearch } from '../api/editorial'
import { libraryPage, libraryQuery } from '../utils/library'
import AppIcon from '../components/AppIcon.vue'
import ProjectOpportunityCard from '../components/ProjectOpportunityCard.vue'

const route = useRoute()
const router = useRouter()
const searchInput = ref('')
const items = ref([]), count = ref(0), loading = ref(true), error = ref('')
const pageSize = 12
const page = computed(() => libraryPage(route.query.page))
let requestNumber = 0, controller
const search = computed(() =>
  typeof route.query.search === 'string'
    ? route.query.search.trim().slice(0, 200)
    : '',
)
async function load() {
  const request = ++requestNumber
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  items.value = []
  count.value = 0
  try {
    const data = await listResearch({ search: search.value, page: page.value, page_size: pageSize }, controller.signal)
    if (request !== requestNumber) return
    items.value = data.results
    count.value = data.count
  } catch (err) {
    if (request !== requestNumber || err.code === 'ERR_CANCELED') return
    error.value = err.response?.status === 404 ? '这一页不存在，请返回第一页。' : '科研线索暂时无法加载，请重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}
function navigate(value = 1) {
  router.push({ name: 'research-projects', query: libraryQuery({ search: search.value, page: value > 1 ? value : undefined }) })
}
function submitSearch() {
  const value = searchInput.value.trim().slice(0, 200)
  if (value === search.value && page.value === 1) { load(); return }
  router.push({
    name: 'research-projects',
    query: value ? { search: value } : {},
  })
}
function clearSearch() {
  searchInput.value = ''
  router.push({ name: 'research-projects' })
}
watch(
  search,
  (value) => {
    searchInput.value = value
  },
  { immediate: true },
)
watch(() => [search.value, page.value], load, { immediate: true })
onBeforeUnmount(() => { requestNumber++; controller?.abort() })
</script>

<template>
  <section class="project-page" aria-labelledby="projects-title">
    <div v-reveal class="project-intro">
      <h2 id="projects-title">把好奇心带进实验室。</h2>
      <p>阅读真实来源，找到与你的兴趣相交的研究方向。</p>
    </div>
    <form class="search-bar" role="search" @submit.prevent="submitSearch">
      <AppIcon name="search" :size="19" />
      <label class="sr-only" for="project-search">搜索科研线索</label>
      <input
        id="project-search"
        v-model="searchInput"
        type="search"
        maxlength="200"
        placeholder="搜索课题组、单位、研究方向或参与要求…"
      />
      <button class="action-button" type="submit">搜索</button>
      <button
        v-if="search || searchInput"
        class="text-button"
        type="button"
        @click="clearSearch"
      >
        清空搜索
      </button>
    </form>
    <p class="notice-text">
      浏览实验室研究方向、招募记录与本科生参与方式。
    </p>
    <div class="list-summary" role="status" aria-live="polite">
      <span>{{
        search ? '“' + search + '” 的搜索结果' : '全部科研线索'
      }}</span>
      <span v-if="!loading && !error"
        >共 <strong>{{ count }}</strong> 条线索</span
      >
    </div>
    <div v-if="loading" class="state-panel compact-state" role="status">正在加载科研线索…</div>
    <div v-else-if="error" class="state-panel compact-state" role="alert">
      <p>{{ error }}</p><button class="action-button secondary" type="button" @click="load">重新加载</button>
      <button v-if="page > 1" class="text-button" type="button" @click="navigate()">返回第一页</button>
    </div>
    <div v-else-if="items.length" class="research-editorial-list">
      <ProjectOpportunityCard
        v-for="item in items"
        :key="item.id"
        :item="item"
      />
    </div>
    <div v-else class="state-panel compact-state">
      <h3>{{ search ? '没有找到匹配线索' : '官方线索整理中' }}</h3>
      <p>
        {{
          search
            ? '换个关键词试试，或清空搜索查看全部线索。'
            : '实验室与本科生科研参与信息将在这里展示。'
        }}
      </p>
      <button
        v-if="search"
        class="action-button secondary"
        @click="clearSearch"
      >
        清空搜索
      </button>
    </div>
    <el-pagination v-if="!loading && !error && count > pageSize" class="competition-pagination" :current-page="page" :page-size="pageSize" :total="count" layout="prev, pager, next" prev-text="上一页" next-text="下一页" background aria-label="科研线索分页" @update:current-page="navigate" />
  </section>
</template>
