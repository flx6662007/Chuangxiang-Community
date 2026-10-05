import http from '../api/http'
import { createResourceReader } from './resourceClient'

// 始终读取后端；接口失败不回退为示例数据。
export const { listResources, getResource, listResourceTaxonomies } = createResourceReader(http)
