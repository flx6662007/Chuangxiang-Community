function safeHttpUrl(value) {
  if (typeof value !== 'string') return false
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password
  } catch { return false }
}

export function parseAIReply(data) {
  const message = data?.message
  if (message?.role !== 'assistant' || typeof message.content !== 'string' || !message.content.trim()) {
    throw new Error('Invalid AI response')
  }
  const sources = Array.isArray(data.sources) ? data.sources.slice(0, 6).filter(source => {
    return source && typeof source.title === 'string' && safeHttpUrl(source.url)
  }).map(source => ({
    id: source.id,
    title: source.title,
    url: source.url,
    internal_url: (/^\/competitions\/\d+$/.test(source.internal_url || '') ||
      (source.kind === 'resource' && /^\/resources\/[a-zA-Z0-9_-]{1,80}$/.test(source.internal_url || ''))) ? source.internal_url : null,
    kind: source.kind,
    source_type: typeof source.source_type === 'string' ? source.source_type : null,
    trust_label: typeof source.trust_label === 'string' ? source.trust_label : null,
    reviewed: source.reviewed === true,
    status: typeof source.status === 'string' ? source.status : null,
    status_note: typeof source.status_note === 'string' ? source.status_note : null,
    verified_at: typeof source.verified_at === 'string' ? source.verified_at : null,
    published_on: typeof source.published_on === 'string' ? source.published_on : null,
    read_at: typeof source.read_at === 'string' ? source.read_at : null,
  })) : []
  const recommendations = Array.isArray(data.recommendations) ? data.recommendations.slice(0, 6)
    .filter(item => item && ['competition', 'resource', 'research_opportunity', 'research_group'].includes(item.object_type)
      && typeof item.title === 'string' && typeof item.reason === 'string'
      && safeHttpUrl(item.source_url))
    .map(item => ({ object_type: item.object_type, title: item.title, reason: item.reason,
      source_url: item.source_url, reviewed: item.reviewed === true,
      status_note: typeof item.status_note === 'string' ? item.status_note : '',
      research_group_label: typeof item.research_group_label === 'string' ? item.research_group_label : '',
      related_resources: Array.isArray(item.related_resources) ? item.related_resources.slice(0, 3)
        .filter(resource => resource && typeof resource.title === 'string' && safeHttpUrl(resource.source_url)) : [],
      related_object_ids: item.related_object_ids && typeof item.related_object_ids === 'object' ? item.related_object_ids : {} })) : []
  return { role: 'assistant', content: message.content, sources, recommendations,
    retrieval: data.retrieval && typeof data.retrieval === 'object' ? data.retrieval : null }
}
