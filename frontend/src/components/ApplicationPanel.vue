<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { applicationAction, getApplicationContact } from '../api/teams'
import {
  actionLabels,
  applicationInput,
  applicationVersionPayload,
  can,
  fieldLabels,
  label,
  optionNames,
  teamError,
  withHistoricalOptions,
} from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
import ApplicationFields from './ApplicationFields.vue'
import RecruitmentFacts from './RecruitmentFacts.vue'
const props = defineProps({ item: Object, dictionaries: Object })
const emit = defineEmits(['refresh'])
const busy = ref(false),
  error = ref(''),
  selectedAction = ref(''),
  contact = ref(null),
  form = ref(applicationInput()),
  consent = ref(false)
const choices = computed(() => {
  const current = props.item.recruitment.required_roles
  const activeCodes = new Set(
    (props.dictionaries.roles || []).map((role) => role.code),
  )
  return {
    ...props.dictionaries,
    roles: withHistoricalOptions(
      current.filter((role) => activeCodes.has(role.code)),
      props.item.desired_roles.filter((role) =>
        current.some((option) => option.code === role.code),
      ),
    ),
    skills: withHistoricalOptions(props.dictionaries.skills, props.item.skills),
  }
})
let contactGeneration = 0,
  contactController,
  contactTimer
