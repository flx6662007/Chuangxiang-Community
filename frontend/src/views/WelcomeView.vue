<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { listCompetitions } from '../api/competitions'
import { listRecruitments } from '../api/teams'
import { summaryDeadline, levelLabels, safeExternalUrl, deadlineStatusLabel } from '../utils/competition'
import { label, optionNames } from '../utils/teams'
import { newsletters, laboratories } from '../data/editorial'
import { previewCompetitions, previewRecruitments } from '../mocks/homeVisualPreview'
import AICompetitionAssistant from '../components/AICompetitionAssistant.vue'
import HomeBlankImpression from '../components/HomeBlankImpression.vue'
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

async function loadCompetitions() {
  competitionController?.abort()
  competitionController = new AbortController()
  loading.value = true
  error.value = false
  try {
    const data = await listCompetitions(
      { page_size: 4, time_status: 'current' },
      competitionController.signal,
    )
    if (isVisualPreview.value) return
    if (!Array.isArray(data.results)) throw new Error('Invalid response')
    items.value = data.results
  } catch (err) {
    if (!isVisualPreview.value && err.code !== 'ERR_CANCELED') error.value = true
  } finally {
    loading.value = false
  }
}

async function loadTeams() {
  teamController?.abort()
  teamController = new AbortController()
  teamsLoading.value = true
  teamsError.value = false
  try {
    const data = await listRecruitments(
      { open_only: 'true', page_size: 2 },
      teamController.signal,
    )
    if (isVisualPreview.value) return
    if (!Array.isArray(data.results)) throw new Error('Invalid response')
    recruitments.value = data.results
  } catch (err) {
    if (!isVisualPreview.value && err.code !== 'ERR_CANCELED') teamsError.value = true
  } finally {
    teamsLoading.value = false
  }
}

onMounted(() => {
  if (!isVisualPreview.value) {
    loadCompetitions()
    loadTeams()
  }
})
watch(isVisualPreview, (preview) => {
  if (preview) {
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
  competitionController?.abort()
  teamController?.abort()
})
</script>

<template>
  <div ref="pageRoot" class="welcome">
    <div v-if="isVisualPreview" class="home-preview-banner" role="note"><span>界面预览</span>赛事与团队为前端占位内容，仅用于评估视觉。<RouterLink to="/">退出预览 ↗</RouterLink></div>
    <section class="home-dark home-opening" aria-labelledby="welcome-title">
      <div class="home-wrap">
        <div class="home-hero">
          <div class="hero-copy">
            <HomeBlankImpression />
            <h1 id="welcome-title">在创新中相遇，<br />遇见<span>更大的可能。</span></h1>
            <p class="hero-lead">发现值得投入的比赛、研究与伙伴。<br />从一个想法开始。</p>
          </div>
          <div class="hero-art hero-shortcuts"><HomeLiquidLinks /></div>
        </div>
        <div class="start-here" aria-labelledby="start-title">
          <div class="start-label"><span id="start-title">从你的下一步开始</span></div>
          <div class="start-links">
            <RouterLink :to="{ name: 'competitions' }"><span>赛事</span><strong>浏览已收录比赛</strong><span class="start-arrow">↗</span></RouterLink>
            <RouterLink :to="{ name: 'research-projects' }"><span>科研</span><strong>查阅官方研究线索</strong><span class="start-arrow">↗</span></RouterLink>
            <RouterLink :to="{ name: 'teams' }"><span>组队</span><strong>寻找参赛伙伴</strong><span class="start-arrow">↗</span></RouterLink>
            <RouterLink :to="{ name: 'resources' }"><span>资源</span><strong>查看学习与工具示例</strong><span class="start-arrow">↗</span></RouterLink>
          </div>
        </div>
      </div>
    </section>

    <div id="ai" class="home-dark home-ai"><div v-reveal class="home-wrap"><AICompetitionAssistant /></div></div>

    <section id="discover" class="home-light home-discover" aria-labelledby="discover-title">
      <div v-reveal class="home-wrap">
        <header class="home-section-heading">
          <div><h2 id="discover-title">最近，<br /><span>有什么值得参加？</span></h2></div>
          <RouterLink class="home-more" :to="{ name: 'competitions' }">查看全部 <span>↗</span></RouterLink>
        </header>
        <p class="home-intro">{{ isVisualPreview ? '以下是版式占位示例；真实赛事与时间请进入赛事列表核对。' : '从真实收录的赛事开始探索。时间未知不代表正在报名，请以官方通知为准。' }}</p>
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
          <div><h2 id="research-title">加入<span>真正的研究。</span></h2></div>
          <RouterLink class="home-more" :to="{ name: 'research-projects' }">查看全部 <span>↗</span></RouterLink>
        </header>
        <p class="home-intro">来自官方页面的本科科研线索。具体课题、条件与当前名额请向相关团队确认。</p>
        <div v-if="!laboratories.length" class="home-state">官方科研线索整理中。</div>
        <div v-else class="research-list">
          <article v-for="item in laboratories.slice(0, 3)" :key="item.id" class="research-row">
            <div class="research-main"><h3>{{ item.title }}</h3><p>{{ item.summary }}</p><span>{{ item.participation }}</span></div>
            <div class="research-end"><span>{{ item.unit }}</span><span>核查于 {{ item.verifiedOn }}</span></div>
            <a v-if="safeExternalUrl(item.sourceUrl)" class="research-arrow" :href="safeExternalUrl(item.sourceUrl)" target="_blank" rel="noopener noreferrer" :aria-label="`查看${item.title}的官方来源`">↗</a>
          </article>
        </div>
      </div>
    </section>

    <section id="together" class="home-dark home-together" aria-labelledby="together-title">
      <div v-reveal class="home-wrap motif-host">
        <HomeMarginMotif kind="pair" />
        <header class="home-section-heading"><div><h2 id="together-title">找到一起把想法<br /><span>做出来的人。</span></h2></div><RouterLink class="home-more" :to="{ name: 'teams' }">浏览团队 <span>↗</span></RouterLink></header>
        <p class="home-intro">{{ isVisualPreview ? '以下团队为视觉占位；真实招募请进入团队广场查看。' : '围绕真实赛事组队，让不同能力的人找到共同的目标。' }}</p>
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
      <header class="home-section-heading"><div><h2 id="briefing-title">这周，<br /><span>科创圈发生了什么？</span></h2></div></header>
      <div v-if="!newsletters.length" class="briefing-empty"><div><h3>创享快讯正在筹备</h3><p>团队会在核实来源后，把值得关注的科创动态放在这里。</p></div><span>✦</span></div>
      <div v-else class="briefing-list"><article v-for="item in newsletters" :key="item.id" class="briefing-row"><div><h3>{{ item.title }}</h3><p>{{ item.summary }}</p></div><time :datetime="item.date || undefined">{{ item.date || '日期未注明' }}</time><a v-if="safeExternalUrl(item.sourceUrl)" :href="safeExternalUrl(item.sourceUrl)" target="_blank" rel="noopener noreferrer" :aria-label="`阅读${item.title}的来源`">↗</a></article></div>
    </div></section>
  </div>
</template>
