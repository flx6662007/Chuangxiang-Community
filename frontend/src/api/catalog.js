import http from './http'
import { paginatedLibrary } from '../utils/library'

export async function listCatalogEntries(params, signal) {
  return paginatedLibrary((await http.get('/competition-catalog/', { params, signal })).data)
}

export async function getCatalogEntry(code, params, signal) {
  return (await http.get(`/competition-catalog/${encodeURIComponent(code)}/`, { params, signal })).data
}

export async function listKnowledgeDocuments(params, signal) {
  return paginatedLibrary((await http.get('/knowledge-documents/', { params, signal })).data)
}

export async function getKnowledgeDocument(code, params, signal) {
  return (await http.get(`/knowledge-documents/${encodeURIComponent(code)}/`, { params, signal })).data
}
