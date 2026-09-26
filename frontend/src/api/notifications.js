import http from './http'
import { ensureCsrf } from './accounts'
export async function listNotifications(params, signal) {
  return (await http.get('/notifications/', { params, signal })).data
}
export async function readNotification(id) {
  await ensureCsrf()
  return (await http.post(`/notifications/${encodeURIComponent(id)}/read/`, {}))
    .data
}
