<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { listCompetitions } from '../api/competitions'
import { listRecruitments } from '../api/teams'
import { listResearch, listNewsletters } from '../api/editorial'
import { summaryDeadline, levelLabels, safeExternalUrl, deadlineStatusLabel } from '../utils/competition'
import { label, optionNames } from '../utils/teams'
import { previewCompetitions, previewRecruitments } from '../mocks/homeVisualPreview'
import AICompetitionAssistant from '../components/AICompetitionAssistant.vue'
import HomeDotField from '../components/HomeDotField.vue'
import HomeMarginMotif from '../components/HomeMarginMotif.vue'
import HomeLiquidLinks from '../components/HomeLiquidLinks.vue'
import { useHomeLineResponse } from '../composables/useHomeLineResponse'

const pageRoot = ref(null)
useHomeLineResponse(pageRoot)

const route = useRoute()
const isVisualPreview = computed(() => route.query.ui_preview === '1')
const items = ref(isVisualPreview.value ? previewCompetitions : [])
const loading = ref(!isVisualPreview.value)
const error = ref(false)
const recruitments = ref(isVisualPreview.value ? previewRecruitments : [])
const teamsLoading = ref(!isVisualPreview.value)
const teamsError = ref(false)
let competitionController
let teamController
let competitionRequest = 0, teamRequest = 0
const laboratories = ref([]), newsletters = ref([])
const researchLoading = ref(true), researchError = ref(false)
const newslettersLoading = ref(true), newslettersError = ref(false), newslettersCount = ref(0)
const newslettersPage = ref(1), newsletterSearch = ref(''), newsletterSearchInput = ref('')
const editorialFeeds = {
  research: { api: listResearch, items: laboratories, loading: researchLoading, error: researchError, request: 0 },
  newsletters: { api: listNewsletters, items: newsletters, loading: newslettersLoading, error: newslettersError, request: 0 },
}

async function loadEditorial(kind) {
  const feed = editorialFeeds[kind]
  const request = ++feed.request
  feed.controller?.abort()
  feed.controller = new AbortController()
  feed.loading.value = true
  feed.error.value = false
  try {
    const params = kind === 'newsletters'
      ? { page_size: 3, page: newslettersPage.value, search: newsletterSearch.value }
      : { page_size: 3 }
    const data = await feed.api(params, feed.controller.signal)
    if (request !== feed.request) return
    feed.items.value = data.results
    if (kind === 'newsletters') newslettersCount.value = data.count
  } catch (err) {
    if (request === feed.request && err.code !== 'ERR_CANCELED') feed.error.value = true
  } finally {
    if (request === feed.request) feed.loading.value = false
  }
}
function searchNewsletters() {
  newsletterSearch.value = newsletterSearchInput.value.trim().slice(0, 200)
  newslettersPage.value = 1
  loadEditorial('newsletters')
}
function changeNewsletterPage(value) {
  newslettersPage.value = value
  loadEditorial('newsletters')
}

async function loadCompetitions() {
  const request = ++competitionRequest
  competitionController?.abort()
  competitionController = new AbortController()
  loading.value = true
  error.value = false
  try {
    const data = await listCompetitions(
      { page_size: 4, time_status: 'current' },
      competitionController.signal,
    )
    if (request !== competitionRequest || isVisualPreview.value) return
    if (!Array.isArray(data.results)) throw new Error('Invalid response')
    items.value = data.results
  } catch (err) {
    if (request === competitionRequest && !isVisualPreview.value && err.code !== 'ERR_CANCELED') error.value = true
  } finally {
    if (request === competitionRequest) loading.value = false
  }
}

async function loadTeams() {
  const request = ++teamRequest
  teamController?.abort()
  teamController = new AbortController()
  teamsLoading.value = true
  teamsError.value = false
  try {
    const data = await listRecruitments(
      { open_only: 'true', page_size: 2 },
      teamController.signal,
    )
    if (request !== teamRequest || isVisualPreview.value) return
    if (!Array.isArray(data.results)) throw new Error('Invalid response')
    recruitments.value = data.results
  } catch (err) {
    if (request === teamRequest && !isVisualPreview.value && err.code !== 'ERR_CANCELED') teamsError.value = true
  } finally {
    if (request === teamRequest) teamsLoading.value = false
  }
}

onMounted(() => {
  loadEditorial('research')
  loadEditorial('newsletters')
  if (!isVisualPreview.value) {
    loadCompetitions()
    loadTeams()
  }
})
watch(isVisualPreview, (preview) => {
  if (preview) {
    competitionRequest++
    teamRequest++
    competitionController?.abort()
    teamController?.abort()
    items.value = previewCompetitions
    recruitments.value = previewRecruitments
    loading.value = false
    teamsLoading.value = false
    error.value = false
    teamsError.value = false
  } else {
    items.value = []
    recruitments.value = []
    loadCompetitions()
    loadTeams()
  }
})
onBeforeUnmount(() => {
  competitionRequest++
  teamRequest++
  competitionController?.abort()
  teamController?.abort()
  Object.values(editorialFeeds).forEach(feed => { feed.request++; feed.controller?.abort() })
})
</script>

