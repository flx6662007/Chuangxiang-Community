<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { getCatalogEntry, listKnowledgeDocuments, getKnowledgeDocument } from '../api/catalog'
import { useLibrarySession } from '../composables/useLibrarySession'
import { libraryPage, libraryQuery } from '../utils/library'
import { formatUpdatedAt, safeExternalUrl } from '../utils/competition'

const route = useRoute(), router = useRouter()
const item = ref(null), documents = ref([]), count = ref(0), loading = ref(true), error = ref(''), documentError = ref('')
const selected = ref(null), selectedCode = ref(''), documentLoading = ref(false), detailError = ref('')
const preview = computed(() => route.query.preview === '1')
const page = computed(() => libraryPage(route.query.doc_page))
const pageSize = 10
const previewParams = computed(() => preview.value ? { preview: '1' } : {})
const resourceQuery = computed(() => ({ catalog_code: route.params.code }))
let generation = 0, documentGeneration = 0, controller, documentController

function clear() {
  generation++
  documentGeneration++
  controller?.abort()
  documentController?.abort()
  item.value = null
  documents.value = []
  selected.value = null
  selectedCode.value = ''
  count.value = 0
}
const { canPreview } = useLibrarySession(() => { if (preview.value) clear() }, () => { if (preview.value) load() })
function errorMessage(err, fallback) {
  if ([401, 403].includes(err.response?.status)) return '内部预览需要登录具有资料查看权限的管理员账号。'
  if (err.response?.status === 404) return '未找到资料，请返回目录或第一页。'
  return fallback
}
async function load() {
  clear()
  const request = generation
  controller = new AbortController()
  loading.value = true
  error.value = ''
  documentError.value = ''
  detailError.value = ''
  const results = await Promise.allSettled([
    getCatalogEntry(route.params.code, previewParams.value, controller.signal),
    listKnowledgeDocuments({ catalog_code: route.params.code, page: page.value, page_size: pageSize, ...previewParams.value }, controller.signal),
  ])
  if (request !== generation) return
  if (results[0].status === 'fulfilled') item.value = results[0].value
  else error.value = errorMessage(results[0].reason, '暂时无法读取赛事目录，请稍后重试。')
  if (results[1].status === 'fulfilled') {
    documents.value = results[1].value.results
    count.value = results[1].value.count
  } else documentError.value = errorMessage(results[1].reason, '整理资料暂时无法加载。')
  loading.value = false
}
async function openDocument(code) {
  if (selectedCode.value === code) {
    documentGeneration++
    documentController?.abort()
    selectedCode.value = ''
    selected.value = null
    return
  }
  const request = ++documentGeneration
  documentController?.abort()
  documentController = new AbortController()
  selectedCode.value = code
  selected.value = null
  documentLoading.value = true
  detailError.value = ''
  try {
    const data = await getKnowledgeDocument(code, previewParams.value, documentController.signal)
    if (request === documentGeneration) selected.value = data
  } catch (err) {
    if (request === documentGeneration && err.code !== 'ERR_CANCELED') detailError.value = errorMessage(err, '暂时无法读取正文。')
  } finally {
    if (request === documentGeneration) documentLoading.value = false
  }
}
function changePage(value) {
  router.push({ query: libraryQuery({ ...route.query, doc_page: value > 1 ? value : undefined }) })
}
function togglePreview() {
  router.replace({ query: libraryQuery({ ...route.query, preview: preview.value ? undefined : '1', doc_page: undefined }) })
}
watch(() => [route.params.code, preview.value, page.value], load, { immediate: true })
onBeforeUnmount(clear)
</script>

