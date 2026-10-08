<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { renderAIMessage } from '../utils/aiMarkdown.js'
import { getAIStatus } from '../api/ai'
import { requestAIChatStream } from '../api/aiStream'
import { useAIChat } from '../composables/useAIChat.js'
import CatalogSearch from './CatalogSearch.vue'
import CompetitionGuide from './CompetitionGuide.vue'
import ResearchFieldLinks from './ResearchFieldLinks.vue'

const researchFields = [
  ['summary', '研究内容'], ['direction', '研究方向'], ['location', '研究地点'], ['achievements', '研究成果'],
  ['roles', '招募对象'], ['eligibility', '申请条件'], ['work', '参与工作'], ['commitment', '时间投入'],
  ['scope', '申请范围'], ['cohort', '招募批次'], ['deadline', '申请截止'], ['status', '招募状态'],
]

const modeOptions = [
  { value: 'smart', label: '智能' }, { value: 'competition', label: '赛事' },
  { value: 'research', label: '科研' }, { value: 'resource', label: '资源' },
]
const examplesByMode = {
  smart: ['竞赛入门', 'AI 相关', '适合大二学生', '科研创新类'],
  competition: ['数学建模比赛', '适合大二学生', '机器人赛事'],
  research: ['人机交互实验室的成果', '本科生科研机会', '可兼职科研助理'],
  resource: ['Python 入门', '数学建模学习资料'],
}
const mode = ref('smart')
const webSearch = ref(false)
const examples = computed(() => examplesByMode[mode.value])
const query = ref('')
const validation = ref('')
const conversation = ref(null)
let followOutput = true
function onConversationScroll() {
  const panel = conversation.value
  if (panel) followOutput = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 80
}
const configured = ref(false)
const statusLoading = ref(true)
const statusError = ref(false)
let statusController
async function loadStatus() {
  statusController?.abort()
  const controller = statusController = new AbortController()
  statusLoading.value = true
  statusError.value = false
  try {
    const status = await getAIStatus(controller.signal)
    if (controller !== statusController) return
    if (typeof status.chat_configured !== 'boolean') throw new Error('Invalid AI status')
    configured.value = status.chat_configured
  } catch (err) {
    if (controller === statusController && err.code !== 'ERR_CANCELED') statusError.value = true
  } finally {
    if (controller === statusController) statusLoading.value = false
  }
}
onMounted(loadStatus)
const { messages, pending, phase, error, failed, submit, stop, dispose, clear } = useAIChat(requestAIChatStream)

function changeMode(value) {
  if (value === mode.value || pending.value) return
  clear()
  query.value = ''
  validation.value = ''
  mode.value = value
}

function addExample(example) {
  const current = query.value.trim()
  if (!current.includes(example)) query.value = current ? `${current}，${example}` : example
  validation.value = ''
}

function submitChat() {
  if (pending.value) return
  const text = query.value.trim()
  if (!text) {
    validation.value = '请先输入你的问题。'
    return
  }
  if (text.length > 2000) {
    validation.value = '每条问题最多 2000 字，请缩短后发送。'
    return
  }
  query.value = ''
  validation.value = ''
  void submit(text, { mode: mode.value, webSearch: webSearch.value })
}

function onKeydown(event) {
  // 中文输入法确认候选时不发送；Shift + Enter 保留换行。
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    submitChat()
  }
}

watch(() => [messages.value.length, messages.value.at(-1)?.content, pending.value, error.value], async () => {
  await nextTick()
  const panel = conversation.value
  if (panel && followOutput) panel.scrollTop = panel.scrollHeight
})

onBeforeUnmount(() => { statusController?.abort(); dispose() })
</script>

