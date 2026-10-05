<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  listCompetitions,
  listCompetitionCategories,
} from '../api/competitions'
import CompetitionCard from '../components/CompetitionCard.vue'
import CatalogCard from '../components/CatalogCard.vue'
import { listCatalogEntries } from '../api/catalog'
import { libraryQuery, paginatedLibrary } from '../utils/library'
import {
  competitionTimeOptions,
  normalizeTimeStatus,
  competitionListQuery,
} from '../utils/competition'
import AppIcon from '../components/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const view = computed(() => route.query.view === 'editions' || (!route.query.view && (route.query.category || route.query.time_status)) ? 'editions' : 'catalog')
const isCatalog = computed(() => view.value === 'catalog')
const grade = computed(() => ['A+', 'A', 'B', 'C'].includes(route.query.grade) ? route.query.grade : '')
const items = ref([])
const count = ref(0)
const loading = ref(false)
const error = ref('')
const searchInput = ref('')
const categories = ref([])
const categoryError = ref('')
const category = computed(() =>
  typeof route.query.category === 'string' ? route.query.category : '',
)
const pageSize = 20
const timeStatus = computed(() => normalizeTimeStatus(route.query.time_status))
const search = computed(() =>
  typeof route.query.search === 'string' ? route.query.search.trim() : '',
)
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
    const data = isCatalog.value ? await listCatalogEntries({
      page: page.value, page_size: pageSize, search: search.value || undefined, grade: grade.value || undefined,
    }, controller.signal) : await listCompetitions(
      {
        page: page.value,
        page_size: pageSize,
        time_status: timeStatus.value,
        search: search.value || undefined,
        category: category.value || undefined,
      },
      controller.signal,
    )
    if (request !== requestNumber) return
    paginatedLibrary(data)
    items.value = data.results
    count.value = data.count
  } catch (err) {
    if (request !== requestNumber || err.code === 'ERR_CANCELED') return
    error.value =
      err.response?.status === 404
        ? '这一页不存在，请返回第一页。'
        : '暂时无法加载赛事，请稍后重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

function changePage(next) {
  router.push({
    name: 'competitions',
    query: isCatalog.value ? libraryQuery({ view: 'catalog', search: search.value, grade: grade.value, page: next > 1 ? next : undefined }) : { view: 'editions', ...competitionListQuery({
      search: search.value,
      category: category.value,
      timeStatus: timeStatus.value,
      page: next,
    }) },
  })
}

function submitSearch() {
  const nextSearch = searchInput.value.trim()
  if (nextSearch === search.value && page.value === 1) return load()
  router.push({
    name: 'competitions',
    query: isCatalog.value ? libraryQuery({ view: 'catalog', search: nextSearch, grade: grade.value }) : { view: 'editions', ...competitionListQuery({
      search: nextSearch,
      category: category.value,
      timeStatus: timeStatus.value,
    }) },
  })
}

function selectTimeStatus(value) {
  router.push({
    name: 'competitions',
    query: { view: 'editions', ...competitionListQuery({
      search: search.value,
      category: category.value,
      timeStatus: value,
    }) },
  })
}

watch(
  () => [page.value, search.value, category.value, timeStatus.value, view.value, grade.value],
  () => {
    searchInput.value = search.value
    load()
  },
  { immediate: true },
)
async function loadCategories() {
  categoryError.value = ''
  try {
    categories.value = await listCompetitionCategories()
  } catch {
    categoryError.value = '分类选项暂时无法加载。'
  }
}
function selectCategory(value) {
  router.push({
    name: 'competitions',
    query: { view: 'editions', ...competitionListQuery({
      search: search.value,
      category: value,
      timeStatus: timeStatus.value,
    }) },
  })
}
function selectView(value) {
  router.push({ name: 'competitions', query: libraryQuery({ view: value, search: search.value }) })
}
function selectGrade(value) {
  router.push({ name: 'competitions', query: libraryQuery({ view: 'catalog', search: search.value, grade: value }) })
}
onMounted(loadCategories)
onBeforeUnmount(() => {
  requestNumber++
  controller?.abort()
})
</script>

<template>
  <section class="competition-page" aria-labelledby="competition-title">
    <div v-reveal class="competition-intro">
      <div>
        <h2 id="competition-title">探索赛事</h2>
      </div>
      <p>查找赛事、参赛要求与学习资料。</p>
    </div>
    <div class="category-tabs" role="group" aria-label="赛事视图">
      <button :class="{ selected: isCatalog }" :aria-pressed="isCatalog" @click="selectView('catalog')">赛事目录</button>
      <button :class="{ selected: !isCatalog }" :aria-pressed="!isCatalog" @click="selectView('editions')">届次通知</button>
    </div>
    <form class="search-bar" role="search" @submit.prevent="submitSearch">
      <AppIcon name="search" :size="19" /><label
        class="sr-only"
        for="competition-search"
        >搜索赛事</label
      >
      <input
        id="competition-search"
        v-model="searchInput"
        type="search"
        maxlength="200"
        :placeholder="isCatalog ? '搜索赛事名称或目录编号…' : '搜索赛事名称、关键词、主办单位…'"
      />
      <button class="action-button" type="submit">搜索</button>
    </form>
    <div v-if="isCatalog" class="competition-filters">
      <div class="filter-heading"><strong>按目录等级筛选</strong></div>
      <div class="category-tabs" role="group" aria-label="目录等级">
        <button :class="{ selected: !grade }" @click="selectGrade('')">全部等级</button>
        <button v-for="value in ['A+', 'A', 'B', 'C']" :key="value" :class="{ selected: grade === value }" @click="selectGrade(value)">{{ value }}</button>
      </div>
    </div>
    <div v-else class="competition-filters">
      <div class="filter-heading"><strong>按方向筛选</strong></div>
      <div class="category-tabs competition-category-tabs" aria-label="赛事分类">
        <button :class="{ selected: !category }" @click="selectCategory('')">
          全部分类
        </button>
        <button
          v-for="option in categories"
          :key="option.code"
          :class="{ selected: category === option.code }"
          @click="selectCategory(option.code)"
        >
          {{ option.name }}
        </button>
        <span v-if="categoryError" role="alert">
          {{ categoryError }}
          <button class="text-button" @click="loadCategories">重试</button>
        </span>
      </div>
      <div class="filter-heading"><strong>按时效筛选</strong></div>
      <div class="category-tabs competition-time-tabs" aria-label="赛事时效">
        <button
          v-for="option in competitionTimeOptions"
          :key="option.code"
          :class="{ selected: timeStatus === option.code }"
          :aria-pressed="timeStatus === option.code"
          @click="selectTimeStatus(option.code)"
        >
          {{ option.name }}
        </button>
      </div>
    </div>
    <div v-reveal class="competition-content">
      <div class="competition-results">
        <div class="list-summary">
          <span
            >{{
              isCatalog ? (search ? `“${search}” 的目录搜索结果` : '学校赛事目录') : search
                ? `“${search}” 的搜索结果`
                : competitionTimeOptions.find(
                    (option) => option.code === timeStatus,
                  )?.name + '赛事'
            }}
            · {{ isCatalog ? '按目录编号排序' : '按截止状态及来源发布日期排序' }}</span
          ><span v-if="!loading && !error"
            >共 <strong>{{ count }}</strong> 项赛事</span
          >
        </div>
        <div
          v-if="loading"
          class="state-panel"
          role="status"
          aria-live="polite"
        >
          正在加载赛事…
        </div>
        <div v-else-if="error" class="state-panel" role="alert">
          <p>{{ error }}</p>
          <button class="action-button secondary" @click="load">
            重新加载
          </button>
          <button
            v-if="page > 1"
            class="action-button secondary"
            @click="changePage(1)"
          >
            返回第一页
          </button>
        </div>
        <div v-else-if="!items.length" class="state-panel" role="status">
          <h2>{{ search ? '没有找到相关赛事' : '当前筛选下暂无赛事' }}</h2>
          <p>
            {{
              search
                ? '换个关键词试试，或调整分类和时效筛选。'
                : isCatalog ? '暂无匹配的目录记录，可调整关键词或等级。' : '可切换历史或全部查看已有记录，新赛事发布后会显示在这里。'
            }}
          </p>
        </div>
        <div v-else-if="isCatalog" class="competition-grid">
          <CatalogCard v-for="item in items" :key="item.code" :item="item" :detail-query="route.query" />
        </div>
        <div v-else class="competition-grid">
          <CompetitionCard
            v-for="item in items"
            :key="item.id"
            :competition="item"
            :detail-query="route.query"
          />
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
      </div>
    </div>
  </section>
</template>
