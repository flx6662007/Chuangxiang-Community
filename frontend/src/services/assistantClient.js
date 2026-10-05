export function createAssistantReader(http) {
  return {
    async search(query, { signal } = {}) {
      const q = typeof query === 'string' ? query.trim() : ''
      if (!q || q.length > 500) throw new TypeError('请输入 1—500 字的赛事关键词。')
      const { data } = await http.get('/ai/search/', { params: { q }, signal })
      if (data?.mode !== 'keyword' || !Array.isArray(data.keywords)
        || !data.keywords.every(word => typeof word === 'string')
        || !Number.isSafeInteger(data.count) || data.count < 0 || !Array.isArray(data.results)
        || !data.results.every(item => typeof item.catalog?.code === 'string'
          && typeof item.catalog?.name === 'string' && typeof item.match_reason === 'string')) {
        throw new Error('Invalid assistant response')
      }
      return data
    },
  }
}
