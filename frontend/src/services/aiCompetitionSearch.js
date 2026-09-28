import { mockAICompetitionSearch } from '../mocks/aiCompetitionSearch.js'

// 固定页面契约：未来在此替换为 POST /api/v1/ai/competition-search/，body 为 { query }。
// 返回 { interpretation, results: [{ competition, matchReason }] }，页面无需依赖赛事列表接口。
export async function searchCompetitionsByAI(query, { signal } = {}) {
  const text = typeof query === 'string' ? query.trim() : ''
  if (!text) throw new TypeError('请输入竞赛需求')

  await new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('搜索已取消', 'AbortError'))
      return
    }
    const onAbort = () => {
      clearTimeout(timer)
      reject(new DOMException('搜索已取消', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, 800 + Math.floor(Math.random() * 701))
    signal?.addEventListener('abort', onAbort, { once: true })
  })

  if (signal?.aborted) throw new DOMException('搜索已取消', 'AbortError')
  if (text === '模拟错误') throw new Error('模拟 AI 搜索暂时不可用')
  return mockAICompetitionSearch(text)
}
