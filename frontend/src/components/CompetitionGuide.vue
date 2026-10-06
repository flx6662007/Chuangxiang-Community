<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getGuide, updateGuide } from '../api/guide'
import { profilePayload, conditionLabels, registrationLabels } from '../utils/guide'
import { label } from '../utils/teams'
import { safeExternalUrl } from '../utils/competition'

const result = ref(null), message = ref(''), busy = ref(false), error = ref(''), openOnly = ref(false)
const form = reactive({ education: '', grade: '', major: '', interests: '', skills: '', weekly_hours: '', team_size: '', collaboration_mode: '', role: '' })
let controller, disposed = false
function accept(data) {
  result.value = data
  for (const key of Object.keys(form)) {
    const value = data.profile?.[key]
    form[key] = Array.isArray(value) ? value.join('、') : value ?? ''
  }
  openOnly.value = data.filters?.recruitment_open === true
}
async function run(action = 'search', recordId, saveProfile = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  controller = new AbortController()
  try {
    const data = { action, message: recordId || saveProfile || ['reset', 'retry'].includes(action) ? '' : message.value }
    if (recordId) data.record_id = recordId
    if (saveProfile) {
      data.profile = profilePayload(form)
      data.filters = openOnly.value ? { recruitment_open: true } : {}
    }
    const reply = await updateGuide(data, controller.signal)
    if (disposed) return
    accept(reply)
    message.value = ''
  } catch (cause) {
    if (!disposed && cause.code !== 'ERR_CANCELED') error.value = cause.response?.status === 400 ? '请检查条件填写：每周投入为 1—80 小时，人数为 1—1000 人。' : '查询未完成，请重试。'
  } finally { busy.value = false }
}
onMounted(async () => {
  busy.value = true
  controller = new AbortController()
  try { const data = await getGuide(controller.signal); if (!disposed) accept(data) }
  catch (cause) { if (!disposed && cause.code !== 'ERR_CANCELED') error.value = '暂时无法读取对话，可以重新查询。' }
  finally { busy.value = false }
})
onBeforeUnmount(() => { disposed = true; controller?.abort() })
function enter(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); if (message.value.trim()) run() }
}
</script>

