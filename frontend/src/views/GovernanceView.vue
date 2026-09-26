<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createAppeal,
  listAppealTargets,
  listMyAppeals,
  listMyReports,
} from '../api/governance'
import { useGovernanceSession } from '../composables/useGovernanceSession'
import {
  appealInput,
  availableAppealTarget,
  descriptionError,
  governanceError,
  governanceTargetLabels,
  targetKey,
} from '../utils/governance'
import { validPage } from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
const route = useRoute(),
  router = useRouter(),
  items = ref([]),
  count = ref(0),
  selected = ref(''),
  description = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('')
const tab = computed(() =>
  ['appeals', 'new'].includes(route.query.tab) ? route.query.tab : 'reports',
)
const page = computed(() => validPage(route.query.page))
function clear() {
  items.value = []
  count.value = 0
  selected.value = ''
  description.value = ''
  busy.value = false
  error.value = ''
  message.value = ''
}
const access = useGovernanceSession(clear, async (context) => {
  const fetch = {
    reports: listMyReports,
    appeals: listMyAppeals,
    new: listAppealTargets,
  }[tab.value]
  const data = await fetch({ page: page.value }, context.signal)
  if (!context.isCurrent()) return
  items.value = data.results
  count.value = data.count
  const match = availableAppealTarget(items.value, route.query.target)
  if (tab.value === 'new' && match) selected.value = targetKey(match)
})
const { profile, checking, sessionError } = access
const selectedTarget = computed(() =>
  availableAppealTarget(items.value, selected.value),
)
function navigate(next, nextPage = 1, target = '') {
  router.push({
    name: 'governance',
    query: {
      ...(next !== 'reports' ? { tab: next } : {}),
      ...(nextPage > 1 ? { page: nextPage } : {}),
      ...(target ? { target } : {}),
    },
  })
}
async function submit() {
  if (busy.value || !profile.value) return
  let body
  try {
    body = appealInput(items.value, selected.value, description.value)
  } catch (err) {
    error.value = err.message
    return
  }
  const token = access.capture()
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await createAppeal(body, access.signal())
    if (!access.isCurrent(token)) return
    selected.value = ''
    description.value = ''
    const reloading = access.refresh()
    const refreshedToken = access.capture()
    await reloading
    if (access.isCurrent(refreshedToken) && profile.value)
      message.value = '申诉已提交。请到“我的申诉”查看处理进度。'
  } catch (err) {
    if (!access.isCurrent(token) || err.code === 'ERR_CANCELED') return
    const text = governanceError(err)
    if ([401, 403, 404, 409].includes(err.response?.status)) {
      const reloading = access.refresh()
      const refreshedToken = access.capture()
      await reloading
      if (!access.isCurrent(refreshedToken)) return
    }
    error.value = text
  } finally {
    if (access.isCurrent(token)) busy.value = false
  }
}
watch(
  () => [route.query.tab, route.query.page, route.query.target],
  access.refresh,
)
</script>
<template>
  <section>
    <header class="page-heading heading-with-actions">
      <div>
        <span class="section-kicker">REPORTS & APPEALS</span>
        <h1>我的举报与申诉</h1>
        <p>仅显示本人记录。登录后即可使用，邮箱未核验或账号受限不影响提交。</p>
      </div>
      <RouterLink class="action-button secondary" to="/account"
        >账号中心</RouterLink
      >
    </header>
    <nav class="tab-nav" aria-label="举报与申诉分类">
      <button
        :class="{ active: tab === 'reports' }"
        @click="navigate('reports')"
      >
        我的举报</button
      ><button
        :class="{ active: tab === 'appeals' }"
        @click="navigate('appeals')"
      >
        我的申诉</button
      ><button :class="{ active: tab === 'new' }" @click="navigate('new')">
        发起申诉</button
      ><button
        class="refresh-button"
        :disabled="checking || busy"
        @click="access.refresh"
      >
        刷新记录
      </button>
    </nav>
    <div v-if="checking" class="state-panel" role="status">
      正在读取本人记录…
    </div>
    <div v-else-if="sessionError" class="state-panel" role="alert">
      <p>{{ sessionError }}</p>
      <button class="action-button secondary" @click="access.refresh">
        重试
      </button>
    </div>
    <div v-else-if="!profile" class="state-panel">
      <h2>登录后查看本人记录</h2>
      <p>举报内容与申诉说明不会公开展示。</p>
      <RouterLink class="action-button" to="/account">去登录</RouterLink>
    </div>
    <template v-else>
      <p v-if="message" class="notice-text" role="status">{{ message }}</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <template v-if="tab === 'new'">
        <section class="team-panel">
          <h2>选择需要复核的事项</h2>
          <p>
            可申诉本人账号限制、招募处置及已处理的举报结果。申诉成立不等于已解除限制或恢复招募，以实际处理反馈为准。
          </p>
          <p v-if="!items.length" class="muted">暂无可申诉事项。</p>
          <form v-else class="governance-form" @submit.prevent="submit">
            <label for="appeal-target">相关事项（第 {{ page }} 页）</label
            ><select
              id="appeal-target"
              v-model="selected"
              required
              :disabled="busy"
            >
              <option value="" disabled>请选择本人事项</option>
              <option
                v-for="item in items"
                :key="targetKey(item)"
                :value="targetKey(item)"
                :disabled="!item.can_appeal || !!item.pending_appeal_id"
              >
                {{ governanceTargetLabels[item.target_type] }} · {{ item.title
                }}{{
                  item.pending_appeal_id
                    ? '（已有待处理申诉）'
                    : !item.can_appeal
                      ? '（当前不可申诉）'
                      : ''
                }}
              </option>
            </select>
            <div v-if="selectedTarget" class="notice-text">
              <p class="preserve-lines">
                处理原因：{{ selectedTarget.reason || '未注明' }}
              </p>
              <p class="timestamp">
                {{ formatUpdatedAt(selectedTarget.occurred_at) }}
              </p>
            </div>
            <label for="appeal-description">申诉说明</label
            ><textarea
              id="appeal-description"
              v-model="description"
              required
              maxlength="1000"
              rows="6"
              :disabled="busy"
              placeholder="说明需要复核的原因与核对依据，勿填写密码等敏感资料。"
            />
            <p class="field-hint">
              {{ description.length }}/1000 字。离开标签页会清空未提交内容。
            </p>
            <button
              class="action-button"
              :disabled="
                busy || !selectedTarget || !!descriptionError(description)
              "
            >
              {{ busy ? '提交中…' : '提交申诉' }}
            </button>
          </form>
        </section>
      </template>
      <div v-else-if="!items.length" class="state-panel">
        <h2>{{ tab === 'reports' ? '暂无举报记录' : '暂无申诉记录' }}</h2>
        <p>
          {{
            tab === 'reports'
              ? '如发现问题，可在赛事或招募详情提交举报。'
              : '有需要复核的事项时，可通过“发起申诉”提交。'
          }}
        </p>
      </div>
      <div v-else class="team-records">
        <article
          v-for="item in items"
          :key="item.id"
          class="team-panel governance-panel"
        >
          <div class="heading-with-actions">
            <h2>{{ item.target_title }}</h2>
            <span class="tag">{{ item.status_label }}</span>
          </div>
          <p class="muted">
            {{ governanceTargetLabels[item.target_type]
            }}{{ item.reason_label ? ' · ' + item.reason_label : '' }} · 记录
            #{{ item.id }}
          </p>
          <h3>{{ tab === 'reports' ? '举报说明' : '申诉说明' }}</h3>
          <p class="preserve-lines governance-description">
            {{ item.description }}
          </p>
          <h3>处理反馈</h3>
          <p class="preserve-lines">
            {{
              item.feedback ||
              (item.status === 'pending'
                ? '等待管理员核实处理。'
                : '暂无补充反馈。')
            }}
          </p>
          <p v-if="item.effect_note" class="notice-text preserve-lines">
            {{ item.effect_note }}
          </p>
          <p class="timestamp">
            提交：{{ formatUpdatedAt(item.created_at)
            }}<template v-if="item.reviewed_at"
              ><br />处理：{{ formatUpdatedAt(item.reviewed_at) }}</template
            >
          </p>
          <button
            v-if="tab === 'reports' && item.allowed_actions?.includes('appeal')"
            class="action-button secondary"
            @click="navigate('new', 1, 'report:' + item.id)"
          >
            申请复核
          </button>
        </article>
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
        @update:current-page="navigate(tab, $event)"
      />
    </template>
  </section>
</template>
