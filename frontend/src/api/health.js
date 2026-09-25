import http from './http'

export async function getHealth() {
  const response = await http.get('/health/')
  return response.data
}