<template>
  <section class="ai-assistant" aria-labelledby="ai-assistant-title">
    <div class="section-heading ai-assistant-heading">
      <div>
        <h2 id="ai-assistant-title">科创 AI 助手</h2>
      </div>
      <span class="editorial-label">赛事 · 科研 · 资源</span>
    </div>
    <p class="ai-assistant-intro">选择关注方向，问比赛、科研机会或学习资源；也可以在赛事模式使用完整的选赛与找队友向导。</p>
    <div class="ai-mode-list" role="group" aria-label="助手模式">
      <button v-for="option in modeOptions" :key="option.value" type="button" class="ai-mode-button"
        :class="{ 'is-active': mode === option.value }" :aria-pressed="mode === option.value"
        :disabled="pending" @click="changeMode(option.value)">{{ option.label }}</button>
    </div>
    <div v-if="statusLoading" class="home-state" role="status">正在加载查询工具…</div>
    <div v-else-if="statusError" class="home-state" role="alert">查询工具暂时无法加载。<button class="text-button" @click="loadStatus">重试</button></div>
    <CatalogSearch v-else-if="!configured" />
    <div v-else class="ai-assistant-panel">
      <div v-if="messages.length" ref="conversation" class="ai-conversation" role="log" aria-label="当前对话" aria-live="polite" :aria-busy="pending" tabindex="0" @scroll="onConversationScroll">
        <article v-for="(message, index) in messages" :key="index" class="ai-chat-message" :class="{ 'is-user': message.role === 'user' }">
          <strong>{{ message.role === 'user' ? '你' : '创享 AI' }}</strong>
          <p v-if="message.role === 'user'">{{ message.content }}</p>
          <div v-else-if="message.content" class="ai-chat-markdown" v-html="renderAIMessage(message)"></div>
          <p v-else-if="message.generating" class="ai-chat-status">{{ phase === 'retrieving' ? '正在查找资料…' : '正在生成回答…' }}</p>
          <small v-if="message.incomplete" class="ai-chat-coverage">回答未完成，可重试。</small>
          <div v-if="message.sources?.length" class="ai-chat-sources" aria-label="回答来源">
            <span>参考来源</span>
            <ol>
              <li v-for="source in message.sources" :key="source.id">
                <RouterLink v-if="source.internal_url" :to="source.internal_url">[{{ source.id }}] {{ source.title }}</RouterLink>
                <a v-else :href="source.url" target="_blank" rel="noopener noreferrer">[{{ source.id }}] {{ source.title }}</a>
                <small v-if="!['research_opportunity', 'research_group'].includes(source.kind)">{{ source.published_on ? `发布 ${source.published_on}` : source.verified_at ? `核查 ${source.verified_at.slice(0, 10)}` : source.read_at ? `读取 ${source.read_at.slice(0, 10)}` : '日期未注明' }}</small>
                <small v-if="source.status_note">{{ source.status_note }}</small>
                <small v-if="source.trust_label && !['research_opportunity', 'research_group'].includes(source.kind)">{{ source.trust_label }}{{ source.reviewed ? ' · 已核验' : ' · 未经人工核验' }}</small>
                <a v-if="source.internal_url" :href="source.url" target="_blank" rel="noopener noreferrer">外部原文</a>
              </li>
            </ol>
          </div>
          <div v-if="message.recommendations?.length" class="ai-chat-sources" aria-label="相关推荐">
            <strong>相关推荐</strong>
            <ul>
              <li v-for="(item, itemIndex) in message.recommendations" :key="itemIndex">
                <span>{{ itemIndex + 1 }}. {{ { competition: '赛事', resource: '资源', research_opportunity: '科研资料', research_group: '课题组' }[item.object_type] }} · </span>
                <a :href="item.source_url" target="_blank" rel="noopener noreferrer">{{ item.title }}</a>
                <template v-if="item.object_type === 'research_opportunity' && Object.keys(item.facts || {}).length">
                  <template v-for="[field, label] in researchFields" :key="field">
                    <small v-if="item.facts[field]">{{ label }}：{{ item.facts[field] }} <ResearchFieldLinks :links="item.field_links[field]" :context="`${item.title} · ${label}`" /></small>
                  </template>
                  <small v-if="item.field_links.recruitment?.length">招募信息：<ResearchFieldLinks :links="item.field_links.recruitment" /></small>
                  <a :href="item.source_url" target="_blank" rel="noopener noreferrer">官方说明 ↗</a>
                </template>
                <small v-else>{{ item.reason }} · {{ item.reviewed ? '站内已核验' : '站内公开' }}</small>
                <small v-if="item.status_note">{{ item.status_note }}</small>
                <small v-if="item.research_group_label && item.object_type !== 'research_opportunity'">课题组：{{ item.research_group_label }}</small>
                <small v-if="item.related_resources?.length">相关资源：<a v-for="(resource, resourceIndex) in item.related_resources" :key="resourceIndex"
                  :href="resource.source_url" target="_blank" rel="noopener noreferrer">{{ resource.title }}{{ resourceIndex < item.related_resources.length - 1 ? '、' : '' }}</a></small>
              </li>
            </ul>
          </div>
          <small v-if="!message.sources?.length && ['no_approved_knowledge', 'no_published_knowledge'].includes(message.retrieval?.knowledge)" class="ai-chat-coverage">暂无可引用的站内资料。</small>
          <small v-if="!message.sources?.length && ['registered_site_not_matched', 'official_site_unavailable', 'official_page_not_a_notice'].includes(message.retrieval?.web)" class="ai-chat-coverage">这次未找到可用的官网通知。目前只查询已登记的官网。</small>
        </article>
        <p v-if="pending" class="ai-chat-status" role="status">{{ phase === 'retrieving' ? '正在查找资料…' : '正在生成回答…' }} <button type="button" class="text-button" @click="stop">停止生成</button></p>
        <div v-if="error" class="ai-chat-error" role="alert">
          <p>{{ error }}</p>
          <button v-if="failed" class="action-button secondary" type="button" :disabled="pending" @click="submit('', { retry: true, mode, webSearch })">重试这条消息</button>
        </div>
      </div>
      <form class="ai-assistant-form" aria-label="科创 AI 对话" @submit.prevent="submitChat">
        <label for="ai-competition-query">你的问题</label>
        <textarea
          id="ai-competition-query"
          v-model="query"
          maxlength="2000"
          :disabled="pending"
          rows="3"
          :placeholder="mode === 'research' ? '例如：介绍一下人机交互实验室的研究方向和成果；有哪些可兼职的科研助理机会？' : '例如：我是大二学生，会一点 Python，可以参加哪些比赛？需要怎么准备？'"
          :aria-invalid="Boolean(validation)"
          :aria-describedby="validation ? 'ai-query-validation' : undefined"
          @input="validation = ''"
          @keydown="onKeydown"
        />
        <div class="ai-assistant-actions">
          <div class="ai-example-list" aria-label="快捷输入">
            <span>试试：</span>
            <button v-for="example in examples" :key="example" type="button" class="ai-example" :disabled="pending" @click="addExample(example)">
              {{ example }}
            </button>
          </div>
          <div class="ai-send-controls">
            <button type="button" class="ai-web-toggle" aria-label="联网搜索" :class="{ 'is-active': webSearch }"
              :aria-pressed="webSearch" :disabled="pending" @click="webSearch = !webSearch">联网搜索</button>
            <button class="action-button ai-submit" type="submit" :disabled="pending || !query.trim()">
              <AppIcon name="spark" :size="17" />{{ pending ? '正在回复…' : '发送' }}
            </button>
          </div>
        </div>
        <p v-if="validation" id="ai-query-validation" class="form-error" role="alert">{{ validation }}</p>
      </form>
      <p class="ai-demo-note">回答按需参考站内资料与站外原文，来源状态会单独标注。Enter 发送，Shift + Enter 换行。切换模式会开始新对话。</p>
    </div>
    <details v-if="mode === 'competition'" class="ai-guide-details">
      <summary>打开赛事向导：选赛事、分析条件、找队友</summary>
      <CompetitionGuide />
    </details>
  </section>
