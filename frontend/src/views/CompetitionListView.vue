<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  listCompetitions,
  listCompetitionCategories,
} from '../api/competitions'
import CompetitionCard from '../components/CompetitionCard.vue'
import AppIcon from '../components/AppIcon.vue'

const route = useRoute()
const router = useRouter()
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
    const data = await listCompetitions(
      {
        page: page.value,
        page_size: pageSize,
        search: search.value || undefined,
        category: category.value || undefined,
      },
      controller.signal,
    )
    if (request !== requestNumber) return
    if (
      !Array.isArray(data.results) ||
      !Number.isInteger(data.count) ||
      data.count < 0
    )
      throw new Error('Invalid response')
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
    query: {
      ...(search.value ? { search: search.value } : {}),
      ...(category.value ? { category: category.value } : {}),
      ...(next > 1 ? { page: next } : {}),
    },
  })
}

function submitSearch() {
  const nextSearch = searchInput.value.trim()
  if (nextSearch === search.value && page.value === 1) return load()
  router.push({
    name: 'competitions',
    query: {
      ...(nextSearch ? { search: nextSearch } : {}),
      ...(category.value ? { category: category.value } : {}),
    },
  })
}

watch(
  () => [page.value, search.value, category.value],
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
    query: {
      ...(search.value ? { search: search.value } : {}),
      ...(value ? { category: value } : {}),
    },
  })
}
onMounted(loadCategories)
onBeforeUnmount(() => {
  requestNumber++
  controller?.abort()
})
</script>

<template>
  <section class="competition-page" aria-labelledby="competition-title">
    <header class="page-heading">
      <span class="section-kicker">COMPETITION CENTER</span>
      <h1 id="competition-title">赛事中心</h1>
      <p>汇聚赛事信息，发现值得投入的方向。</p>
    </header>
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
        placeholder="搜索赛事名称、关键词、主办单位…"
      />
      <button class="action-button" type="submit">搜索</button>
    </form>
    <div class="category-tabs" aria-label="赛事分类">
      <button :class="{ selected: !category }" @click="selectCategory('')">
        全部分类</button
      ><button
        v-for="option in categories"
        :key="option.code"
        :class="{ selected: category === option.code }"
        @click="selectCategory(option.code)"
      >
        {{ option.name }}</button
      ><span v-if="categoryError" role="alert"
        >{{ categoryError }}
        <button class="text-button" @click="loadCategories">重试</button></span
      >
    </div>
    <div class="competition-content">
      <aside class="competition-sidebar" aria-label="赛事导航">
        <div class="sidebar-title">EXPLORE / 赛事导航</div>
        <RouterLink class="sidebar-active" :to="{ name: 'competitions' }"
          ><AppIcon name="trophy" :size="19" />全部赛事</RouterLink
        >
        <div class="sidebar-note">
          <h2>找到你的参赛方向</h2>
          <p>用赛事名称、感兴趣的关键词或主办单位搜索。</p>
        </div>
        <div class="sidebar-illustration">
          <AppIcon name="book" :size="42" />
          <p>每一次探索<br />都是新的开始</p>
        </div>
        <div class="sidebar-note">
          <h2>查阅提示</h2>
          <p>报名要求与截止时间以赛事官方通知为准。</p>
        </div>
      </aside>
      <div class="competition-results">
        <div class="list-summary">
          <span
            >{{ search ? `“${search}” 的搜索结果` : '全部赛事' }} ·
            按最新发布排序</span
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
          <h2>{{ search ? '没有找到相关赛事' : '暂时没有公开赛事' }}</h2>
          <p>
            {{
              search
                ? '换个关键词试试，或清空搜索查看全部赛事。'
                : '新赛事发布后会显示在这里。'
            }}
          </p>
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
