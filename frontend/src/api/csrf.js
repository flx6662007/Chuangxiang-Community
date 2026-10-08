import http from './http'
import { csrfFromCookie } from '../utils/account'

export async function ensureCsrf() {
  if (!csrfFromCookie(document.cookie)) await http.get('/accounts/csrf/')
}
