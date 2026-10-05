import { paginatedLibrary, publicResourceQuery } from '../utils/library.js'

export function createResourceReader(http) {
  return {
    async listResources(params = {}, signal) {
      return paginatedLibrary((await http.get('/resources/', { params: publicResourceQuery(params), signal })).data)
    },
    async getResource(code, params = {}, signal) {
      return (await http.get(`/resources/${encodeURIComponent(code)}/`, { params: publicResourceQuery(params), signal })).data
    },
    async listResourceTaxonomies(params = {}, signal) {
      const { data } = await http.get('/resources/options/', { params: publicResourceQuery(params), signal })
      if (!Array.isArray(data?.categories) || !Array.isArray(data?.directions)) {
        throw new Error('Invalid resource taxonomy response')
      }
      return data
    },
  }
}
