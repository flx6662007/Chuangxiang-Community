<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listCompetitions } from '../api/competitions'
import {
  summaryDeadline,
  formatDate,
  levelLabels,
  safeExternalUrl,
} from '../utils/competition'
import { newsletters, laboratories } from '../data/editorial'
import AppIcon from '../components/AppIcon.vue'
import CampusIllustration from '../components/CampusIllustration.vue'

const router = useRouter()
const search = ref('')
const items = ref([])
const loading = ref(true)
const error = ref(false)
let controller
function submitSearch() {
  router.push({
    name: 'competitions',
    query: search.value.trim() ? { search: search.value.trim() } : {},
  })
}
async function load() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = false
  try {
    const data = await listCompetitions({ page_size: 4 }, controller.signal)
    if (!Array.isArray(data.results)) throw new Error('Invalid response')
    items.value = data.results
  } catch (err) {
    if (err.code !== 'ERR_CANCELED') error.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="welcome" aria-labelledby="welcome-title">
    <div class="home-hero">
      <div class="hero-copy">
        <span class="eyebrow"
          ><span class="small-dot" />连接校园里的每一个好想法</span
        >
        <h1 id="welcome-title">
          在创新中相遇，<br />遇见<span>更大的可能</span>
        </h1>
        <p>
          发现值得投入的赛事，让灵感迈出第一步。<br />你的科创之旅，从这里开始。
        </p>
        <form class="hero-search" role="search" @submit.prevent="submitSearch">
          <AppIcon name="search" :size="20" /><label
            class="sr-only"
            for="home-search"
            >搜索赛事</label
          ><input
            id="home-search"
            v-model="search"
            type="search"
            maxlength="200"
            placeholder="搜索赛事名称、关键词、主办单位…"
          /><button type="submit" aria-label="搜索赛事">
            <AppIcon name="arrow" :size="23" />
          </button>
        </form>
        <div class="hero-note">
          <AppIcon name="book" :size="15" /><span
            >赛事通知 · 参赛要求 · 官方来源</span
          >
        </div>
      </div>
      <CampusIllustration /><span class="hero-caption">IDEAS BEGIN HERE</span>
    </div>
    <div class="service-grid">
      <RouterLink class="service-card" :to="{ name: 'competitions' }"
        ><span class="service-icon"><AppIcon name="trophy" :size="28" /></span>
        <div>
          <h2>赛事中心</h2>
          <p>发现赛事，查阅通知与参赛要求</p>
        </div>
        <AppIcon name="arrow" :size="20"
      /></RouterLink>
      <RouterLink class="service-card violet" :to="{ name: 'account' }"
        ><span class="service-icon"><AppIcon name="shield" :size="28" /></span>
        <div>
          <h2>我的账号</h2>
          <p>管理学校邮箱与个人联系方式</p>
        </div>
        <AppIcon name="arrow" :size="20"
      /></RouterLink>
      <RouterLink class="service-card teal" to="/teams">
        <span class="service-icon"><AppIcon name="users" :size="28" /></span>
        <div>
          <h2>团队广场</h2>
          <p>围绕已收录赛事，寻找同行伙伴</p>
        </div>
        <AppIcon name="arrow" :size="20" />
      </RouterLink>
    </div>
    <section class="home-latest" aria-labelledby="latest-title">
      <div class="section-heading">
        <div>
          <span class="section-kicker">DISCOVER</span>
          <h2 id="latest-title">赛事速览</h2>
        </div>
        <RouterLink class="more-link" :to="{ name: 'competitions' }"
          >查看全部<AppIcon name="arrow" :size="17"
        /></RouterLink>
      </div>
      <div v-if="loading" class="state-panel compact-state" role="status">
        正在加载赛事…
      </div>
      <div v-else-if="error" class="state-panel compact-state" role="alert">
        <p>暂时无法加载赛事。</p>
        <button class="text-button" @click="load">重新加载</button>
      </div>
      <div v-else-if="!items.length" class="state-panel compact-state">
        <p>新赛事发布后会显示在这里。</p>
      </div>
      <div v-else class="latest-grid">
        <RouterLink
          v-for="item in items"
          :key="item.id"
          class="latest-card"
          :to="{ name: 'competition-detail', params: { id: item.id } }"
          ><div class="latest-card-top">
            <span class="tag">{{ item.category?.name || '赛事资讯' }}</span
            ><AppIcon name="arrow" :size="18" />
          </div>
          <h3>{{ item.title }}</h3>
          <p>
            {{ levelLabels[item.level] || '范围未注明' }}<span>·</span
            >{{ item.edition }}
          </p>
          <div class="latest-deadline">
            <AppIcon name="calendar" :size="16" /><span
              >{{ summaryDeadline(item).label }}<br /><strong>{{
                summaryDeadline(item).value
              }}</strong></span
            >
          </div></RouterLink
        >
      </div>
    </section>
    <section
      id="newsletters"
      class="home-latest"
      aria-labelledby="newsletters-title"
    >
      <div class="section-heading">
        <div>
          <span class="section-kicker">EDITORIAL BRIEFING</span>
          <h2 id="newsletters-title">创享快讯</h2>
        </div>
        <span class="editorial-label">团队手动整理</span>
      </div>
      <div v-if="!newsletters.length" class="editorial-empty">
        <span class="service-icon"><AppIcon name="book" :size="28" /></span>
        <div>
          <h3>由团队整理发布，首期筹备中</h3>
          <p>汇集值得关注的赛事与科创动态。</p>
        </div>
      </div>
      <div v-else class="editorial-grid">
        <article
          v-for="item in newsletters"
          :key="item.id"
          class="editorial-card"
        >
          <p class="editorial-meta">
            创享快讯<span v-if="item.date"> · {{ formatDate(item.date) }}</span>
          </p>
          <h3>{{ item.title }}</h3>
          <p class="preserve-lines">{{ item.summary }}</p>
          <a
            v-if="safeExternalUrl(item.sourceUrl)"
            class="more-link"
            :href="safeExternalUrl(item.sourceUrl)"
            target="_blank"
            rel="noopener noreferrer"
            >阅读快讯 ↗</a
          >
        </article>
      </div>
    </section>
    <section id="research" class="home-latest" aria-labelledby="research-title">
      <div class="section-heading">
        <div>
          <span class="section-kicker">UNDERGRADUATE RESEARCH</span>
          <h2 id="research-title">本科科研机会</h2>
        </div>
        <span class="editorial-label">实验室招募线索</span>
      </div>
      <p class="editorial-intro">
        汇集官方明确欢迎本科生参与的研究方向与实验室。线索不代表当前有名额，参与条件和安排请查阅官方说明并联系相关团队。
      </p>
      <div v-if="!laboratories.length" class="editorial-empty">
        <span class="service-icon"><AppIcon name="spark" :size="28" /></span>
        <div>
          <h3>官方线索整理中</h3>
          <p>核对本科生参与说明后在此展示。</p>
        </div>
      </div>
      <div v-else class="editorial-grid">
        <article
          v-for="item in laboratories"
          :key="item.id"
          class="editorial-card"
        >
          <p class="editorial-meta">{{ item.unit || '官方科研线索' }}</p>
          <h3>{{ item.title }}</h3>
          <p class="preserve-lines">{{ item.summary }}</p>
          <p v-if="item.participation" class="editorial-participation">
            {{ item.participation }}
          </p>
          <p v-if="item.evidenceNote" class="field-hint preserve-lines">
            {{ item.evidenceNote }}
          </p>
          <p v-if="item.date || item.verifiedOn" class="timestamp">
            <span>原文日期：{{ formatDate(item.date) }}</span
            ><span v-if="item.verifiedOn"> · </span
            ><span v-if="item.verifiedOn"
              >核验：{{ formatDate(item.verifiedOn) }}</span
            >
          </p>
          <a
            v-if="safeExternalUrl(item.sourceUrl)"
            class="more-link"
            :href="safeExternalUrl(item.sourceUrl)"
            target="_blank"
            rel="noopener noreferrer"
            >查阅官方说明 ↗</a
          >
        </article>
      </div>
    </section>
    <section class="home-vision">
      <div class="vision-icon"><AppIcon name="spark" :size="32" /></div>
      <div>
        <h2>让校园里的好想法，相遇成行</h2>
        <p>从一场赛事出发，探索兴趣、积累经验、找到伙伴。</p>
      </div>
      <RouterLink class="action-button" :to="{ name: 'competitions' }"
        >去发现赛事<AppIcon name="arrow" :size="17"
      /></RouterLink>
    </section>
    <p class="development-note">
      快讯由团队整理，科研参与条件以官方说明为准。智能辅助功能尚未开放。
    </p>
  </section>
</template>
