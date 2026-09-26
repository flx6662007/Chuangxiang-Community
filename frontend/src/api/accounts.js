import axios from 'axios'
import { announceSessionChange } from '../utils/sessionEvents'
import http, { useCsrf } from './http'
import {
  csrfFromCookie,
  isFinishedPasswordReset,
  isPendingPasswordReset,
  isSignedOut,
  withProfileSessionCheck,
} from '../utils/account'

const auth = useCsrf(
  axios.create({
    baseURL: import.meta.env.VITE_AUTH_BASE_URL || '/api/auth/browser/v1',
    timeout: 15000,
    withCredentials: true,
  }),
)

const sessionStatus = (status) => status === 200 || status === 401
const readSession = () =>
  auth.get('/auth/session', { validateStatus: sessionStatus })

function unexpectedResponse(response) {
  const error = new Error('Account flow was not completed')
  error.response = response
  throw error
}

export async function ensureCsrf() {
  if (!csrfFromCookie(document.cookie)) await http.get('/accounts/csrf/')
}

export async function getProfile() {
  return withProfileSessionCheck(
    async () => (await http.get('/accounts/me/')).data,
    readSession,
  )
}

export async function getSessionProfile() {
  const response = await readSession()
  if (response.status === 401 && isSignedOut(response.data)) return null
  if (response.status !== 200 || response.data?.meta?.is_authenticated !== true)
    unexpectedResponse(response)
  return getProfile()
}

export async function signIn(email, password, register = false) {
  await auth.post(register ? '/auth/signup' : '/auth/login', {
    email,
    password,
  })
  announceSessionChange()
  return getProfile()
}

export async function signOut() {
  const response = await auth.delete('/auth/session', {
    validateStatus: sessionStatus,
  })
  if (!isSignedOut(response.data)) unexpectedResponse(response)
  announceSessionChange()
}

export async function saveContacts(contacts) {
  return withProfileSessionCheck(
    async () => (await http.patch('/accounts/me/', contacts)).data,
    readSession,
  )
}

export async function sendVerification(email) {
  await auth.put('/account/email', { email })
}

export async function verifyEmail(key) {
  await auth.post('/auth/email/verify', { key })
  return getProfile()
}

export async function requestPasswordReset(email) {
  const response = await auth.post(
    '/auth/password/request',
    { email },
    { validateStatus: sessionStatus },
  )
  if (!isPendingPasswordReset(response.data)) unexpectedResponse(response)
}

export async function resetPassword(key, password) {
  const response = await auth.post(
    '/auth/password/reset',
    { key, password },
    { validateStatus: sessionStatus },
  )
  if (!isFinishedPasswordReset(response.data)) unexpectedResponse(response)
  announceSessionChange()
}
