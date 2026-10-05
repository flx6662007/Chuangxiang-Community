<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import ResourceCard from '../components/ResourceCard.vue'
import { listResources, listResourceTaxonomies } from '../services/resources'
import { libraryPage, libraryQuery, libraryText, resourceIcon } from '../utils/library'

const route = useRoute(), router = useRouter()
const items = ref([]), count = ref(0), loading = ref(true), error = ref(''), searchInput = ref('')
const taxonomies = ref({ categories: [], directions: [] }), taxonomyError = ref('')
const pageSize = 20
const search = computed(() => libraryText(route.query.search))
const direction = computed(() => libraryText(route.query.direction))
const category = computed(() => libraryText(route.query.category))
const catalogCode = computed(() => libraryText(route.query.catalog_code))
const page = computed(() => libraryPage(route.query.page))
const currentQuery = computed(() => libraryQuery({
  search: search.value, direction: direction.value, category: category.value,
  catalog_code: catalogCode.value, page: page.value > 1 ? page.value : undefined,
}))
let requestNumber = 0, taxonomyRequest = 0, controller, taxonomyController

async function load() {
  const request = ++requestNumber
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  items.value = []
  count.value = 0
  try {
    const data = await listResources({ ...currentQuery.value, page: page.value, page_size: pageSize }, controller.signal)
    if (request !== requestNumber) return
    items.value = data.results
    count.value = data.count
  } catch (err) {
    if (request !== requestNumber || err.code === 'ERR_CANCELED') return
    error.value = err.response?.status === 404 ? '这一页不存在，请返回第一页。' : '资源暂时无法加载，请稍后重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}
async function loadTaxonomies() {
  const request = ++taxonomyRequest
  taxonomyController?.abort()
  taxonomyController = new AbortController()
  taxonomies.value = { categories: [], directions: [] }
  taxonomyError.value = ''
  try {
    const data = await listResourceTaxonomies({}, taxonomyController.signal)
    if (request === taxonomyRequest) taxonomies.value = data
  } catch (err) {
    if (request === taxonomyRequest && err.code !== 'ERR_CANCELED') taxonomyError.value = '分类暂时无法加载；仍可搜索资源。'
  }
}
function navigate(changes = {}) {
  router.push({ name: 'resources', query: libraryQuery({ ...currentQuery.value, page: undefined, ...changes }) })
}
function submitSearch() {
  const next = libraryText(searchInput.value)
  if (next === search.value && page.value === 1) load()
  else navigate({ search: next })
}
function clearFilters() {
  searchInput.value = ''
  navigate({ search: '', direction: '', category: '', catalog_code: '' })
}
watch(search, value => { searchInput.value = value }, { immediate: true })
watch(() => [search.value, direction.value, category.value, catalogCode.value, page.value], load, { immediate: true })
onMounted(loadTaxonomies)
onBeforeUnmount(() => { requestNumber++; taxonomyRequest++; controller?.abort(); taxonomyController?.abort() })
</script>

<template>
  <section class="resource-page" aria-labelledby="resource-title">
    <div class="section-heading">
      <div><h2 id="resource-title">资源中心</h2></div>
    </div>
    <p v-if="catalogCode" class="notice-text">仅查看目录 {{ catalogCode }} 的学习资料。 <RouterLink :to="{ name: 'catalog-detail', params: { code: catalogCode } }">返回赛事目录详情 →</RouterLink></p>
    <form class="search-bar" role="search" @submit.prevent="submitSearch">
      <AppIcon name="search" :size="19" /><label class="sr-only" for="resource-search">搜索资源标题、简介和来源</label>
      <input id="resource-search" v-model="searchInput" type="search" maxlength="200" placeholder="搜索赛题、教程、工具或来源…" />
      <button class="action-button" type="submit">搜索</button>
    </form>
    <div v-if="taxonomies.directions?.length || direction" class="category-tabs" role="group" aria-label="资源方向筛选">
      <button type="button" :class="{ selected: !direction }" @click="navigate({ direction: '' })">全部方向</button>
      <button v-for="option in taxonomies.directions" :key="option.code" type="button" :class="{ selected: direction === option.code }" :aria-pressed="direction === option.code" @click="navigate({ direction: option.code })">{{ option.name }}</button>
    </div>
    <section v-if="taxonomies.categories?.length > 1 || taxonomies.has_unclassified || category" class="resource-category-section" aria-labelledby="resource-categories-title">
      <div class="section-heading resource-category-heading"><h2 id="resource-categories-title">按资源类型查找</h2><button class="text-button" type="button" @click="navigate({ category: '' })">查看全部类型</button></div>
      <div class="resource-category-grid" role="group" aria-label="资源类型筛选">
        <button v-for="option in taxonomies.categories" :key="option.code" type="button" class="resource-category-card" :class="{ selected: category === option.code }" :aria-pressed="category === option.code" @click="navigate({ category: option.code })">
          <span class="resource-category-icon"><AppIcon :name="resourceIcon(option)" :size="24" /></span><strong>{{ option.name }}</strong>
        </button>
        <button v-if="taxonomies.has_unclassified" type="button" class="resource-category-card" :class="{ selected: category === 'unclassified' }" @click="navigate({ category: 'unclassified' })"><span class="resource-category-icon"><AppIcon name="book" :size="24" /></span><strong>待分类资料</strong></button>
      </div>
    </section>
    <p v-if="taxonomyError" class="notice-text" role="alert">{{ taxonomyError }} <button class="text-button" @click="loadTaxonomies">重试</button></p>
    <section class="resource-results" aria-labelledby="resource-list-title">
      <div class="section-heading"><div><h2 id="resource-list-title">资源列表</h2></div></div>
      <div class="list-summary" role="status" aria-live="polite"><span>学习资料</span><span v-if="!loading && !error">共 <strong>{{ count }}</strong> 条资源</span></div>
      <div v-if="loading" class="state-panel compact-state" role="status">正在加载资源…</div>
      <div v-else-if="error" class="state-panel compact-state" role="alert">
        <p>{{ error }}</p><button class="action-button secondary" type="button" @click="load">重新加载</button>
        <button v-if="page > 1" class="text-button" @click="navigate({ page: undefined })">返回第一页</button>
      </div>
      <div v-else-if="!items.length" class="state-panel compact-state">
        <h3>暂无匹配的资源</h3><p>可调整筛选条件，或换个关键词试试。</p><button class="action-button secondary" type="button" @click="clearFilters">清空筛选</button>
      </div>
      <div v-else class="editorial-grid"><ResourceCard v-for="item in items" :key="item.id" :item="item" :detail-query="currentQuery" /></div>
      <el-pagination v-if="!loading && !error && count > pageSize" class="competition-pagination" :current-page="page" :page-size="pageSize" :total="count" layout="prev, pager, next" prev-text="上一页" next-text="下一页" background aria-label="资源分页" @update:current-page="value => navigate({ page: value })" />
    </section>
  </section>
</template>
