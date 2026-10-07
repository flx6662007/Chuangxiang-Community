<script setup>
import { onBeforeUnmount, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import CatalogCard from './CatalogCard.vue'
import { searchCompetitionsByAI } from '../services/aiCompetitionSearch.js'

const examples = ['人工智能', '机器人', '数学建模', '创新创业']
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
    validation.value = '请输入赛事名称或关键词。'
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
    if (request !== requestNumber || error.name === 'AbortError' || error.code === 'ERR_CANCELED') return
    phase.value = 'error'
  }
}

onBeforeUnmount(() => {
  requestNumber++
  controller?.abort()
})
</script>

<template>
  <section class="ai-assistant" aria-labelledby="catalog-search-title">
    <div class="section-heading ai-assistant-heading">
      <div>
        <h2 id="catalog-search-title">查阅比赛资料</h2>
      </div>
      <span class="editorial-label">关键词搜索</span>
    </div>
    <p class="ai-assistant-intro">输入赛事名称、技能或方向，查找已收录的赛事和学习资料。</p>
    <div class="ai-assistant-panel">
      <form class="ai-assistant-form" role="search" aria-label="赛事资料搜索" @submit.prevent="submitSearch">
        <label for="catalog-search-query">赛事名称或关键词</label>
        <textarea
          id="catalog-search-query"
          v-model="query"
          maxlength="500"
          rows="3"
          placeholder="例如：人工智能、机器人、Python、数学建模……"
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
            <AppIcon name="search" :size="17" />搜索赛事
          </button>
        </div>
        <p v-if="validation" id="ai-query-validation" class="form-error" role="alert">{{ validation }}</p>
      </form>
      <p class="ai-demo-note">按关键词搜索赛事名称和正文，打开结果查看通知与资料。</p>
    </div>

    <div v-if="phase === 'loading'" class="state-panel ai-search-state" role="status" aria-live="polite">
      正在检索资料库…
    </div>
    <div v-else-if="phase === 'error'" class="state-panel ai-search-state" role="alert">
      <p>暂时无法完成检索，请重试。</p>
      <button class="action-button secondary" type="button" @click="submitSearch">重新搜索</button>
    </div>
    <div v-else-if="phase === 'success'" class="ai-search-results" aria-live="polite">
      <div class="ai-interpretation">
        <h3>检索关键词</h3>
        <p>{{ response.keywords.join('、') || '请使用赛事名称或研究方向' }}</p>
      </div>
      <h3 class="ai-result-count">找到 {{ response.count }} 项相关赛事 <span v-if="response.count > response.results.length">展示前 {{ response.results.length }} 项</span></h3>
      <div v-if="!response.results.length" class="state-panel ai-search-state" role="status">
        <p>没有找到相关赛事资料。</p>
        <p>试试其他关键词，或点击上方示例再搜一次。</p>
      </div>
      <div v-else class="competition-grid ai-result-list">
        <div v-for="result in response.results" :key="result.catalog.code" class="ai-result-item">
          <CatalogCard :item="result.catalog" />
          <p class="ai-match-reason"><AppIcon name="spark" :size="15" /><span>{{ result.match_reason }}</span></p>
        </div>
      </div>
    </div>
  </section>
</template>