<template>
  <section class="competition-guide" aria-labelledby="competition-guide-title" :aria-busy="busy">
    <div class="section-heading">
      <div><h2 id="competition-guide-title">选比赛，了解要求，找到队友</h2><p>说说你的兴趣和技能，一起找到适合准备的赛事。</p></div>
      <button type="button" class="text-button" :disabled="busy" @click="run('reset')">重新开始</button>
    </div>
    <form class="guide-question" @submit.prevent="run()">
      <label for="guide-message">你的需求</label>
      <textarea id="guide-message" v-model="message" rows="3" maxlength="500" placeholder="例如：我是大二学生，会一点 Python，每周能投入 5 小时，想了解数学建模比赛。" @keydown="enter" />
      <button class="action-button" :disabled="busy || !message.trim()">{{ busy ? '正在整理回答…' : '发送' }}</button>
    </form>
    <details class="guide-profile">
      <summary>查看和修改我的条件</summary>
      <form @submit.prevent="run('search', null, true)">
        <div class="guide-fields">
          <label>学历<select v-model="form.education"><option value="">未填写</option><option v-for="value in ['本科','专科','硕士','博士']" :key="value">{{ value }}</option></select></label>
          <label>年级<select v-model="form.grade"><option value="">未填写</option><option v-for="value in ['大一','大二','大三','大四','大五','大六']" :key="value">{{ value }}</option></select></label>
          <label>专业<input v-model="form.major" maxlength="60" /></label>
          <label>兴趣方向<input v-model="form.interests" maxlength="200" placeholder="数学建模、机器人" /></label>
          <label>已有技能<input v-model="form.skills" maxlength="300" placeholder="Python、写作" /></label>
          <label>每周投入（小时）<input v-model="form.weekly_hours" type="number" min="1" max="80" /></label>
          <label>参赛团队人数<input v-model="form.team_size" type="number" min="1" max="1000" /></label>
          <label>想承担的角色<input v-model="form.role" maxlength="40" /></label>
          <label>协作方式<select v-model="form.collaboration_mode"><option value="">均可</option><option value="online">线上</option><option value="offline">线下</option><option value="hybrid">线上线下结合</option></select></label>
        </div>
        <label class="guide-checkbox"><input v-model="openOnly" type="checkbox" />只看可以组队的赛事</label>
        <button class="action-button secondary" :disabled="busy">按这些条件查找</button>
      </form>
    </details>
    <p v-if="error" role="alert" class="form-error">{{ error }}</p>
    <div v-if="result" aria-live="polite">
      <div v-if="result.answer?.paragraphs?.length" class="guide-answer">
        <h3>赛事助手</h3>
        <div v-for="(paragraph, index) in result.answer.paragraphs" :key="index">
          <p class="guide-answer-text">{{ paragraph.text }}</p>
          <a v-for="source in paragraph.citations" :key="`${source.record_id}:${source.id}`" :href="safeExternalUrl(source.url) || undefined" target="_blank" rel="noopener noreferrer" class="guide-citation">{{ source.title }} · {{ source.edition }}</a>
        </div>
      </div>
      <p v-else class="guide-response">{{ result.message }}</p>
      <div v-if="result.answer?.notice" role="status">
        <p>{{ result.answer.notice }}</p>
        <button type="button" class="text-button" :disabled="busy" @click="run('retry')">重试 AI 回答</button>
      </div>
      <p v-for="question in result.questions" :key="question">{{ question }}</p>
      <div class="guide-candidates">
        <article v-for="(candidate, index) in result.candidates" :key="candidate.record_id" class="guide-card">
          <h3>{{ index + 1 }}. {{ candidate.title }}</h3>
          <p class="muted">{{ candidate.edition || '届次未注明' }} · {{ registrationLabels[candidate.registration_status] }}</p>
          <p v-if="candidate.recruitment_target">{{ candidate.recruitment_target.reason }}</p>
          <p>{{ conditionLabels[candidate.match_status] }}</p>
          <p v-for="reason in candidate.match_reasons" :key="reason.text">{{ reason.text }}</p>
          <button type="button" class="action-button secondary" :disabled="busy" @click="run('analyze', candidate.record_id)">分析这个赛事</button>
        </article>
      </div>
      <article v-if="result.selected" class="guide-analysis">
        <h3>{{ result.selected.title }}</h3>
        <p>资料届次：{{ result.selected.edition || '未注明' }} · {{ registrationLabels[result.selected.registration_status] }}</p>
        <p v-if="result.selected.recruitment_target">组队目标：{{ result.selected.recruitment_target.edition }} · {{ result.selected.recruitment_target.reason }}</p>
        <p><strong>{{ conditionLabels[result.selected.match_status] }}</strong></p>
        <ul v-if="result.selected.condition_checks.length">
          <li v-for="check in result.selected.condition_checks" :key="check.field">{{ check.label }}：{{ check.value }} — {{ { matched: '符合', unmatched: '不符合', unknown: '缺少对应规则依据' }[check.state] }}</li>
        </ul>
        <details v-for="section in result.selected.sections" :key="section.id" class="guide-section">
          <summary>{{ section.heading }}</summary><p>{{ section.text }}</p>
          <div v-for="source in section.evidence" :key="source.id">
            <a v-if="safeExternalUrl(source.url)" :href="safeExternalUrl(source.url)" target="_blank" rel="noopener noreferrer">{{ source.title || '官方来源' }}</a>
            <small v-if="source.locator"> · {{ source.locator }}</small>
          </div>
        </details>
        <section v-if="result.selected.learning_resources?.length">
          <h4>学习资料</h4>
          <p v-for="resource in result.selected.learning_resources" :key="resource.id">
            <a v-if="safeExternalUrl(resource.url)" :href="safeExternalUrl(resource.url)" target="_blank" rel="noopener noreferrer">{{ resource.title }}</a> · {{ resource.summary }}
          </p>
        </section>
        <button type="button" class="action-button" :disabled="busy || !result.selected.recruitment_target?.open || result.selected.match_status === 'unmatched'" @click="run('teammates', result.selected.record_id)">查找队友</button>
      </article>
      <section v-if="result.stage === 'teammates'" class="guide-team-results">
        <h3>适合你的开放招募</h3>
        <p v-if="!result.recruitments.length">{{ result.message }}</p>
        <article v-for="card in result.recruitments" :key="card.id" class="guide-card">
          <h4>{{ card.competition.title }} · {{ card.competition.edition }}</h4>
          <p>还需 {{ card.remaining_slots }} 人 · {{ card.required_roles.map(role => role.name).join('、') }}</p>
          <p>{{ label(card.weekly_effort) }} · {{ label(card.collaboration_mode) }} · {{ label(card.foundation_requirement) }}</p>
          <p v-for="reason in card.match_reasons" :key="reason">{{ reason }}</p>
          <p v-if="card.skills_to_confirm.length">需要沟通的技能：{{ card.skills_to_confirm.join('、') }}</p>
          <RouterLink class="action-button secondary" :to="card.url">查看招募与申请</RouterLink>
        </article>
        <div v-if="result.team_context?.competition" class="guide-team-actions">
          <p>组队赛事：{{ result.team_context.competition.title }} · {{ result.team_context.competition.edition }}</p>
          <RouterLink class="action-button secondary" :to="result.team_context.browse_url">查看该届全部招募</RouterLink>
          <RouterLink class="action-button secondary" :to="result.team_context.create_url">发布该赛事招募</RouterLink>
        </div>
        <RouterLink class="text-button" to="/teams">浏览其他赛事招募 →</RouterLink>
      </section>
    </div>
  </section>
