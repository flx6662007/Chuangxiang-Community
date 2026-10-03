<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import ResourceCard from '../components/ResourceCard.vue'
import {
  listResources,
  normalizeResourceCategory,
  normalizeResourceDirection,
  resourceCategories,
  resourceDirections,
} from '../services/resources'

const route = useRoute()
const router = useRouter()
const items = ref([])
const count = ref(0)
const loading = ref(true)
const error = ref('')
const searchInput = ref('')
let requestNumber = 0

const search = computed(() =>
  typeof route.query.search === 'string' ? route.query.search.trim().slice(0, 200) : '',
)
const direction = computed(() => normalizeResourceDirection(route.query.direction))
const category = computed(() => normalizeResourceCategory(route.query.category))
const activeFilters = computed(() => Boolean(search.value || direction.value || category.value))
const currentQuery = computed(() => ({
  ...(search.value ? { search: search.value } : {}),
  ...(direction.value ? { direction: direction.value } : {}),
  ...(category.value ? { category: category.value } : {}),
}))
const featuredItems = computed(() => items.value.filter((item) => item.featured))

async function load() {
  const request = ++requestNumber
  loading.value = true
  error.value = ''
  try {
    const data = await listResources({
      search: search.value,
      direction: direction.value,
      category: category.value,
    })
    if (request === requestNumber) {
      items.value = data.results
      count.value = data.count
    }
  } catch {
    if (request === requestNumber) {
      items.value = []
      count.value = 0
      error.value = '资源暂时无法加载，请稍后重试。'
    }
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

function navigate({ nextSearch = search.value, nextDirection = direction.value, nextCategory = category.value, hash = '' } = {}) {
  router.push({
    name: 'resources',
    query: {
      ...(nextSearch ? { search: nextSearch } : {}),
      ...(nextDirection ? { direction: nextDirection } : {}),
      ...(nextCategory ? { category: nextCategory } : {}),
    },
    hash,
  })
}

function submitSearch() {
  navigate({ nextSearch: searchInput.value.trim().slice(0, 200) })
}

function clearSearch() {
  searchInput.value = ''
  navigate({ nextSearch: '' })
}

function clearFilters() {
  searchInput.value = ''
  navigate({ nextSearch: '', nextDirection: '', nextCategory: '' })
}

watch(search, (value) => { searchInput.value = value }, { immediate: true })
watch(() => [search.value, direction.value, category.value], load, { immediate: true })
onBeforeUnmount(() => { requestNumber++ })
</script>

<template>
  <section class="resource-page" aria-labelledby="resource-title">
    <div class="section-heading">
      <div>
        <h2 id="resource-title">资源中心</h2>
      </div>

    </div>
    <p class="editorial-intro">
      按方向和资源类型查找竞赛、科研与技能学习资料。未来由管理员维护；当前先展示前端示例清单。
    </p>
    <form class="search-bar" role="search" @submit.prevent="submitSearch">
      <AppIcon name="search" :size="19" />
      <label class="sr-only" for="resource-search">搜索资源标题、简介和标签</label>
      <input
        id="resource-search"
        v-model="searchInput"
        type="search"
        maxlength="200"
        placeholder="搜索资源标题、简介或标签…"
      />
      <button class="action-button" type="submit">搜索</button>
      <button v-if="search || searchInput" class="text-button" type="button" @click="clearSearch">
        清空搜索
      </button>
    </form>

    <div class="category-tabs" role="group" aria-label="资源方向筛选">
      <button
        v-for="option in resourceDirections"
        :key="option.value || 'all'"
        type="button"
        :class="{ selected: direction === option.value }"
        :aria-pressed="direction === option.value"
        @click="navigate({ nextDirection: option.value })"
      >{{ option.label }}</button>
    </div>

    <section class="resource-category-section" aria-labelledby="resource-categories-title">
      <div class="section-heading resource-category-heading">
        <div>
          <h2 id="resource-categories-title">按资源类型查找</h2>
        </div>
        <button
          type="button"
          class="text-button"
          :aria-pressed="!category"
          @click="navigate({ nextCategory: '', hash: '#resource-list' })"
        >查看全部类型</button>
      </div>
      <div class="resource-category-grid" role="group" aria-label="资源类型筛选">
        <button
          v-for="option in resourceCategories"
          :key="option.value"
          type="button"
          class="resource-category-card"
          :class="{ selected: category === option.value }"
          :aria-pressed="category === option.value"
          @click="navigate({ nextCategory: option.value, hash: '#resource-list' })"
        >
          <span class="resource-category-icon"><AppIcon :name="option.icon" :size="24" /></span>
          <strong>{{ option.label }}</strong>
          <span>{{ option.description }}</span>
        </button>
      </div>
    </section>

    <p class="notice-text resource-notice">
      当前为前端 Mock 示例资源，尚未接入管理员审核与发布。示例清单不是当期报名通知，具体要求请以相应原文为准。
    </p>

    <section v-if="!activeFilters && !loading && !error && featuredItems.length" class="resource-featured" aria-labelledby="resource-featured-title">
      <div class="section-heading">
        <div>
          <h2 id="resource-featured-title">先看这些示例</h2>
        </div>
      </div>
      <div class="editorial-grid">
        <ResourceCard v-for="item in featuredItems" :key="item.id" :item="item" :detail-query="currentQuery" id-prefix="featured-resource" />
      </div>
    </section>

    <section id="resource-list" class="resource-results" aria-labelledby="resource-list-title">
      <div class="section-heading">
        <div>
          <h2 id="resource-list-title">资源列表</h2>
        </div>
      </div>
      <div class="list-summary" role="status" aria-live="polite">
        <span>{{ activeFilters ? '当前筛选结果' : '全部示例资源' }}</span>
        <span v-if="!loading && !error">共 <strong>{{ count }}</strong> 条资源</span>
      </div>
      <div v-if="loading" class="state-panel compact-state" role="status">正在加载资源…</div>
      <div v-else-if="error" class="state-panel compact-state" role="alert">
        <p>{{ error }}</p>
        <button class="action-button secondary" type="button" @click="load">重新加载</button>
      </div>
      <div v-else-if="!items.length" class="state-panel compact-state">
        <h3>没有找到匹配资源</h3>
        <p>试试其他关键词，或调整方向与资源类型。</p>
        <button class="action-button secondary" type="button" @click="clearFilters">清空筛选</button>
      </div>
      <div v-else class="editorial-grid">
        <ResourceCard v-for="item in items" :key="item.id" :item="item" :detail-query="currentQuery" />
      </div>
    </section>
  </section>
</template>
