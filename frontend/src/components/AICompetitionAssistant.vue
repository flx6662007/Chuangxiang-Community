<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { getAIStatus, requestAIChat } from '../api/ai'
import { useAIChat } from '../composables/useAIChat.js'
import CatalogSearch from './CatalogSearch.vue'
import CompetitionGuide from './CompetitionGuide.vue'

const examples = ['竞赛入门', 'AI 相关', '适合大二学生', '科研创新类']
const query = ref('')
const validation = ref('')
const conversation = ref(null)
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
const { messages, pending, error, failed, submit, dispose } = useAIChat(requestAIChat)

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
  void submit(text)
}

function onKeydown(event) {
  // 中文输入法确认候选时不发送；Shift + Enter 保留换行。
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    submitChat()
  }
}

watch(() => [messages.value.length, pending.value, error.value], async () => {
  await nextTick()
  const panel = conversation.value
  if (panel) panel.scrollTop = panel.scrollHeight
})

onBeforeUnmount(() => { statusController?.abort(); dispose() })
</script>

<template>
  <CompetitionGuide />
  <details class="general-chat"><summary>其他科研与学习问题</summary>
  <div v-if="statusLoading" class="home-state" role="status">正在加载查询工具…</div>
  <div v-else-if="statusError" class="home-state" role="alert">查询工具暂时无法加载。<button class="text-button" @click="loadStatus">重试</button></div>
  <CatalogSearch v-else-if="!configured" />
  <section v-else class="ai-assistant" aria-labelledby="ai-assistant-title">
    <div class="section-heading ai-assistant-heading">
      <div>
        <h2 id="ai-assistant-title">竞赛和科研问题，<br /><span>问问 AI 助手</span></h2>
      </div>
      <span class="editorial-label">科创 AI 助手</span>
    </div>
    <p class="ai-assistant-intro">可以问比赛怎么选、如何准备，也可以说说你的专业和经验。</p>
    <div class="ai-assistant-panel">
      <div v-if="messages.length" ref="conversation" class="ai-conversation" role="log" aria-label="当前对话" aria-live="polite" :aria-busy="pending" tabindex="0">
        <article v-for="(message, index) in messages" :key="index" class="ai-chat-message" :class="{ 'is-user': message.role === 'user' }">
          <strong>{{ message.role === 'user' ? '你' : '创享 AI' }}</strong>
          <p>{{ message.content }}</p>
          <div v-if="message.sources?.length" class="ai-chat-sources" aria-label="回答来源">
            <span>参考来源</span>
            <ol>
              <li v-for="source in message.sources" :key="source.id">
                <RouterLink v-if="source.internal_url" :to="source.internal_url">[{{ source.id }}] {{ source.title }}</RouterLink>
                <a v-else :href="source.url" target="_blank" rel="noopener noreferrer">[{{ source.id }}] {{ source.title }}</a>
                <small>{{ source.published_on ? `发布 ${source.published_on}` : source.verified_at ? `核查 ${source.verified_at.slice(0, 10)}` : source.read_at ? `读取 ${source.read_at.slice(0, 10)}` : '日期未注明' }}</small>
                <small v-if="source.status_note">{{ source.status_note }}</small>
                <a v-if="source.internal_url" :href="source.url" target="_blank" rel="noopener noreferrer">官方原文</a>
              </li>
            </ol>
          </div>
          <small v-if="['no_approved_knowledge', 'no_published_knowledge'].includes(message.retrieval?.knowledge)" class="ai-chat-coverage">暂无可引用的站内资料。</small>
          <small v-if="['registered_site_not_matched', 'official_site_unavailable', 'official_page_not_a_notice'].includes(message.retrieval?.web)" class="ai-chat-coverage">这次未找到可用的官网通知。目前只查询已登记的官网。</small>
        </article>
        <p v-if="pending" class="ai-chat-status" role="status">正在回复…</p>
        <div v-if="error" class="ai-chat-error" role="alert">
          <p>{{ error }}</p>
          <button v-if="failed" class="action-button secondary" type="button" :disabled="pending" @click="submit('', { retry: true })">重试这条消息</button>
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
          placeholder="例如：我是大二学生，会一点 Python，可以参加哪些比赛？需要怎么准备？"
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
          <button class="action-button ai-submit" type="submit" :disabled="pending || !query.trim()">
            <AppIcon name="spark" :size="17" />{{ pending ? '正在回复…' : '发送' }}
          </button>
        </div>
        <p v-if="validation" id="ai-query-validation" class="form-error" role="alert">{{ validation }}</p>
      </form>
      <p class="ai-demo-note">回答参考站内资料和已登记的官网页面，请以官方原文为准。Enter 发送，Shift + Enter 换行。对话仅在当前页面保留，最多参考最近 20 轮（约 6 万字符）。</p>
    </div>

  </section>
  </details>
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
.ai-chat-message.is-user { padding-left: 16px; border-left: 2px solid var(--accent, #6da5ff); }
.ai-chat-status { margin: 0; color: var(--text-secondary, #a4b1c0); }
.ai-chat-error p { margin: 0 0 12px; }
.ai-chat-sources { margin-top: 12px; padding: 12px; border: 1px solid var(--border, #344357); border-radius: 8px; font-size: var(--type-small); }
.ai-chat-sources ol { margin: 8px 0 0; padding-left: 22px; }
.ai-chat-sources li { margin: 7px 0; overflow-wrap: anywhere; }
.ai-chat-sources small { display: block; color: var(--text-secondary, #a4b1c0); }
.ai-chat-sources a { color: var(--accent, #6da5ff); }
.ai-chat-coverage { display: block; margin-top: 8px; color: var(--text-secondary, #a4b1c0); }
</style>
