import http from './http'
import { createCatalogSearchReader } from './catalogSearchClient.js'

// 关键词检索真实资料库，不调用聊天模型。
export const searchCatalog = createCatalogSearchReader(http).search