<template>
  <section class="detail-page resource-detail catalog-detail" aria-labelledby="catalog-title">
    <RouterLink class="back-link" :to="{ name: 'competitions', query: { view: 'catalog', search: route.query.search, grade: route.query.grade, page: route.query.page } }">← 赛事目录<span>/</span>目录详情</RouterLink>
    <div v-if="canPreview || preview" class="library-preview-controls">
      <button class="text-button" @click="togglePreview">{{ preview ? '返回公开资料' : '管理员：预览未发布资料' }}</button>
      <span v-if="preview" class="tag warm">资料预览</span>
    </div>
    <div v-if="loading" class="state-panel" role="status">正在加载目录与关联资料…</div>
    <div v-else-if="error" class="state-panel" role="alert"><p>{{ error }}</p><button class="action-button secondary" @click="load">重新加载</button><RouterLink v-if="preview" class="text-button" :to="{ name: 'account' }">前往登录</RouterLink></div>
    <template v-else-if="item">
      <header class="detail-hero">
        <span class="detail-emblem"><AppIcon name="trophy" :size="36" /></span>
        <div class="detail-hero-copy">
          <p class="editorial-meta">{{ item.code }} · {{ item.version }} 年目录</p>
          <h2 id="catalog-title">{{ item.name }}</h2>
          <div class="tag-row"><span class="tag">目录等级 {{ item.grade }}</span><span class="tag neutral">{{ item.levels }}</span></div>
        </div>
      </header>
      <nav class="detail-tabs" aria-label="赛事资料导航">
        <a href="#catalog-editions">届次通知 {{ item.competition_count || 0 }}</a>
        <a href="#catalog-documents">赛事资料 {{ count }}</a>
        <RouterLink :to="{ name: 'resources', query: resourceQuery }">学习资源 {{ item.resource_count || 0 }} →</RouterLink>
      </nav>
      <div class="detail-layout">
        <div class="detail-main">
          <el-card id="catalog-editions" class="detail-section" shadow="never">
            <h2>届次通知</h2>
            <ul v-if="item.competitions?.length" class="source-list">
              <li v-for="competition in item.competitions" :key="competition.id">
                <RouterLink v-if="competition.publication_status === 'published'" :to="{ name: 'competition-detail', params: { id: competition.id }, query: { view: 'editions' } }">{{ competition.title }} →</RouterLink>
                <strong v-else>{{ competition.title }} <span class="tag warm">待发布</span></strong>
                <p>{{ competition.summary }}</p>
              </li>
            </ul>
            <p v-else class="muted">暂无届次通知。</p>
          </el-card>
          <el-card id="catalog-documents" class="detail-section" shadow="never">
            <div class="section-heading"><h2>赛事资料</h2><span class="muted">{{ count }} 份</span></div>
            <p v-if="documentError" class="notice-text" role="alert">{{ documentError }} <button class="text-button" @click="changePage(1); load()">重新加载第一页</button></p>
            <p v-else-if="!documents.length" class="muted">暂无已收录的整理资料。</p>
            <article v-for="document in documents" :key="document.code" class="knowledge-document">
              <div class="tag-row"><span class="tag neutral">{{ document.edition || '届次未注明' }}</span><span v-if="document.review_status === 'draft'" class="tag warm">草稿</span></div>
              <h3>{{ document.title }}</h3>
              <p v-if="selectedCode !== document.code" class="knowledge-summary preserve-lines">{{ document.summary }}</p>
              <button class="text-button" :aria-expanded="selectedCode === document.code" @click="openDocument(document.code)">{{ selectedCode === document.code ? '收起正文' : '阅读全文' }}</button>
              <template v-if="selectedCode === document.code">
                <p v-if="documentLoading" role="status">正在读取正文…</p>
                <p v-else-if="detailError" role="alert">{{ detailError }}</p>
                <section v-else-if="selected" class="knowledge-body">
                  <p v-if="selected.notes?.edition_note && !selected.body.includes(selected.notes.edition_note)" class="muted preserve-lines">{{ selected.notes.edition_note }}</p>
                  <p class="preserve-lines">{{ selected.body }}</p>
                  <p v-if="selected.body_truncated" class="muted">继续阅读：打开下方来源链接查看完整内容。</p>
                  <p class="timestamp">资料更新：{{ formatUpdatedAt(selected.updated_at) }}</p>
                </section>
              </template>
              <ul v-if="document.sources?.length" class="source-list"><li v-for="(source, index) in document.sources" :key="index"><a v-if="safeExternalUrl(source.url)" :href="safeExternalUrl(source.url)" target="_blank" rel="noopener noreferrer">{{ source.title || '来源原文' }} ↗</a><span v-else>{{ source.title || '来源链接待补充' }}</span></li></ul>
            </article>
            <el-pagination v-if="count > pageSize && !documentError" class="competition-pagination" :current-page="page" :page-size="pageSize" :total="count" layout="prev, pager, next" prev-text="上一页" next-text="下一页" background @update:current-page="changePage" />
          </el-card>
        </div>
        <aside class="detail-sidebar">
          <el-card class="detail-section" shadow="never">
            <h2>学习资源</h2><p>规则、赛题、课程、工具及案例，与本赛事目录关联。</p>
            <p v-if="!preview" class="muted">共 {{ item.resource_count || 0 }} 条学习资料</p>
            <RouterLink class="action-button" :to="{ name: 'resources', query: resourceQuery }">查看关联学习资料 →</RouterLink>
          </el-card>
        </aside>
      </div>
    </template>
  </section>
</template>
