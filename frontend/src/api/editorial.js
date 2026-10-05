import http from './http'

async function listEditorial(kind, params, signal) {
  const { data } = await http.get(`/editorial/${kind}/`, { params, signal })
  if (!data || !Array.isArray(data.results) || !Number.isInteger(data.count) || data.count < 0) {
    throw new Error('Invalid editorial response')
  }
  return data
}

export const listResearch = (params, signal) => listEditorial('research', params, signal)
export const listNewsletters = (params, signal) => listEditorial('newsletters', params, signal)