<template>
  <div ref="pageRoot" class="welcome">
    <HomeDotField />
    <div v-if="isVisualPreview" class="home-preview-banner" role="note"><span>界面预览</span>赛事与团队为前端占位内容，仅用于评估视觉。<RouterLink to="/">退出预览 ↗</RouterLink></div>
    <section class="home-dark home-opening" aria-labelledby="welcome-title">
      <div class="home-wrap">
        <div class="home-hero">
          <div class="hero-copy">
            <h1 id="welcome-title">在创新中相遇，<br />遇见<span>更大的可能</span></h1>
            <p class="hero-lead">查看比赛通知和科研项目，<br />了解报名与参与方式。</p>
          </div>
          <div class="hero-art hero-shortcuts"><HomeLiquidLinks /></div>
        </div>
        <div class="start-here" aria-labelledby="start-title">
          <div class="start-label"><span id="start-title">快速入口</span></div>
          <div class="start-links">
            <RouterLink :to="{ name: 'competitions' }"><span>赛事</span><strong>查看比赛通知</strong><span class="start-arrow">↗</span></RouterLink>
            <RouterLink :to="{ name: 'research-projects' }"><span>科研</span><strong>查看科研项目</strong><span class="start-arrow">↗</span></RouterLink>
            <RouterLink :to="{ name: 'teams' }"><span>组队</span><strong>查看组队招募</strong><span class="start-arrow">↗</span></RouterLink>
            <RouterLink :to="{ name: 'resources' }"><span>资源</span><strong>查找学习资料</strong><span class="start-arrow">↗</span></RouterLink>
          </div>
        </div>
      </div>
    </section>

    <div id="ai" class="home-dark home-ai"><div v-reveal class="home-wrap"><AICompetitionAssistant /></div></div>

    <section id="discover" class="home-light home-discover" aria-labelledby="discover-title">
      <div v-reveal class="home-wrap">
        <header class="home-section-heading">
          <div><h2 id="discover-title">近期比赛<br /><span>通知与报名信息</span></h2></div>
          <RouterLink class="home-more" :to="{ name: 'competitions' }">查看全部 <span>↗</span></RouterLink>
        </header>
        <p class="home-intro">{{ isVisualPreview ? '页面效果演示 · 以下为示例赛事。' : '查看报名时间、参赛要求和官方通知。' }}</p>
        <div v-if="loading" class="home-state" role="status">正在加载赛事…</div>
        <div v-else-if="error" class="home-state" role="alert">暂时无法加载赛事。<button type="button" @click="loadCompetitions">重新加载 ↗</button></div>
        <div v-else-if="!items.length" class="home-state">当前暂无未明确截止的赛事。<RouterLink :to="{ name: 'competitions' }">查看完整赛事目录 ↗</RouterLink></div>
        <div v-else class="discover-grid">
          <RouterLink v-for="(item, index) in items" :key="item.id" class="discover-item" :class="{ 'discover-feature': index === 0 }" :to="isVisualPreview ? { name: 'competitions' } : { name: 'competition-detail', params: { id: item.id } }">
            <div class="discover-top"><span>{{ item.category?.name || '赛事资讯' }}<template v-if="isVisualPreview"> · 占位</template></span><span>↗</span></div>
            <div class="discover-body"><p class="discover-level">{{ levelLabels[item.level] || '范围未注明' }} <span>/</span> {{ item.edition || '届次未注明' }}</p><h3>{{ item.title }}</h3></div>
            <div class="discover-bottom"><span>{{ isVisualPreview ? item.previewBadge : deadlineStatusLabel(item) }}</span><span>{{ isVisualPreview ? item.previewDate : `${summaryDeadline(item).label} · ${summaryDeadline(item).value}` }}</span></div>
          </RouterLink>
        </div>
      </div>
    </section>

    <section id="research" class="home-light home-research" aria-labelledby="research-title">
      <div v-reveal class="home-wrap motif-host">
        <HomeMarginMotif kind="star" />
        <header class="home-section-heading">
          <div><h2 id="research-title">科研项目<span>与参与方式</span></h2></div>
          <RouterLink class="home-more" :to="{ name: 'research-projects' }">查看全部 <span>↗</span></RouterLink>
        </header>
        <p class="home-intro">了解实验室在做什么，以及本科生如何参与。</p>
        <div v-if="researchLoading" class="home-state" role="status">正在加载科研线索…</div>
        <div v-else-if="researchError" class="home-state" role="alert">暂时无法加载科研线索。<button type="button" @click="loadEditorial('research')">重新加载 ↗</button></div>
        <div v-else-if="!laboratories.length" class="home-state">科研项目信息正在整理。</div>
        <div v-else class="research-list">
          <article v-for="item in laboratories.slice(0, 3)" :key="item.id" class="research-row">
            <div class="research-main"><h3>{{ item.title }}</h3><p>{{ item.summary }}</p><span>{{ item.participation }}</span></div>
            <div class="research-end"><span>{{ item.unit }}</span><span v-if="item.verifiedOn">核查于 {{ item.verifiedOn }}</span></div>
            <a v-if="safeExternalUrl(item.sourceUrl)" class="research-arrow" :href="safeExternalUrl(item.sourceUrl)" target="_blank" rel="noopener noreferrer" :aria-label="`查看${item.title}的官方来源`">↗</a>
          </article>
        </div>
      </div>
    </section>

    <section id="together" class="home-dark home-together" aria-labelledby="together-title">
      <div v-reveal class="home-wrap motif-host">
        <HomeMarginMotif kind="pair" />
        <header class="home-section-heading"><div><h2 id="together-title">组队招募</h2></div><RouterLink class="home-more" :to="{ name: 'teams' }">浏览团队 <span>↗</span></RouterLink></header>
        <p class="home-intro">{{ isVisualPreview ? '以下团队为视觉占位；真实招募请进入团队广场查看。' : '查看团队参加的比赛、已有技能和招募需求。' }}</p>
        <div v-if="teamsLoading" class="home-state" role="status">正在加载招募…</div>
        <div v-else-if="teamsError" class="home-state" role="alert">暂时无法加载招募。<button type="button" @click="loadTeams">重新加载 ↗</button></div>
        <div v-else-if="!recruitments.length" class="home-state">目前没有正在招募的团队。<RouterLink :to="{ name: 'teams' }">查看团队广场 ↗</RouterLink></div>
        <div v-else class="team-grid">
          <RouterLink v-for="item in recruitments" :key="item.id" class="team-preview" :to="isVisualPreview ? { name: 'teams' } : { name: 'recruitment-detail', params: { id: item.id } }">
            <div class="team-top"><span>团队 {{ item.code || item.id }}</span><span>{{ isVisualPreview ? '视觉示例' : '正在招募' }} ↗</span></div>
            <h3>{{ item.competition.title }}</h3><p class="team-edition">{{ item.competition.edition }}</p>
            <div class="team-skills"><div><span>已有能力</span><strong>{{ optionNames(item.current_skills) }}</strong></div><div><span>寻找角色</span><strong>{{ optionNames(item.required_roles) }}</strong></div></div>
            <div class="team-bottom"><span>{{ item.current_existing_member_count }} 位已有成员 · {{ item.remaining_slots }} 个剩余名额</span><span>{{ label(item.collaboration_mode) }}<template v-if="item.campuses?.length"> · {{ optionNames(item.campuses) }}</template></span></div>
          </RouterLink>
        </div>
      </div>
    </section>

    <section id="newsletters" class="home-light home-briefing" aria-labelledby="briefing-title"><div v-reveal class="home-wrap">
      <header class="home-section-heading"><div><h2 id="briefing-title">创享快讯<br /><span>比赛与科研动态</span></h2></div></header>
      <form v-if="newslettersCount || newsletterSearch" class="search-bar" role="search" @submit.prevent="searchNewsletters"><label class="sr-only" for="newsletter-search">搜索创享快讯</label><input id="newsletter-search" v-model="newsletterSearchInput" type="search" maxlength="200" placeholder="搜索快讯标题与内容…" /><button class="action-button" type="submit">搜索</button></form>
      <div v-if="newslettersLoading" class="home-state" role="status">正在加载快讯…</div>
      <div v-else-if="newslettersError" class="home-state" role="alert">暂时无法加载快讯。<button type="button" @click="loadEditorial('newsletters')">重新加载 ↗</button><button v-if="newslettersPage > 1" type="button" @click="changeNewsletterPage(1)">返回第一页</button></div>
      <div v-else-if="!newsletters.length" class="briefing-empty"><div><h3>{{ newsletterSearch ? '没有找到匹配快讯' : '暂时没有快讯' }}</h3><p>{{ newsletterSearch ? '换个关键词，或清空搜索查看全部快讯。' : '发布后可在这里查看。' }}</p></div><span>✦</span></div>
      <div v-else class="briefing-list"><article v-for="item in newsletters" :key="item.id" class="briefing-row"><div><h3>{{ item.title }}</h3><p>{{ item.summary }}</p></div><time :datetime="item.date || undefined">{{ item.date || '日期未注明' }}</time><a v-if="safeExternalUrl(item.sourceUrl)" :href="safeExternalUrl(item.sourceUrl)" target="_blank" rel="noopener noreferrer" :aria-label="`阅读${item.title}的来源`">↗</a></article></div>
      <el-pagination v-if="!newslettersLoading && !newslettersError && newslettersCount > 3" class="competition-pagination" :current-page="newslettersPage" :page-size="3" :total="newslettersCount" layout="prev, pager, next" prev-text="上一页" next-text="下一页" background aria-label="快讯分页" @update:current-page="changeNewsletterPage" />
    </div></section>
  </div>
</template>
