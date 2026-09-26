<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listCompetitions } from '../api/competitions'
import { formatDeadline, levelLabels } from '../utils/competition'
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
      <div class="service-card teal planned-service">
        <span class="service-icon"><AppIcon name="users" :size="28" /></span>
        <div>
          <h2>团队广场 <span class="coming-label">筹备中</span></h2>
          <p>围绕已收录赛事，寻找同行伙伴</p>
        </div>
      </div>
    </div>
    <section class="home-latest" aria-labelledby="latest-title">
      <div class="section-heading">
        <div>
          <span class="section-kicker">DISCOVER</span>
          <h2 id="latest-title">新近收录赛事</h2>
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
              >报名截止<br /><strong>{{
                formatDeadline(item, 'registration_deadline')
              }}</strong></span
            >
          </div></RouterLink
        >
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
      后续建设：参赛组队、创享资讯与快讯、基于来源的智能辅助。上述功能尚未开放。
    </p>
  </section>
</template>
