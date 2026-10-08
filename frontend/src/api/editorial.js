import http from './http'

async function listEditorial(kind, params, signal) {
  const { data } = await http.get(`/editorial/${kind}/`, { params, signal })
  if (!data || !Array.isArray(data.results) || !Number.isInteger(data.count) || data.count < 0) {
    throw new Error('Invalid editorial response')
  }
  return data
}

export const listResearch = (params, signal) => listEditorial('research', params, signal)
export async function getResearch(id, signal) {
  const { data } = await http.get(`/editorial/research/${encodeURIComponent(id)}/`, { signal })
  if (!data || data.id !== `db-${id}` || typeof data.title !== 'string') throw new Error('Invalid research response')
  return data
}
export const listNewsletters = (params, signal) => listEditorial('newsletters', params, signal)
