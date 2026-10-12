<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getNewsletter } from '../api/editorial'
import { safeExternalUrl } from '../utils/competition'

const route = useRoute()
const item = ref(null)
const loading = ref(true)
const error = ref('')
const notFound = ref(false)
let controller

async function load(code) {
  controller?.abort()
  const pending = new AbortController()
  controller = pending
  item.value = null
  error.value = ''
  notFound.value = false
  loading.value = true
  try {
    const result = await getNewsletter(code, pending.signal)
    if (!pending.signal.aborted) item.value = result
  } catch (caught) {
    if (!pending.signal.aborted && caught.code !== 'ERR_CANCELED') {
      notFound.value = caught.response?.status === 404
      error.value = notFound.value ? '这期快讯不存在或尚未公开。' : '快讯暂时无法加载，请稍后重试。'
    }
  } finally {
    if (!pending.signal.aborted) loading.value = false
  }
}

function publicationDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
}
watch(() => route.params.code, load, { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="newsletter-page">
    <RouterLink class="back-link" :to="{ name: 'home', hash: '#newsletters' }">← 返回创享快讯</RouterLink>
    <div v-if="loading" class="state-panel" role="status">正在加载本期快讯…</div>
    <div v-else-if="error" class="state-panel" role="alert">
      <h1>{{ notFound ? '未找到快讯' : '加载失败' }}</h1>
      <p>{{ error }}</p>
      <button v-if="!notFound" class="action-button" type="button" @click="load(route.params.code)">重新加载</button>
    </div>
    <article v-else-if="item">
      <header class="newsletter-heading">
        <p class="newsletter-eyebrow">创享快讯</p>
        <h1><span v-for="(part, index) in item.title.split(' · ')" :key="index" class="newsletter-title-part">{{ index ? ' · ' : '' }}{{ part }}</span></h1>
        <div class="newsletter-dates">
          <span v-if="item.sourcePublishedOn">原文发布 <time :datetime="item.sourcePublishedOn">{{ item.sourcePublishedOn }}</time></span>
          <span v-if="item.publishedAt">站内发布 <time :datetime="item.publishedAt">{{ publicationDate(item.publishedAt) }}</time></span>
        </div>
        <p v-if="item.introduction" class="newsletter-introduction">{{ item.introduction }}</p>
        <p v-if="item.hasHiddenItems" class="newsletter-note" role="status">部分关联内容已不再公开，本页仅保留仍可阅读的条目。</p>
      </header>
      <nav v-if="item.sections.length" class="newsletter-toc" aria-label="本期栏目">
        <a v-for="(section, index) in item.sections" :key="section.kind" :href="`#issue-${section.kind}`">{{ String(index + 1).padStart(2, '0') }} · {{ section.title }}</a>
      </nav>
      <p v-else class="state-panel" role="status">本期暂时没有可公开阅读的条目。</p>
      <section v-for="(section, sectionIndex) in item.sections" :id="`issue-${section.kind}`" :key="section.kind" class="newsletter-section" :aria-labelledby="`heading-${section.kind}`">
        <h2 :id="`heading-${section.kind}`"><span>{{ String(sectionIndex + 1).padStart(2, '0') }}</span>{{ section.title }}</h2>
        <div v-for="(group, groupIndex) in section.groups" :key="groupIndex" class="newsletter-group">
          <h3><span>{{ groupIndex + 1 }}.</span> {{ group.title }}</h3>
          <div v-for="entry in group.items" :key="entry.id" class="newsletter-entry">
            <h4 v-if="entry.title !== group.title">{{ entry.title }}</h4>
            <p class="newsletter-body">{{ entry.body }}</p>
            <p v-if="entry.sourceChanged" class="newsletter-note">关联资料已有更新，以上保留本期发布时的内容。请核对最新官方信息。</p>
            <a v-if="safeExternalUrl(entry.sourceUrl)" class="newsletter-source" :href="safeExternalUrl(entry.sourceUrl)" target="_blank" rel="noopener noreferrer" :aria-label="`查看${entry.title}的来源（新窗口）`">查看{{ section.kind === 'resource' ? '资源' : '赛事' }}来源 ↗</a>
            <p v-else class="newsletter-note">来源链接暂不可用。</p>
          </div>
        </div>
      </section>
      <footer v-if="item.credits" class="newsletter-credits">{{ item.credits }}</footer>
    </article>
  </div>
</template>

<style scoped>
.newsletter-page { max-width: 920px; margin: 0 auto; padding: 40px 28px 80px; color: var(--text-primary); overflow-wrap: anywhere; }
.back-link, .newsletter-source, .newsletter-toc a { display: inline-flex; align-items: center; min-height: 44px; color: var(--accent); }
.newsletter-heading { padding: 48px 0 32px; }
.newsletter-eyebrow { color: var(--text-secondary); font-size: 14px; letter-spacing: .12em; }
h1 { font-size: clamp(28px, 4vw, 44px); line-height: 1.3; margin: 16px 0 24px; font-weight: 600; text-wrap: balance; }
.newsletter-title-part { display: inline-block; max-width: 100%; }
.newsletter-dates { display: flex; flex-wrap: wrap; gap: 12px 28px; font-size: 14px; color: var(--text-secondary); }
.newsletter-introduction { font-size: 18px; line-height: 1.9; max-width: 720px; margin: 28px 0 0; white-space: pre-line; }
.newsletter-toc { display: flex; flex-wrap: wrap; gap: 12px 28px; padding: 12px 0; border-block: 1px solid var(--border-soft); }
.newsletter-section { padding-top: 48px; scroll-margin-top: 100px; }
h2 { display: flex; align-items: baseline; gap: 18px; font-size: 26px; margin: 0 0 12px; }
h2 > span { font-size: 14px; color: var(--accent); }
.newsletter-group { padding: 28px 0; border-bottom: 1px solid var(--border-soft); }
h3 { font-size: 21px; line-height: 1.6; margin: 0 0 18px; }
h3 > span { color: var(--text-secondary); }
h4 { font-size: 18px; margin: 24px 0 12px; }
.newsletter-body { white-space: pre-line; line-height: 1.95; font-size: 16px; margin: 0; }
.newsletter-note { color: var(--text-secondary); font-size: 14px; line-height: 1.7; margin: 16px 0; }
.newsletter-source { margin-top: 12px; text-decoration: underline; text-underline-offset: 5px; font-size: 15px; }
.newsletter-credits { padding-top: 36px; white-space: pre-line; line-height: 1.9; color: var(--text-secondary); }
a:hover { color: var(--accent-hover); }
a:active { opacity: .75; }
a:focus-visible, button:focus-visible { outline: 2px solid var(--accent); outline-offset: 5px; }
@media (max-width: 600px) { .newsletter-page { padding: 24px 20px 56px; } .newsletter-heading { padding-top: 28px; } .newsletter-section { padding-top: 36px; } h3 { font-size: 19px; } }
</style>
