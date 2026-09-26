import http from './http'
import { ensureCsrf } from './accounts'
const id = (value) => encodeURIComponent(value)
const read = async (path, params, signal) =>
  (await http.get(path, { params, signal })).data
const write = async (path, body = {}, method = 'post') => {
  await ensureCsrf()
  return (await http[method](path, body)).data
}
export const getRecruitmentOptions = (signal) =>
  read('/recruitments/options/', undefined, signal)
export const listRecruitments = (params, signal) =>
  read('/recruitments/', params, signal)
export const getRecruitment = (value, signal) =>
  read(`/recruitments/${id(value)}/`, undefined, signal)
export const previewRecruitment = (body) =>
  write('/recruitments/preview/', body)
export const createRecruitment = (body) => write('/recruitments/', body)
export const editRecruitment = (value, body) =>
  write(`/recruitments/${id(value)}/`, body, 'patch')
export const closeRecruitment = (value, body) =>
  write(`/recruitments/${id(value)}/close/`, body)
export const applyToRecruitment = (value, body) =>
  write(`/recruitments/${id(value)}/applications/`, body)
export const listApplications = (params, signal) =>
  read('/applications/', params, signal)
export const getApplication = (value, signal) =>
  read(`/applications/${id(value)}/`, undefined, signal)
export const applicationAction = (value, action, body) =>
  write(`/applications/${id(value)}/${id(action)}/`, body)
export const getApplicationContact = (value, signal) =>
  read(`/applications/${id(value)}/contact/`, undefined, signal)
export const listMyTeams = (params, signal) =>
  read('/teams/mine/', params, signal)
export const getTeam = (value, signal) =>
  read(`/teams/${id(value)}/`, undefined, signal)
export const requestDeparture = (value, kind) =>
  write(`/memberships/${id(value)}/departure-requests/`, { kind })
export const departureAction = (value, action, body) =>
  write(`/departure-requests/${id(value)}/${id(action)}/`, body)
export const requestDissolution = (value) =>
  write(`/teams/${id(value)}/dissolution-requests/`, { confirm: true })
export const dissolutionAction = (value, action, body) =>
  write(`/dissolution-requests/${id(value)}/${id(action)}/`, body)
