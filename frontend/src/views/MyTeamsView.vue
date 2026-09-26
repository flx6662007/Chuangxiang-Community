<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSessionProfile } from '../api/accounts'
import {
  getApplication,
  getRecruitmentOptions,
  listApplications,
  listMyTeams,
} from '../api/teams'
import { teamError, validPage } from '../utils/teams'
import TeamPanel from '../components/TeamPanel.vue'
import ApplicationPanel from '../components/ApplicationPanel.vue'
const route = useRoute(),
  router = useRouter(),
  dictionaries = ref({}),
  profile = ref(null),
  initialized = ref(false),
  loading = ref(true),
  error = ref(''),
  items = ref([]),
  count = ref(0),
  focused = ref(null)
const tab = computed(() =>
    ['sent', 'received'].includes(route.query.tab) ? route.query.tab : 'teams',
  ),
  page = computed(() => validPage(route.query.page))
const actionMessage = ref('')
let serial = 0,
  controller
function routeTo(next, nextPage = 1) {
  router.push({
    name: 'my-teams',
    query: {
      ...(next !== 'teams' ? { tab: next } : {}),
      ...(nextPage > 1 ? { page: nextPage } : {}),
    },
  })
}
async function load() {
  const request = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  items.value = []
  focused.value = null
  try {
    const user = await getSessionProfile()
    if (request !== serial) return
    profile.value = user
    initialized.value = true
    if (!user) return
    const [options, data] = await Promise.all([
      getRecruitmentOptions(controller.signal),
      tab.value === 'teams'
        ? listMyTeams({ page: page.value }, controller.signal)
        : listApplications(
            { scope: tab.value, page: page.value },
            controller.signal,
          ),
    ])
    if (request !== serial) return
    dictionaries.value = options
    items.value = data.results
    count.value = data.count
    if (
      route.query.application &&
      tab.value !== 'teams' &&
      !items.value.some((item) => String(item.id) === route.query.application)
    ) {
      const result = await getApplication(
        route.query.application,
        controller.signal,
      )
      if (request === serial) focused.value = result
    }
  } catch (err) {
    if (request === serial && err.code !== 'ERR_CANCELED') {
      error.value = teamError(err)
      if (err.sessionExpired) profile.value = null
    }
  } finally {
    if (request === serial) loading.value = false
  }
}
function refresh(message) {
  if (typeof message === 'string') actionMessage.value = message
  return load()
}
function visibleRefresh() {
  if (document.visibilityState === 'visible') load()
}
watch(
  () => [route.query.tab, route.query.page, route.query.application],
  load,
  { immediate: true },
)
onMounted(() => {
  document.addEventListener('visibilitychange', visibleRefresh)
})
onBeforeUnmount(() => {
  serial++
  controller?.abort()
  document.removeEventListener('visibilitychange', visibleRefresh)
})
</script>
<template>
  <section>
    <header class="page-heading heading-with-actions">
      <div>
        <span class="section-kicker">MY COLLABORATIONS</span>
        <h1>我的组队</h1>
        <p>处理申请、核对条件，记录每一次正式确认。</p>
      </div>
      <div class="button-row">
        <RouterLink class="action-button secondary" to="/account/notifications"
          >系统通知</RouterLink
        ><RouterLink class="action-button" to="/teams">寻找伙伴</RouterLink>
      </div>
    </header>
    <nav class="tab-nav" aria-label="我的组队分类">
      <button :class="{ active: tab === 'teams' }" @click="routeTo('teams')">
        我的队伍与招募</button
      ><button :class="{ active: tab === 'sent' }" @click="routeTo('sent')">
        我提交的申请</button
      ><button
        :class="{ active: tab === 'received' }"
        @click="routeTo('received')"
      >
        我收到的申请</button
      ><button class="refresh-button" :disabled="loading" @click="load">
        刷新状态
      </button>
    </nav>
    <p v-if="actionMessage" class="notice-text" role="status">
      {{ actionMessage }}
    </p>
    <div v-if="loading" class="state-panel" role="status">
      正在读取最新状态…
    </div>
    <div v-else-if="error" class="state-panel" role="alert">
      <p>{{ error }}</p>
      <button class="action-button secondary" @click="load">重试</button
      ><RouterLink to="/account">检查账号状态</RouterLink>
    </div>
    <div v-else-if="initialized && !profile" class="state-panel">
      <h2>登录后查看本人记录</h2>
      <p>他人的申请与联系资料不会公开展示。</p>
      <RouterLink class="action-button" to="/account">去登录</RouterLink>
    </div>
    <template v-else
      ><ApplicationPanel
        v-if="focused"
        :item="focused"
        :dictionaries="dictionaries"
        @refresh="refresh" />
      <p v-if="focused" class="muted">
        以上为通知或提交后定位的申请；下面为本页列表。
      </p>
      <div v-if="!items.length" class="state-panel">
        <h2>{{ tab === 'teams' ? '还没有队伍记录' : '还没有申请记录' }}</h2>
        <p>
          {{
            tab === 'received'
              ? '发布招募后，收到的申请会显示在这里。'
              : '可以先去团队广场查看适合自己的赛事招募。'
          }}
        </p>
        <RouterLink class="action-button secondary" to="/teams"
          >浏览团队广场</RouterLink
        >
      </div>
      <div v-else class="team-records">
        <template v-for="item in items" :key="item.id"
          ><TeamPanel
            v-if="tab === 'teams'"
            :team="item"
            @refresh="refresh" /><ApplicationPanel
            v-else
            :item="item"
            :dictionaries="dictionaries"
            @refresh="refresh"
        /></template>
      </div>
      <el-pagination
        v-if="count > 20"
        class="competition-pagination"
        :current-page="page"
        :page-size="20"
        :total="count"
        layout="prev, pager, next"
        prev-text="上一页"
        next-text="下一页"
        background
        @update:current-page="routeTo(tab, $event)"
    /></template>
  </section>
</template>
