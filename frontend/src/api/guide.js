import http from './http'
import { ensureCsrf } from './csrf'

export async function getGuide(signal) {
  return (await http.get('/ai/guide/', { signal, timeout: 130000 })).data
}

export async function updateGuide(data, signal) {
  await ensureCsrf()
  return (await http.post('/ai/guide/', data, { signal, timeout: 130000 })).data
}