</template>

<style scoped>
.ai-conversation {
  max-height: 480px;
  overflow-y: auto;
  overscroll-behavior: contain;
  display: grid;
  gap: 20px;
  color: var(--text-primary, #f4f2ee);
}
.ai-chat-message { min-width: 0; }
.ai-chat-message strong { color: var(--text-secondary, #a4b1c0); font-size: var(--type-small); }
.ai-chat-message p { margin: 8px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: var(--leading-body); }
.ai-chat-markdown { margin-top: 8px; overflow-wrap: anywhere; line-height: var(--leading-body); }
.ai-chat-markdown :deep(p) { margin: 0 0 10px; }
.ai-chat-markdown :deep(p:last-child) { margin-bottom: 0; }
.ai-chat-markdown :deep(a) { color: var(--accent, #6da5ff); }
.ai-chat-markdown :deep(pre) { overflow-x: auto; }
.ai-chat-message.is-user { padding-left: 16px; border-left: 2px solid var(--accent, #6da5ff); }
.ai-chat-status { margin: 0; color: var(--text-secondary, #a4b1c0); }
.ai-chat-error p { margin: 0 0 12px; }
.ai-chat-sources { margin-top: 12px; padding: 12px; border: 1px solid var(--border, #344357); border-radius: 8px; font-size: var(--type-small); }
.ai-chat-sources ol { margin: 8px 0 0; padding-left: 22px; }
.ai-chat-sources li { margin: 7px 0; overflow-wrap: anywhere; }
.ai-chat-sources small { display: block; color: var(--text-secondary, #a4b1c0); }
.ai-chat-sources a { color: var(--accent, #6da5ff); }
.ai-chat-coverage { display: block; margin-top: 8px; color: var(--text-secondary, #a4b1c0); }
.ai-mode-list { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; }
.ai-mode-button { border: 1px solid var(--border, #344357); border-radius: 999px; padding: 8px 18px; color: var(--text-primary, #f4f2ee); background: transparent; font: inherit; cursor: pointer; }
.ai-mode-button.is-active { color: var(--bg-primary, #101a24); background: var(--text-primary, #f4f2ee); }
.ai-mode-button:disabled { opacity: .55; cursor: not-allowed; }
.ai-send-controls { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-shrink: 0; }
.ai-web-toggle { border: 1px solid var(--border, #344357); border-radius: 999px; padding: 7px 14px; font: inherit; color: var(--text-primary, #f4f2ee); background: transparent; cursor: pointer; white-space: nowrap; }
.ai-web-toggle.is-active { border-color: var(--accent, #6da5ff); color: var(--accent, #6da5ff); }
.ai-web-toggle:disabled { opacity: .55; cursor: not-allowed; }
.ai-guide-details { margin-top: 24px; border-top: 1px solid var(--border, #344357); padding-top: 18px; }
.ai-guide-details summary { cursor: pointer; }
</style>