</template>

<style scoped>
.guide-answer { padding:18px; border-left:3px solid var(--accent-color,#447864); background:var(--bg-secondary,transparent); border-radius:8px; }
.guide-answer-text { white-space:pre-wrap; line-height:1.85; }
.guide-citation { display:inline-block; margin:0 12px 8px 0; font-size:.85em; }
.guide-team-actions { display:flex; flex-wrap:wrap; gap:12px; align-items:center; }
.guide-team-actions p { flex-basis:100%; }
.competition-guide { padding-block: 24px; }
.guide-question,.guide-profile form,.guide-candidates,.guide-team-results { display:grid; gap:16px; }
.guide-question textarea,.guide-fields input,.guide-fields select { width:100%; padding:10px 12px; color:var(--text-primary); background:var(--bg-secondary,transparent); border:1px solid var(--border-color,#8b8b8b66); border-radius:8px; font:inherit; }
.guide-question .action-button { justify-self:end; }
.guide-profile { margin:24px 0; padding:16px; border:1px solid var(--border-color,#8b8b8b66); border-radius:12px; }
summary { cursor:pointer; font-weight:600; }
.guide-fields { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; padding-top:16px; }
.guide-fields label { display:grid; gap:6px; }
.guide-checkbox { display:flex; gap:8px; align-items:center; }
.guide-candidates { grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr)); }
.guide-card,.guide-analysis { padding:20px; border:1px solid var(--border-color,#8b8b8b66); border-radius:12px; overflow-wrap:anywhere; }
.guide-card h3,.guide-card h4 { margin-top:0; }
.guide-analysis { margin-top:24px; }
.guide-section { margin-block:18px; }
.guide-section p { white-space:pre-wrap; line-height:1.8; }
.guide-section a { color:var(--accent,#4875b8); }
.guide-response { font-size:1.1em; }
button:disabled { opacity:.55; cursor:wait; }
</style>
