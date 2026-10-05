import http from '../api/http'
import { createAssistantReader } from './assistantClient.js'

// 模型接入前通过同一服务入口检索真实资料库。
export const searchCompetitionsByAI = createAssistantReader(http).search
