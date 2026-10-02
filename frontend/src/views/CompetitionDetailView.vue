<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getCompetition } from '../api/competitions'
import AppIcon from '../components/AppIcon.vue'
import DeadlineStatusBadge from '../components/DeadlineStatusBadge.vue'
import ReportPanel from '../components/ReportPanel.vue'
import {
  formatDate,
  formatDeadline,
  formatUpdatedAt,
  levelLabels,
  participationLabels,
  safeExternalUrl,
  officialText,
  officialUnknown,
  teamSizeLabel,
  competitionOfficialLink,
} from '../utils/competition'

const route = useRoute()
const item = ref(null)
const loading = ref(false)
const error = ref('')
const officialLink = computed(() => item.value ? competitionOfficialLink(item.value) : null)
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
    error.value =
      err.response?.status === 404
        ? '这项赛事不存在或已下架。'
        : '暂时无法加载赛事详情，请稍后重试。'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}

watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => {
  requestNumber++
  controller?.abort()
})
</script>

<template>
  <section class="detail-page" aria-labelledby="detail-title">
    <RouterLink
      class="back-link"
      :to="{ name: 'competitions', query: route.query }"
      >← 信息中心 · 赛事讯息<span>/</span>赛事详情</RouterLink
    >
    <div v-if="loading" class="state-panel" role="status">
      正在加载赛事详情…
    </div>
    <div v-else-if="error" class="state-panel" role="alert">
      <p>{{ error }}</p>
      <button class="action-button secondary" @click="load">重新加载</button>
    </div>
    <template v-else-if="item">
      <header class="detail-hero">
        <span class="detail-emblem"><AppIcon name="trophy" :size="40" /></span>
        <div class="detail-hero-copy">
          <h1 id="detail-title">{{ item.title }}</h1>
          <div class="tag-row">
            <span v-if="item.category" class="tag">{{
              item.category.name
            }}</span
            ><span class="tag warm">{{
              item.level === 'unknown' ? officialUnknown : levelLabels[item.level] || officialUnknown
            }}</span
            ><span class="tag neutral">{{ item.edition }}</span>
          </div>
          <p><DeadlineStatusBadge :competition="item" /></p>
          <p>{{ officialText(item.summary) }}</p>
        </div>
        <a
          v-if="officialLink"
          class="action-button detail-hero-action"
          :href="officialLink.url"
          target="_blank"
          rel="noopener noreferrer"
          >{{ officialLink.label }} ↗</a
        >
      </header>
      <div class="detail-layout">
        <div class="detail-main">
          <nav class="detail-tabs" aria-label="赛事详情内容">
            <a href="#introduction">赛事介绍</a
            ><a href="#requirements">参赛要求</a
            ><a href="#arrangements">报名与提交</a
            ><a href="#sources">信息来源</a>
          </nav>
          <el-card class="detail-section" shadow="never">
            <section id="introduction">
              <h2>赛事介绍</h2>
              <p class="preserve-lines">
                {{ officialText(item.description) }}
              </p>
              <h3>赛道说明</h3>
              <p class="preserve-lines">{{ officialText(item.tracks) }}</p>
            </section>
          </el-card>
          <el-card class="detail-section" shadow="never">
            <section id="requirements">
              <h2>参赛要求</h2>
              <h3>参赛资格</h3>
              <p class="preserve-lines">{{ officialText(item.eligibility) }}</p>
              <dl class="detail-facts">
                <div>
                  <dt>参赛形式</dt>
                  <dd>
                    {{
                      item.participation_type === 'unknown' ? officialUnknown : participationLabels[item.participation_type] || officialUnknown
                    }}
                  </dd>
                </div>
                <div>
                  <dt>参赛人数</dt>
                  <dd>{{ teamSizeLabel(item) }}</dd>
                </div>
              </dl>
            </section>
          </el-card>
          <el-card class="detail-section" shadow="never">
            <section id="arrangements">
              <h2>报名与提交</h2>
              <h3>报名方式</h3>
              <p class="preserve-lines">
                {{ officialText(item.registration_method) }}
              </p>
              <p v-if="safeExternalUrl(item.registration_url)">
                <a :href="officialLink.url" target="_blank" rel="noopener noreferrer">
                  {{ officialLink.label }} ↗
                </a>
              </p>
              <p v-else class="muted">暂未收录独立报名网址，请按原文中的报名方式办理。</p>
              <dl class="detail-facts">
                <div>
                  <dt>报名截止日期</dt>
                  <dd>{{ formatDeadline(item, 'registration_deadline') }}</dd>
                </div>
                <div>
                  <dt>作品提交截止日期</dt>
                  <dd>{{ formatDeadline(item, 'submission_deadline') }}</dd>
                </div>
                <div>
                  <dt>校内截止日期</dt>
                  <dd>{{ formatDeadline(item, 'campus_deadline') }}</dd>
                </div>
              </dl>
              <h3>时间说明</h3>
              <p class="notice-text preserve-lines">{{ officialText(item.deadline_notes) }}</p>
              <p class="muted">报名、作品提交和校内选拔可能使用不同期限。只有日期而没有完整时区信息时，具体时刻以官方原文为准；截止尚未到不代表报名已经开放。</p>
              <h3>校内安排</h3>
              <p class="preserve-lines">
                {{ officialText(item.campus_arrangements) }}
              </p>
            </section>
          </el-card>
          <el-card id="sources" class="detail-section" shadow="never"
            ><h2>信息来源</h2>
            <ul v-if="item.sources?.length" class="source-list">
              <li v-for="source in item.sources" :key="source.id">
                <a
                  v-if="safeExternalUrl(source.source_url)"
                  :href="safeExternalUrl(source.source_url)"
                  target="_blank"
                  rel="noopener noreferrer"
                  ><AppIcon name="link" :size="14" />
                  {{ source.source_name || '通知原文' }} ↗</a
                ><span v-else>{{ source.source_name || '来源网址待核实' }}</span
                ><span class="muted"
                  >原文发布日期：{{
                    source.source_published_on ? formatDate(source.source_published_on) : officialUnknown
                  }}</span
                >
                <span v-if="source.source_updated_on" class="muted">原文更新日期：{{ formatDate(source.source_updated_on) }}</span>
                <span class="muted">该来源最近核验：{{ source.last_verified_at ? formatUpdatedAt(source.last_verified_at) : '尚未记录' }}</span>
              </li>
            </ul>
            <p v-else class="muted">暂无可展示的已核验来源。</p>
            <p class="timestamp">
              平台内容更新：{{ formatUpdatedAt(item.updated_at) }}<br />最近核验：{{
                item.last_verified_at ? formatUpdatedAt(item.last_verified_at) : '尚未记录'
              }}
            </p></el-card
          >
        </div>
        <aside class="detail-sidebar">
          <section class="team-panel">
            <h2>寻找参赛伙伴</h2>
            <p>查看本届赛事招募，或以固定模板发起组队。</p>
            <div class="stack-links">
              <RouterLink
                class="action-button"
                :to="{ name: 'teams', query: { competition_id: item.id } }"
                >查看本赛事招募</RouterLink
              ><RouterLink
                v-if="item.is_recruitment_open"
                :to="{
                  name: 'recruitment-publish',
                  query: { competition_id: item.id },
                }"
                >为本赛事发布招募 →</RouterLink
              >
              <p v-else class="muted">本赛事当前未开放平台招募。</p>
              <p v-if="item.is_recruitment_open && item.recruitment_deadline" class="muted">平台招募截止：{{ formatUpdatedAt(item.recruitment_deadline) }}。此期限用于站内组队，不代替官方报名期限。</p>
            </div>
          </section>
          <el-card class="detail-section" shadow="never"
            ><h2><AppIcon name="calendar" :size="21" /> 赛事信息</h2>
            <dl class="detail-facts">
              <div>
                <dt>主办方</dt>
                <dd class="preserve-lines">{{ officialText(item.organizer) }}</dd>
              </div>
              <div>
                <dt>赛事范围</dt>
                <dd>{{ item.level === 'unknown' ? officialUnknown : levelLabels[item.level] || officialUnknown }}</dd>
              </div>
              <div>
                <dt>年度 / 届次</dt>
                <dd>{{ officialText(item.edition) }}</dd>
              </div>
              <div>
                <dt>赛事分类</dt>
                <dd>{{ item.category?.name || officialUnknown }}</dd>
              </div>
              <div>
                <dt>当前时效</dt>
                <dd><DeadlineStatusBadge :competition="item" /></dd>
              </div>
            </dl>
            <div v-if="item.tags?.length" class="tag-row">
              <span v-for="tag in item.tags" :key="tag.id" class="tag">{{ tag.name }}</span>
            </div></el-card
          >
          <ReportPanel target-type="competition" :target-id="item.id" />
          <div class="detail-quote">
            <AppIcon name="spark" :size="32" />
            <h3>好想法，<br />从一次尝试开始。</h3>
            <p>先了解规则，再选择适合自己的方向。</p>
          </div>
        </aside>
      </div>
    </template>
  </section>
</template>
