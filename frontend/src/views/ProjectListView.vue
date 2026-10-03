<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { laboratories } from '../data/editorial'
import AppIcon from '../components/AppIcon.vue'
import ProjectOpportunityCard from '../components/ProjectOpportunityCard.vue'

const route = useRoute()
const router = useRouter()
const searchInput = ref('')
const search = computed(() =>
  typeof route.query.search === 'string'
    ? route.query.search.trim().slice(0, 200)
    : '',
)
const items = computed(() => {
  const words = search.value.toLocaleLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return laboratories
  return laboratories.filter((item) => {
    const text = [
      item.title,
      item.unit,
      item.direction,
      item.summary,
      item.participation,
      item.evidenceNote,
    ]
      .filter((value) => typeof value === 'string')
      .join(' ')
      .toLocaleLowerCase()
    return words.every((word) => text.includes(word))
  })
})
function submitSearch() {
  const value = searchInput.value.trim().slice(0, 200)
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
      收录内容包含历史招募和长期参与说明，不代表当前已有项目名额。请通过官方页面确认具体课题、参与条件与时间安排。
    </p>
    <div class="list-summary" role="status" aria-live="polite">
      <span>{{
        search ? '“' + search + '” 的搜索结果' : '全部科研线索'
      }}</span>
      <span
        >共 <strong>{{ items.length }}</strong> 条线索</span
      >
    </div>
    <div v-if="items.length" v-reveal class="research-editorial-list">
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
            : '核对本科生参与说明后，会在此展示。'
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
  </section>
</template>
