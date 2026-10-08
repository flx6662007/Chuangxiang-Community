import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
// Only completed, source-checked links are interactive; never load remote images.
markdown.renderer.rules.image = (tokens, index) => markdown.utils.escapeHtml(tokens[index].content || '')
markdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  const href = tokens[index].attrGet('href')
  if (!env.urls?.has(href)) return '<span>'
  tokens[index].attrSet('target', '_blank')
  tokens[index].attrSet('rel', 'noopener noreferrer')
  return renderer.renderToken(tokens, index, options)
}
markdown.renderer.rules.link_close = (tokens, index, options, env) => {
  let depth = 1
  for (let i = index - 1; i >= 0; i--) {
    if (tokens[i].type === 'link_close') depth++
    if (tokens[i].type === 'link_open' && --depth === 0) return env.urls?.has(tokens[i].attrGet('href')) ? '</a>' : '</span>'
  }
  return '</span>'
}
export function renderAIMessage(message) {
  const urls = new Set(message.generating || message.incomplete ? [] : (message.sources || []).map(source => source.url))
  return markdown.render(message.content || '', { urls })
}