function clearContact() {
  contactGeneration++
  contactController?.abort()
  clearTimeout(contactTimer)
  contact.value = null
}
function reset() {
  clearContact()
  selectedAction.value = ''
  consent.value = false
  form.value = applicationInput(props.item)
}
function choose(action) {
  clearContact()
  selectedAction.value = action
  consent.value = false
  form.value = applicationInput(props.item)
  if (action === 'continue')
    form.value.desired_roles = form.value.desired_roles.filter((code) =>
      props.item.recruitment.required_roles.some((role) => role.code === code),
    )
  error.value = ''
}
const explanation = computed(
  () =>
    ({
      accept:
        '接受后，双方即可查看彼此的联系方式；这一步不占名额，也不代表正式入队。',
      confirm:
        '确认针对当前招募与申请资料。双方均确认且条件仍满足时正式入队，占用一个名额；不代表已完成官方报名。',
      reject: '拒绝后，本次申请结束，申请人不能向同一卡重新申请。',
      withdraw: '撤回后，本次申请结束，不能向同一卡重新申请。',
      end: '结束后，未入队申请及其联系授权将失效。',
      'revoke-confirmation': '只撤销本人本次确认，申请仍保留。',
      continue:
        '按最新招募条件更新申请资料，双方均须重新确认；阅读通知不会代替本次操作。',
    })[selectedAction.value],
)
async function run() {
  if (busy.value || !consent.value || !can(props.item, selectedAction.value))
    return
  clearContact()
  busy.value = true
  error.value = ''
  try {
    await applicationAction(props.item.id, selectedAction.value, {
      ...applicationVersionPayload(props.item),
      ...(selectedAction.value === 'continue'
        ? applicationInput(form.value)
        : {}),
    })
    selectedAction.value = ''
    emit('refresh', '操作已完成，已重新读取最新状态。')
  } catch (err) {
    error.value = teamError(err)
    if ([401, 403, 404, 409].includes(err.response?.status)) {
      selectedAction.value = ''
      emit('refresh', error.value)
    }
  } finally {
    busy.value = false
  }
}
async function viewContact() {
  if (busy.value || !props.item.contact_available) return
  clearContact()
  const generation = contactGeneration
  contactController = new AbortController()
  busy.value = true
  error.value = ''
  try {
    const data = await getApplicationContact(
      props.item.id,
      contactController.signal,
    )
    if (
      generation === contactGeneration &&
      props.item.contact_available &&
      document.visibilityState === 'visible'
    ) {
      contact.value = data
      contactTimer = setTimeout(clearContact, 30000)
    }
  } catch (err) {
    if (err.code !== 'ERR_CANCELED') {
      error.value = teamError(err)
      emit('refresh', error.value)
    }
  } finally {
    busy.value = false
  }
}
function onVisibility() {
  clearContact()
  if (document.visibilityState === 'visible') emit('refresh')
}
watch(() => props.item, reset, { immediate: true })
onMounted(() => {
  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('blur', clearContact)
  window.addEventListener('pagehide', clearContact)
})
onBeforeUnmount(() => {
  clearContact()
  document.removeEventListener('visibilitychange', onVisibility)
  window.removeEventListener('blur', clearContact)
  window.removeEventListener('pagehide', clearContact)
})
</script>
<template>
  <article class="team-panel application-panel" :id="`application-${item.id}`">
    <div class="heading-with-actions">
      <div>
        <span class="tag" :class="{ warm: item.is_paused }">{{
          item.is_paused ? '条件变更，待申请人继续' : label(item.status)
        }}</span>
        <h2>{{ item.recruitment.competition.title }}</h2>
        <p class="muted">
          {{ item.recruitment.competition.edition }} · 申请 #{{ item.id }} ·
          {{
            item.is_applicant
              ? '我提交的申请'
              : `申请人 ${item.applicant.public_code}`
          }}
        </p>
      </div>
      <RouterLink
        :to="{
          name: 'recruitment-detail',
          params: { id: item.recruitment.id },
        }"
        >查看招募 →</RouterLink
      >
    </div>
    <p>
      意向角色：{{ optionNames(item.desired_roles) }}<br />已有技能：{{
        optionNames(item.skills)
      }}<br />可投入时间：{{ label(item.weekly_effort) }}
    </p>
    <div v-if="item.is_paused" class="notice-text">
      <strong
        >当前卡片版本 {{ item.recruitment.version }}，本申请接受的版本
        {{ item.recruitment_version }}</strong
      >
      <p v-if="item.changed_fields?.length">
        变更：{{
          item.changed_fields.map((key) => fieldLabels[key] || key).join('、')
        }}
      </p>
      <p>挂起期间不能正式入队。申请人继续后，双方须按最新条件重新确认。</p>
    </div>
    <details>
      <summary>核对当前招募条件</summary>
      <RecruitmentFacts :revision="item.recruitment" />
    </details>
    <p v-if="item.status === 'contact_open'" class="confirmation-state">
      申请人：{{ item.applicant_confirmed_at ? '已确认' : '未确认' }} ·
      招募者：{{
        item.recruiter_confirmed_at ? '已确认' : '未确认'
      }}。双方确认前不占名额。
    </p>
    <p v-if="item.end_reason" class="muted">
      结果：{{ label(item.end_reason) }}
    </p>
    <p class="timestamp">
      提交：{{ formatUpdatedAt(item.submitted_at) }} · 本申请资料版本
      {{ item.version }}
    </p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <div class="button-row">
      <button
        v-for="action in item.allowed_actions"
        :key="action"
        class="action-button secondary"
        :disabled="busy"
        @click="choose(action)"
      >
        {{ actionLabels[action] || action }}</button
      ><button
        v-if="item.contact_available"
        class="action-button secondary"
        :disabled="busy"
        @click="contact ? clearContact() : viewContact()"
      >
        {{ contact ? '隐藏联系方式' : '查看授权联系方式' }}
      </button>
    </div>
    <section v-if="contact" class="contact-panel" aria-label="授权联系方式">
      <strong>对方联系方式 · {{ contact.public_code }}</strong>
      <p v-if="contact.email">学校邮箱：{{ contact.email }}</p>
      <p v-if="contact.wechat_id">微信：{{ contact.wechat_id }}</p>
      <p v-if="contact.phone_number">手机：{{ contact.phone_number }}</p>
      <p class="timestamp">
        资料更新：{{ formatUpdatedAt(contact.contact_updated_at) }}。离开窗口或
        30 秒后自动隐藏。
      </p>
    </section>
    <form
      v-if="selectedAction && can(item, selectedAction)"
      class="action-confirm"
      @submit.prevent="run"
    >
      <h3>{{ actionLabels[selectedAction] }}</h3>
      <p>{{ explanation }}</p>
      <ApplicationFields
        v-if="selectedAction === 'continue'"
        v-model="form"
        :dictionaries="choices"
        :disabled="busy"
      /><label class="consent-row"
        ><input
          v-model="consent"
          type="checkbox"
          required
          :disabled="busy"
        /><span>我已核对以上信息，确认执行。</span></label
      >
      <div class="button-row">
        <button class="action-button" :disabled="busy || !consent">
          {{ busy ? '处理中…' : '确认操作' }}</button
        ><button
          type="button"
          class="action-button secondary"
          :disabled="busy"
          @click="selectedAction = ''"
        >
          取消
        </button>
      </div>
    </form>
  </article>
</template>
