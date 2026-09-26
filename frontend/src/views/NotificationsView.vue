<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSessionProfile } from '../api/accounts'
import { listNotifications, readNotification } from '../api/notifications'
import { notificationTarget, teamError, validPage } from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
const route = useRoute(),
  router = useRouter(),
  items = ref([]),
  count = ref(0),
  unreadCount = ref(null),
  loading = ref(true),
  error = ref(''),
  profile = ref(null),
  busy = ref(null)
const page = computed(() => validPage(route.query.page)),
  unread = computed(() => route.query.unread === 'true')
let serial = 0,
  controller
function change(nextPage = 1, onlyUnread = unread.value) {
  router.push({
    name: 'notifications',
    query: {
      ...(onlyUnread ? { unread: 'true' } : {}),
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
  try {
    const user = await getSessionProfile()
    if (request !== serial) return
    profile.value = user
    if (!user) return
    const data = await listNotifications(
      { page: page.value, unread: unread.value ? 'true' : undefined },
      controller.signal,
    )
    if (request === serial) {
      items.value = data.results
      count.value = data.count
      unreadCount.value = data.unread_count ?? null
    }
  } catch (err) {
    if (request === serial && err.code !== 'ERR_CANCELED')
      error.value = teamError(err)
  } finally {
    if (request === serial) loading.value = false
  }
}
async function mark(item, open = false) {
  if (busy.value) return
  busy.value = item.id
  error.value = ''
  try {
    if (!item.read_at) {
      const data = await readNotification(item.id)
      item.read_at = data.read_at
    }
    if (open) {
      await router.push(notificationTarget(item.target))
    } else await load()
  } catch (err) {
    error.value = teamError(err)
  } finally {
    busy.value = null
  }
}
watch(() => [page.value, unread.value], load, { immediate: true })
onBeforeUnmount(() => {
  serial++
  controller?.abort()
})
</script>
<template>
  <section>
    <header class="page-heading heading-with-actions">
      <div>
        <span class="section-kicker">NOTIFICATIONS</span>
        <h1>系统通知</h1>
        <p>阅读通知不会代替继续申请、确认入队或同意退出。</p>
      </div>
      <RouterLink class="action-button secondary" to="/account/teams"
        >我的组队</RouterLink
      >
    </header>
    <nav class="tab-nav" aria-label="通知筛选">
      <button :class="{ active: !unread }" @click="change(1, false)">
        全部通知</button
      ><button :class="{ active: unread }" @click="change(1, true)">
        未读通知{{ unreadCount === null ? '' : `（${unreadCount}）` }}</button
      ><button class="refresh-button" :disabled="loading" @click="load">
        刷新
      </button>
    </nav>
    <div v-if="loading" class="state-panel" role="status">正在加载通知…</div>
    <div v-else-if="error" class="state-panel" role="alert">
      <p>{{ error }}</p>
      <button class="action-button secondary" @click="load">重新加载</button>
    </div>
    <div v-else-if="!profile" class="state-panel">
      <p>登录后查看本人的系统通知。</p>
      <RouterLink class="action-button" to="/account">去登录</RouterLink>
    </div>
    <div v-else-if="!items.length" class="state-panel">
      {{ unread ? '当前没有未读通知。' : '当前没有系统通知。' }}
    </div>
    <div v-else class="team-records">
      <article
        v-for="item in items"
        :key="item.id"
        class="team-panel notification-card"
        :class="{ unread: !item.read_at }"
      >
        <div class="heading-with-actions">
          <h2>{{ item.title }}</h2>
          <span v-if="!item.read_at" class="tag">未读</span>
        </div>
        <p class="preserve-lines">{{ item.body }}</p>
        <p class="timestamp">{{ formatUpdatedAt(item.created_at) }}</p>
        <div class="button-row">
          <button
            class="action-button secondary"
            :disabled="busy !== null"
            @click="mark(item, true)"
          >
            查看最新状态</button
          ><button
            v-if="!item.read_at"
            class="text-button"
            :disabled="busy !== null"
            @click="mark(item)"
          >
            标记已读
          </button>
        </div>
      </article>
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
      @update:current-page="change($event)"
    />
  </section>
</template>
