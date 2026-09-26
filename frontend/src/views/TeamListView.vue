<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getRecruitmentOptions, listRecruitments } from '../api/teams'
import { getCompetition } from '../api/competitions'
import { teamError, validPage } from '../utils/teams'
import RecruitmentCard from '../components/RecruitmentCard.vue'
import AppIcon from '../components/AppIcon.vue'
const route = useRoute(),
  router = useRouter()
const options = ref({}),
  items = ref([]),
  count = ref(0),
  loading = ref(true),
  error = ref(''),
  optionsError = ref(''),
  selectedCompetition = ref(null)
const filters = reactive({
  search: '',
  role: '',
  skill: '',
  collaboration_mode: '',
  campus: '',
  open_only: '',
})
const page = computed(() => validPage(route.query.page))
let request = 0,
  controller
function query() {
  return Object.fromEntries(
    Object.entries(route.query).filter(
      ([key, value]) =>
        [
          'search',
          'role',
          'skill',
          'collaboration_mode',
          'campus',
          'open_only',
          'competition_id',
        ].includes(key) && typeof value === 'string',
    ),
  )
}
function changeFilters() {
  router.push({
    name: 'teams',
    query: {
      ...(route.query.competition_id
        ? { competition_id: route.query.competition_id }
        : {}),
      ...Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value),
      ),
    },
  })
}
function changePage(value) {
  router.push({
    name: 'teams',
    query: { ...query(), ...(value > 1 ? { page: value } : {}) },
  })
}
async function load() {
  const number = ++request
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  items.value = []
  Object.keys(filters).forEach((key) => {
    filters[key] = query()[key] || ''
  })
  try {
    const data = await listRecruitments(
      { ...query(), page: page.value },
      controller.signal,
    )
    if (number === request) {
      items.value = data.results
      count.value = data.count
    }
  } catch (err) {
    if (number === request && err.code !== 'ERR_CANCELED')
      error.value = teamError(err)
  } finally {
    if (number === request) loading.value = false
  }
}
async function loadOptions() {
  optionsError.value = ''
  try {
    options.value = await getRecruitmentOptions()
  } catch (err) {
    optionsError.value = teamError(err)
  }
}
watch(() => route.query, load, { immediate: true })
watch(
  () => route.query.competition_id,
  async (value) => {
    selectedCompetition.value = null
    if (!value) return
    try {
      const data = await getCompetition(value)
      if (route.query.competition_id === value) selectedCompetition.value = data
    } catch {}
  },
  { immediate: true },
)
onMounted(loadOptions)
onBeforeUnmount(() => {
  request++
  controller?.abort()
})
</script>
<template>
  <section>
    <header class="page-heading heading-with-actions">
      <div>
        <span class="section-kicker">FIND YOUR TEAM</span>
        <h1>团队广场</h1>
        <p>围绕同一场赛事，找到一起投入的伙伴。</p>
      </div>
      <div class="button-row">
        <RouterLink class="action-button secondary" to="/account/teams"
          >我的组队</RouterLink
        ><RouterLink
          class="action-button"
          :to="{
            name: 'recruitment-publish',
            query: route.query.competition_id
              ? { competition_id: route.query.competition_id }
              : {},
          }"
          >发布招募 ＋</RouterLink
        >
      </div>
    </header>
    <form class="search-bar" role="search" @submit.prevent="changeFilters">
      <AppIcon name="search" :size="19" /><label
        class="sr-only"
        for="team-search"
        >搜索赛事招募</label
      ><input
        id="team-search"
        v-model="filters.search"
        type="search"
        maxlength="200"
        placeholder="搜索赛事名称或届次…"
      /><button class="action-button">搜索</button>
    </form>
    <p v-if="route.query.competition_id" class="notice-text">
      当前赛事：{{
        selectedCompetition?.title || `赛事 #${route.query.competition_id}`
      }}
      <RouterLink :to="{ name: 'teams' }">查看全部赛事招募</RouterLink>
    </p>
    <div class="filter-panel">
      <label
        >所需角色<select v-model="filters.role" @change="changeFilters">
          <option value="">全部角色</option>
          <option
            v-for="option in options.roles"
            :key="option.code"
            :value="option.code"
          >
            {{ option.name }}
          </option>
        </select></label
      >
      <label
        >所需技能<select v-model="filters.skill" @change="changeFilters">
          <option value="">全部技能</option>
          <option
            v-for="option in options.skills"
            :key="option.code"
            :value="option.code"
          >
            {{ option.name }}
          </option>
        </select></label
      >
      <label
        >协作方式<select
          v-model="filters.collaboration_mode"
          @change="changeFilters"
        >
          <option value="">全部方式</option>
          <option
            v-for="option in options.collaboration_mode"
            :key="option.code"
            :value="option.code"
          >
            {{ option.name }}
          </option>
        </select></label
      >
      <label
        >校区<select v-model="filters.campus" @change="changeFilters">
          <option value="">全部校区</option>
          <option
            v-for="option in options.campuses"
            :key="option.code"
            :value="option.code"
          >
            {{ option.name }}
          </option>
        </select></label
      >
      <label
        >招募状态<select v-model="filters.open_only" @change="changeFilters">
          <option value="">全部公开招募</option>
          <option value="true">仅正在招募</option>
        </select></label
      >
    </div>
    <p v-if="optionsError" role="alert" class="notice-text">
      筛选选项加载失败：{{ optionsError }}
      <button class="text-button" @click="loadOptions">重试</button>
    </p>
    <div class="list-summary">
      <span>接受申请后开放联系，双方确认才正式入队</span
      ><span v-if="!loading && !error">共 {{ count }} 条招募</span>
    </div>
    <div v-if="loading" class="state-panel" role="status">正在加载招募…</div>
    <div v-else-if="error" class="state-panel" role="alert">
      <p>{{ error }}</p>
      <button class="action-button secondary" @click="load">重试</button
      ><button v-if="page > 1" class="text-button" @click="changePage(1)">
        返回第一页
      </button>
    </div>
    <div v-else-if="!items.length" class="state-panel">
      <h2>暂时没有符合条件的招募</h2>
      <p>调整筛选条件，或围绕已收录赛事发起招募。</p>
      <RouterLink class="action-button secondary" to="/teams"
        >清空筛选</RouterLink
      >
    </div>
    <div v-else class="recruitment-list">
      <RecruitmentCard
        v-for="item in items"
        :key="item.id"
        :item="item"
        :detail-query="query()"
      />
    </div>
    <el-pagination
      v-if="!loading && !error && count > 20"
      class="competition-pagination"
      :current-page="page"
      :page-size="20"
      :total="count"
      layout="prev, pager, next"
      prev-text="上一页"
      next-text="下一页"
      background
      @update:current-page="changePage"
    />
  </section>
</template>
