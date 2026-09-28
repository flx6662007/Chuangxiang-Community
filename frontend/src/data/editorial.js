// 仅存可公开的人工内容；此 JSON 会打包进前端，不能放草稿、私人资料或内部审核记录。
// 后台信息库读取同一文件。后台数据库草稿与 AI 检索权限另行处理。
import editorial from '../../../backend/information_library/data/editorial.json'

export const newsletters = editorial.newsletters
export const laboratories = editorial.laboratories
