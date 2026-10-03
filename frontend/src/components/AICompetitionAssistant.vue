<script setup>
import { onBeforeUnmount, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import CompetitionCard from './CompetitionCard.vue'
import { searchCompetitionsByAI } from '../services/aiCompetitionSearch.js'

const examples = ['近期可报名', 'AI 相关', '适合大二学生', '科研创新类']
const query = ref('')
const phase = ref('idle')
const response = ref(null)
const validation = ref('')
let controller
let requestNumber = 0

function addExample(example) {
  const current = query.value.trim()
  if (!current.includes(example)) query.value = current ? `${current}，${example}` : example
  validation.value = ''
}

async function submitSearch() {
  const text = query.value.trim()
  if (!text) {
    requestNumber++
    controller?.abort()
    phase.value = 'idle'
    response.value = null
    validation.value = '请先描述你想参加的竞赛。'
    return
  }
  const request = ++requestNumber
  controller?.abort()
  controller = new AbortController()
  validation.value = ''
  phase.value = 'loading'
  response.value = null
  try {
    const data = await searchCompetitionsByAI(text, { signal: controller.signal })
    if (request !== requestNumber) return
    response.value = data
    phase.value = 'success'
  } catch (error) {
    if (request !== requestNumber || error.name === 'AbortError') return
    phase.value = 'error'
  }
}

onBeforeUnmount(() => {
  requestNumber++
  controller?.abort()
})
</script>

<template>
  <section class="ai-assistant" aria-labelledby="ai-assistant-title">
    <div class="section-heading ai-assistant-heading">
      <div>
        <h2 id="ai-assistant-title">不知道参加什么？<br /><span>告诉我你会什么。</span></h2>
      </div>
      <span class="editorial-label">前端功能演示</span>
    </div>
    <p class="ai-assistant-intro">把你的专业、技能和兴趣写下来，从一个方向开始探索。</p>
    <div class="ai-assistant-panel">
      <form class="ai-assistant-form" role="search" aria-label="AI 竞赛搜索" @submit.prevent="submitSearch">
        <label for="ai-competition-query">你的参赛需求</label>
        <textarea
          id="ai-competition-query"
          v-model="query"
          maxlength="500"
          rows="3"
          placeholder="我是物理专业大二学生，会一点 Python，对人工智能感兴趣，希望找一个近期可以报名、适合组队的比赛……"
          :aria-invalid="Boolean(validation)"
          :aria-describedby="validation ? 'ai-query-validation' : undefined"
          @input="validation = ''"
        />
        <div class="ai-assistant-actions">
          <div class="ai-example-list" aria-label="快捷输入">
            <span>试试：</span>
            <button v-for="example in examples" :key="example" type="button" class="ai-example" @click="addExample(example)">
              {{ example }}
            </button>
          </div>
          <button class="action-button ai-submit" type="submit">
            <AppIcon name="search" :size="17" />AI 搜索
          </button>
        </div>
        <p v-if="validation" id="ai-query-validation" class="form-error" role="alert">{{ validation }}</p>
      </form>
      <p class="ai-demo-note">当前为模拟匹配，以下赛事均为虚构演示数据；报名状态和参赛资格不代表真实赛事。</p>
    </div>

    <div v-if="phase === 'loading'" class="state-panel ai-search-state" role="status" aria-live="polite">
      正在理解你的需求……
    </div>
    <div v-else-if="phase === 'error'" class="state-panel ai-search-state" role="alert">
      <p>模拟搜索暂时失败，请重试或换个描述。</p>
      <button class="action-button secondary" type="button" @click="submitSearch">重新搜索</button>
    </div>
    <div v-else-if="phase === 'success'" class="ai-search-results" aria-live="polite">
      <div class="ai-interpretation">
        <h3>AI 对需求的理解 <span>模拟解析</span></h3>
        <dl>
          <div><dt>专业</dt><dd>{{ response.interpretation.major || '未提及' }}</dd></div>
          <div><dt>年级</dt><dd>{{ response.interpretation.grade || '未提及' }}</dd></div>
          <div><dt>兴趣方向</dt><dd>{{ response.interpretation.interests.join('、') || '未提及' }}</dd></div>
          <div><dt>参赛形式</dt><dd>{{ response.interpretation.participationType === 'team' ? '希望组队' : response.interpretation.participationType === 'individual' ? '个人参加' : '未提及' }}</dd></div>
          <div><dt>报名状态</dt><dd>{{ response.interpretation.registrationStatus === 'open' ? '希望报名截止未到' : '未提及' }}</dd></div>
        </dl>
      </div>
      <h3 class="ai-result-count">为你找到 {{ response.results.length }} 个相关赛事 <span>本地模拟结果</span></h3>
      <div v-if="!response.results.length" class="state-panel ai-search-state" role="status">
        <p>没有找到符合这段描述的演示赛事。</p>
        <p>可以换个方向，或点击上方快捷输入后重新搜索。</p>
      </div>
      <div v-else class="competition-grid ai-result-list">
        <div v-for="result in response.results" :key="result.competition.id" class="ai-result-item">
          <CompetitionCard
            :competition="result.competition"
            :detail-enabled="Number.isSafeInteger(result.competition.id) && result.competition.id > 0"
          />
          <p class="ai-match-reason"><AppIcon name="spark" :size="15" /><span>匹配理由：{{ result.matchReason }}</span></p>
        </div>
      </div>
    </div>
    <button class="text-button ai-error-demo" type="button" @click="query = '模拟错误'; submitSearch()">
      体验模拟错误状态
    </button>
  </section>
</template>
