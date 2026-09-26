<script setup>
import { computed, ref, watch } from 'vue'
import { createReport, getGovernanceOptions } from '../api/governance'
import { useGovernanceSession } from '../composables/useGovernanceSession'
import { descriptionError, governanceError } from '../utils/governance'
const props = defineProps({
  targetType: { type: String, required: true },
  targetId: { type: Number, required: true },
})
const open = ref(false),
  busy = ref(false),
  reason = ref(''),
  description = ref(''),
  reasons = ref([]),
  error = ref(''),
  message = ref('')
function clear() {
  open.value = false
  reason.value = ''
  description.value = ''
  reasons.value = []
  error.value = ''
  message.value = ''
  busy.value = false
}
const access = useGovernanceSession(clear, async (context) => {
  const data = await getGovernanceOptions(context.signal)
  if (context.isCurrent()) reasons.value = data.report_reasons || []
})
const { profile, checking, sessionError } = access
const fieldId = computed(
  () => 'report-' + props.targetType + '-' + props.targetId,
)
const canSubmit = computed(
  () =>
    reasons.value.some((item) => item.code === reason.value) &&
    !descriptionError(description.value),
)
async function submit() {
  if (busy.value || !profile.value || !canSubmit.value) return
  const token = access.capture()
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await createReport(
      {
        target_type: props.targetType,
        target_id: props.targetId,
        reason: reason.value,
        description: description.value.trim(),
      },
      access.signal(),
    )
    if (!access.isCurrent(token)) return
    open.value = false
    reason.value = ''
    description.value = ''
    message.value = '举报已提交。可在“我的举报与申诉”查看处理进度。'
  } catch (err) {
    if (access.isCurrent(token) && err.code !== 'ERR_CANCELED') {
      const text = governanceError(err)
      if ([401, 403].includes(err.response?.status)) {
        const reloading = access.refresh()
        const refreshedToken = access.capture()
        await reloading
        if (!access.isCurrent(refreshedToken)) return
      }
      error.value = text
    }
  } finally {
    if (access.isCurrent(token)) busy.value = false
  }
}
function startReport() {
  open.value = true
  message.value = ''
}
function cancel() {
  open.value = false
  description.value = ''
  reason.value = ''
  error.value = ''
}
watch(() => [props.targetType, props.targetId], access.refresh)
</script>
<template>
  <section class="team-panel governance-panel" aria-label="举报信息">
    <h2>信息有问题？</h2>
    <p class="muted">举报由管理员核实后处理，提交举报不会自动下架内容。</p>
    <p v-if="checking" role="status">正在检查登录状态…</p>
    <div v-else-if="sessionError" role="alert">
      <p>{{ sessionError }}</p>
      <button class="text-button" @click="access.refresh">重试</button>
    </div>
    <p v-else-if="!profile">
      <RouterLink to="/account">登录后举报</RouterLink>；无需先核验邮箱。
    </p>
    <template v-else>
      <button v-if="!open" class="action-button secondary" @click="startReport">
        举报此信息
      </button>
      <form v-else class="governance-form" @submit.prevent="submit">
        <label :for="fieldId + '-reason'">举报原因</label>
        <select
          :id="fieldId + '-reason'"
          v-model="reason"
          required
          :disabled="busy"
        >
          <option disabled value="">请选择原因</option>
          <option
            v-for="option in reasons"
            :key="option.code"
            :value="option.code"
          >
            {{ option.name }}
          </option>
        </select>
        <label :for="fieldId + '-description'">具体说明</label>
        <textarea
          :id="fieldId + '-description'"
          v-model="description"
          required
          maxlength="1000"
          rows="5"
          :disabled="busy"
          placeholder="说明有问题的内容及核对依据，勿填写密码等敏感资料。"
        />
        <p class="field-hint">
          {{ description.length }}/1000 字。离开标签页会清空未提交内容。
        </p>
        <div class="button-row">
          <button class="action-button" :disabled="busy || !canSubmit">
            {{ busy ? '提交中…' : '提交举报' }}</button
          ><button
            type="button"
            class="text-button"
            :disabled="busy"
            @click="cancel"
          >
            取消
          </button>
        </div>
      </form>
      <RouterLink class="governance-record-link" to="/account/governance"
        >我的举报与申诉 →</RouterLink
      >
    </template>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-if="message" class="notice-text" role="status">{{ message }}</p>
  </section>
</template>
