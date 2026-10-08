function safeHttpUrl(value) {
  if (typeof value !== 'string') return false
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password
  } catch { return false }
}

function safeInternalUrl(kind, value) {
  if (typeof value !== 'string') return null
  const patterns = {
    competition: /^\/competitions\/[1-9]\d*$/,
    resource: /^\/resources\/[a-zA-Z0-9_-]{1,80}$/,
    research_opportunity: /^\/research\/[1-9]\d*$/,
    team: /^\/teams\/[1-9]\d*$/,
  }
  return patterns[kind]?.test(value) ? value : null
}

function safeSourceUrl(kind, value) {
  return safeHttpUrl(value) || (kind === 'team' && safeInternalUrl(kind, value) === value)
}

const researchFields = ['summary', 'direction', 'location', 'achievements', 'roles', 'eligibility',
  'work', 'commitment', 'scope', 'cohort', 'deadline', 'status', 'recruitment']

function researchFacts(item) {
  const facts = {}, field_links = {}
  for (const field of researchFields) {
    if (typeof item.facts?.[field] === 'string') facts[field] = item.facts[field].slice(0, 5000)
    if (Array.isArray(item.field_links?.[field])) {
      const seen = new Set()
      field_links[field] = item.field_links[field].filter(link => {
        if (!link || typeof link.label !== 'string' || !safeHttpUrl(link.url) || seen.has(link.url)) return false
        seen.add(link.url)
        return true
      }).slice(0, 3).map(link => ({ label: link.label.slice(0, 40), url: link.url }))
    }
  }
  return { facts, field_links }
}

export function parseAIReply(data) {
  const message = data?.message
  if (message?.role !== 'assistant' || typeof message.content !== 'string' || !message.content.trim()) {
    throw new Error('Invalid AI response')
  }
  const sources = Array.isArray(data.sources) ? data.sources.slice(0, 6).filter(source => {
    return source && typeof source.title === 'string' && safeSourceUrl(source.kind, source.url)
  }).map(source => ({
    id: source.id,
    entity_id: typeof source.entity_id === 'string' ? source.entity_id.slice(0, 100) : null,
    database_id: typeof source.database_id === 'string' && /^\d+$/.test(source.database_id) ? source.database_id : null,
    title: source.title,
    url: source.url,
    internal_url: safeInternalUrl(source.kind, source.internal_url),
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
    .filter(item => item && ['competition', 'resource', 'research_opportunity', 'research_group', 'team'].includes(item.object_type)
      && typeof item.title === 'string' && typeof item.reason === 'string'
      && safeSourceUrl(item.object_type, item.source_url))
    .map(item => ({ object_type: item.object_type,
      object_id: typeof item.object_id === 'string' ? item.object_id.slice(0, 100) : null,
      database_id: typeof item.database_id === 'string' && /^\d+$/.test(item.database_id) ? item.database_id : null,
      internal_url: safeInternalUrl(item.object_type, item.internal_url), title: item.title, reason: item.reason,
      ...researchFacts(item),
      source_url: item.source_url, reviewed: item.reviewed === true,
      status_note: typeof item.status_note === 'string' ? item.status_note : '',
      research_group_label: typeof item.research_group_label === 'string' ? item.research_group_label : '',
      related_resources: Array.isArray(item.related_resources) ? item.related_resources.slice(0, 3)
        .filter(resource => resource && typeof resource.title === 'string' && safeHttpUrl(resource.source_url)) : [],
      related_object_ids: item.related_object_ids && typeof item.related_object_ids === 'object' ? item.related_object_ids : {} })) : []
  return { role: 'assistant', content: message.content, sources, recommendations,
    conversation_context: typeof data.conversation_context === 'string' && data.conversation_context.length <= 12000 ? data.conversation_context : undefined,
    retrieval: data.retrieval && typeof data.retrieval === 'object' ? data.retrieval : null }
}
