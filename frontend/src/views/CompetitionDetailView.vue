<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getCompetition } from '../api/competitions'
import { formatDate, formatDeadline, formatUpdatedAt, levelLabels, participationLabels, safeExternalUrl } from '../utils/competition'

const route = useRoute()
const item = ref(null)
const loading = ref(false)
const error = ref('')
let controller
let requestNumber = 0

async function load() {
  const request = ++requestNumber
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  item.value = null
  try {
    const data = await getCompetition(route.params.id, controller.signal)
    if (request === requestNumber) item.value = data
  } catch (err) {
    if (request !== requestNumber || err.code === 'ERR_CANCELED') return
    error.value = err.response?.status === 404 ? '这项赛事不存在或已下架。' : '暂时无法加载赛事详情，请稍后重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => { requestNumber++; controller?.abort() })
</script>

<template>
  <section class="detail-page" aria-labelledby="detail-title">
    <RouterLink class="back-link" :to="{ name: 'competitions', query: route.query }">← 返回赛事列表</RouterLink>
    <div v-if="loading" class="state-panel" role="status">正在加载赛事详情…</div>
    <div v-else-if="error" class="state-panel" role="alert">
      <p>{{ error }}</p><button class="action-button secondary" @click="load">重新加载</button>
    </div>
    <template v-else-if="item">
      <header class="page-heading">
        <div class="tag-row"><span v-if="item.category" class="tag">{{ item.category.name }}</span><span class="tag neutral">{{ item.edition }}</span></div>
        <h1 id="detail-title">{{ item.title }}</h1>
        <p>{{ item.summary || '简介待补充' }}</p>
      </header>
      <el-card class="detail-section" shadow="never">
        <h2>赛事信息</h2>
        <dl class="detail-facts">
          <div><dt>主办方</dt><dd>{{ item.organizer || '未注明' }}</dd></div>
          <div><dt>赛事范围</dt><dd>{{ levelLabels[item.level] || '未注明' }}</dd></div>
          <div><dt>参赛形式</dt><dd>{{ participationLabels[item.participation_type] || '未说明' }}</dd></div>
          <div><dt>团队人数</dt><dd v-if="item.team_size_min != null || item.team_size_max != null">{{ item.team_size_min ?? '下限未注明' }} — {{ item.team_size_max ?? '上限未注明' }} 人</dd><dd v-else>未注明</dd></div>
          <div><dt>报名截止</dt><dd>{{ formatDeadline(item, 'registration_deadline') }}</dd></div>
          <div><dt>作品提交截止</dt><dd>{{ formatDeadline(item, 'submission_deadline') }}</dd></div>
          <div><dt>校内截止</dt><dd>{{ formatDeadline(item, 'campus_deadline') }}</dd></div>
        </dl>
        <p v-if="item.deadline_notes" class="notice-text preserve-lines">{{ item.deadline_notes }}</p>
        <p class="muted">未注明的日期或时刻请查阅官方原文，报名和提交时间可能不同。</p>
      </el-card>
      <el-card class="detail-section" shadow="never">
        <h2>赛事介绍</h2><p class="preserve-lines">{{ item.description || '暂无详细介绍，请查看通知原文。' }}</p>
        <template v-for="section in [{ field: 'tracks', title: '赛道说明' }, { field: 'eligibility', title: '参赛资格' }, { field: 'registration_method', title: '报名方式' }, { field: 'campus_arrangements', title: '校内安排' }]" :key="section.field">
          <h3>{{ section.title }}</h3><p class="preserve-lines">{{ item[section.field] || '未注明' }}</p>
        </template>
        <a v-if="safeExternalUrl(item.registration_url)" class="action-button inline-button" :href="safeExternalUrl(item.registration_url)" target="_blank" rel="noopener noreferrer">前往官方报名入口 ↗</a>
      </el-card>
      <el-card class="detail-section" shadow="never">
        <h2>信息来源</h2>
        <ul v-if="item.sources?.length" class="source-list">
          <li v-for="source in item.sources" :key="source.id">
            <a v-if="safeExternalUrl(source.source_url)" :href="safeExternalUrl(source.source_url)" target="_blank" rel="noopener noreferrer">{{ source.source_name || '通知原文' }} ↗</a>
            <span v-else>{{ source.source_name || '来源网址待核实' }}</span>
            <span class="muted">原文发布日期：{{ formatDate(source.source_published_on) }}</span>
          </li>
        </ul>
        <p v-else class="muted">暂无可展示的来源。</p>
        <p class="timestamp">信息更新：{{ formatUpdatedAt(item.updated_at) }}<br />最近核验：{{ formatUpdatedAt(item.last_verified_at) }}</p>
      </el-card>
    </template>
  </section>
</template>
