<script setup>
import { recruitmentDeadline } from '../utils/teams'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  applyToRecruitment,
  getRecruitment,
  getRecruitmentOptions,
} from '../api/teams'
import {
  applicationInput,
  can,
  label,
  optionNames,
  teamError,
} from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
import RecruitmentFacts from '../components/RecruitmentFacts.vue'
import ApplicationFields from '../components/ApplicationFields.vue'
const route = useRoute(),
  router = useRouter(),
  item = ref(null),
  dictionaries = ref({}),
  loading = ref(true),
  error = ref(''),
  actionError = ref(''),
  busy = ref(false),
  applying = ref(false),
  consent = ref(false),
  form = ref(applicationInput())
const applicationOptions = computed(() => ({
  ...dictionaries.value,
  roles: (item.value?.required_roles || []).filter((role) =>
    (dictionaries.value.roles || []).some(
      (option) => option.code === role.code,
    ),
  ),
}))
let serial = 0,
  controller
async function load() {
  const request = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  item.value = null
  applying.value = false
  try {
    const [data, options] = await Promise.all([
      getRecruitment(route.params.id, controller.signal),
      getRecruitmentOptions(controller.signal),
    ])
    if (request === serial) {
      item.value = data
      dictionaries.value = options
    }
  } catch (err) {
    if (request === serial && err.code !== 'ERR_CANCELED')
      error.value = teamError(err)
  } finally {
    if (request === serial) loading.value = false
  }
}
async function submit() {
  if (busy.value || !consent.value) return
  busy.value = true
  actionError.value = ''
  try {
    const data = await applyToRecruitment(item.value.id, {
      ...applicationInput(form.value),
      expected_version: item.value.version,
    })
    await router.push({
      name: 'my-teams',
      query: { tab: 'sent', application: data.id },
    })
  } catch (err) {
    actionError.value = teamError(err)
    if ([403, 409].includes(err.response?.status)) await load()
  } finally {
    busy.value = false
  }
}
watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => {
  serial++
  controller?.abort()
})
</script>
<template>
  <section class="detail-page">
    <RouterLink class="back-link" :to="{ name: 'teams', query: route.query }"
      >← 团队广场<span>/</span>招募详情</RouterLink
    >
    <div v-if="loading" class="state-panel" role="status">正在加载招募…</div>
    <div v-else-if="error" class="state-panel" role="alert">
      <p>{{ error }}</p>
      <button class="action-button secondary" @click="load">重新加载</button
      ><RouterLink to="/account/teams">查看我的历史记录</RouterLink>
    </div>
    <template v-else-if="item">
      <header class="detail-hero">
        <div class="detail-hero-copy">
          <div class="tag-row">
            <span class="tag" :class="{ neutral: !item.is_open }">{{
              item.is_open ? '正在招募' : label(item.status)
            }}</span
            ><span class="muted">卡片版本 {{ item.version }}</span>
          </div>
          <h1>
            {{ item.competition.title }} ·
            {{
              item.required_roles?.length
                ? optionNames(item.required_roles)
                : '参赛招募'
            }}
          </h1>
          <p>
            {{ item.competition.edition }} · 剩余
            {{ item.remaining_slots }} 个名额
          </p>
        </div>
        <RouterLink
          class="action-button secondary"
          :to="{
            name: 'competition-detail',
            params: { id: item.competition.id },
          }"
          >查看赛事与官方来源</RouterLink
        >
      </header>
      <div class="detail-layout">
        <div class="detail-main">
          <section class="team-panel">
            <h2>招募条件</h2>
            <RecruitmentFacts :revision="item" />
            <p class="muted">
              当前有效已有成员基数：{{
                item.current_existing_member_count
              }}
              人；本轮成功入队且仍占名额：{{ item.joined_member_count }} 人。
            </p>
            <p class="timestamp">
              实际到期：{{ formatUpdatedAt(recruitmentDeadline(item))
              }}<br />最后编辑：{{ formatUpdatedAt(item.last_edited_at) }}
            </p>
          </section>
          <p v-if="actionError" class="form-error" role="alert">
            {{ actionError }}
          </p>
          <form
            v-if="applying && can(item, 'apply')"
            class="team-panel"
            @submit.prevent="submit"
          >
            <h2>申请加入</h2>
            <ApplicationFields
              v-model="form"
              :dictionaries="applicationOptions"
              :disabled="busy"
            /><label class="consent-row"
              ><input
                v-model="consent"
                type="checkbox"
                required
                :disabled="busy"
              /><span
                >我同意招募者接受后，双方可查看彼此约定的联系方式；沟通后仍需双方确认才正式入队。</span
              ></label
            >
            <p class="muted">
              同一张卡仅能申请一次。撤回或被拒绝后，不能向本卡重新申请。
            </p>
            <div class="button-row">
              <button class="action-button" :disabled="busy || !consent">
                {{ busy ? '提交中…' : '提交申请' }}</button
              ><button
                type="button"
                class="action-button secondary"
                :disabled="busy"
                @click="applying = false"
              >
                取消
              </button>
            </div>
          </form>
        </div>
        <aside class="detail-sidebar">
          <section class="team-panel">
            <h2>一起完成一场赛事</h2>
            <p>
              接受申请不占名额。双方针对当前条件确认后，才建立正式队伍关系。
            </p>
            <p>平台内组队不等于完成官方报名。</p>
            <button
              v-if="can(item, 'apply') && !applying"
              class="action-button"
              @click="applying = true"
            >
              申请加入</button
            ><RouterLink
              v-if="can(item, 'edit')"
              class="action-button"
              :to="{ name: 'recruitment-edit', params: { id: item.id } }"
              >编辑招募</RouterLink
            >
            <p
              v-if="!can(item, 'apply') && !can(item, 'edit')"
              class="notice-text"
            >
              {{
                item.is_open
                  ? '发布或申请需登录、核验学校邮箱并完善联系方式。已有申请请到我的组队查看。'
                  : '当前招募不接受新申请，已有关系可到我的组队查看。'
              }}
            </p>
            <div class="stack-links">
              <RouterLink to="/account">账号与邮箱核验 →</RouterLink
              ><RouterLink to="/account/teams">我的组队与申请 →</RouterLink>
            </div>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>
