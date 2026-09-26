import http from './http'

export async function listCompetitionCategories(signal) {
  return (await http.get('/competitions/categories/', { signal })).data
}

export async function listCompetitions(params, signal) {
  const { data } = await http.get('/competitions/', { params, signal })
  return data
}

export async function getCompetition(id, signal) {
  const { data } = await http.get(`/competitions/${encodeURIComponent(id)}/`, {
    signal,
  })
  return data
}
