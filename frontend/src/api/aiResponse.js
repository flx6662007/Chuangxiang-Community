export function parseAIReply(data) {
  const message = data?.message
  if (message?.role !== 'assistant' || typeof message.content !== 'string' || !message.content.trim()) {
    throw new Error('Invalid AI response')
  }
  const sources = Array.isArray(data.sources) ? data.sources.slice(0, 6).filter(source => {
    if (!source || typeof source.title !== 'string' || typeof source.url !== 'string') return false
    try {
      const url = new URL(source.url)
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password
    } catch { return false }
  }).map(source => ({
    id: source.id,
    title: source.title,
    url: source.url,
    internal_url: /^\/competitions\/\d+$/.test(source.internal_url || '') ? source.internal_url : null,
    kind: source.kind,
    status: typeof source.status === 'string' ? source.status : null,
    status_note: typeof source.status_note === 'string' ? source.status_note : null,
    verified_at: typeof source.verified_at === 'string' ? source.verified_at : null,
    published_on: typeof source.published_on === 'string' ? source.published_on : null,
    read_at: typeof source.read_at === 'string' ? source.read_at : null,
  })) : []
  return { role: 'assistant', content: message.content, sources,
    retrieval: data.retrieval && typeof data.retrieval === 'object' ? data.retrieval : null }
}
