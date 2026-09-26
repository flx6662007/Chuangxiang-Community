import http from './http'
import { ensureCsrf } from './accounts'
const read = async (path, params, signal) =>
  (await http.get('/governance/' + path, { params, signal })).data
const write = async (path, body, signal) => {
  await ensureCsrf()
  return (await http.post('/governance/' + path, body, { signal })).data
}
export const getGovernanceOptions = (signal) =>
  read('options/', undefined, signal)
export const listMyReports = (params, signal) =>
  read('reports/', params, signal)
export const listMyAppeals = (params, signal) =>
  read('appeals/', params, signal)
export const listAppealTargets = (params, signal) =>
  read('appeal-targets/', params, signal)
export const createReport = (body, signal) => write('reports/', body, signal)
export const createAppeal = (body, signal) => write('appeals/', body, signal)
