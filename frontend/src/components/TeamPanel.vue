<script setup>
import { recruitmentDeadline } from '../utils/teams'
import { ref } from 'vue'
import {
  closeRecruitment,
  departureAction,
  dissolutionAction,
  requestDeparture,
  requestDissolution,
} from '../api/teams'
import { can, label, teamError } from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
const props = defineProps({ team: Object })
const emit = defineEmits(['refresh'])
const busy = ref(false),
  error = ref(''),
  pending = ref(null)
function prepare(type, target, action, response) {
  pending.value = { type, target, action, response }
  error.value = ''
}
async function run() {
  if (busy.value || !pending.value) return
  busy.value = true
  error.value = ''
  const item = pending.value
  try {
    if (item.type === 'close')
      await closeRecruitment(item.target.id, {
        expected_version: item.target.version,
      })
    if (item.type === 'member')
      await requestDeparture(item.target.id, item.action)
    if (item.type === 'dissolve') await requestDissolution(props.team.id)
    if (item.type === 'departure')
      await departureAction(
        item.target.id,
        item.action,
        item.response ? { response: item.response } : {},
      )
    if (item.type === 'dissolution')
      await dissolutionAction(
        item.target.id,
        item.action,
        item.response ? { response: item.response } : {},
      )
    pending.value = null
    emit('refresh', '操作已完成，已重新读取最新状态。')
  } catch (err) {
    error.value = teamError(err)
    pending.value = null
    emit('refresh', error.value)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <article class="team-panel">
    <div class="heading-with-actions">
      <div>
        <span class="tag" :class="{ neutral: team.dissolved_at }">{{
          team.dissolved_at
            ? '已解散'
            : team.is_recruiter
              ? '我发起的队伍'
              : '我参加的队伍'
        }}</span>
        <h2>{{ team.competition.title }}</h2>
        <p class="muted">{{ team.competition.edition }} · {{ team.code }}</p>
      </div>
      <RouterLink
        :to="{
          name: 'competition-detail',
          params: { id: team.competition.id },
        }"
        >赛事详情 →</RouterLink
      >
    </div>
    <p class="muted">
      此处记录平台成员关系，不代表赛事官方报名。未注册成员不在平台成员列表内。
    </p>
    <p class="muted">
      双方授权的联系方式可在“我提交的申请”或“我收到的申请”中查看。
    </p>
    <h3>平台成员</h3>
    <ul class="member-list">
      <li v-for="member in team.memberships" :key="member.id">
        <div>
          <strong
            >{{ member.user.public_code
            }}{{ member.is_self ? '（本人）' : '' }}</strong
          ><span class="tag neutral">{{
            member.is_recruiter ? '招募者' : '成员'
          }}</span>
          <p class="timestamp">
            加入：{{ formatUpdatedAt(member.joined_at)
            }}<template v-if="member.ended_at">
              · {{ label(member.end_reason) }}：{{
                formatUpdatedAt(member.ended_at)
              }}</template
            >
          </p>
        </div>
        <div class="button-row">
          <button
            v-if="can(member, 'exit')"
            class="text-button"
            :disabled="busy"
            @click="prepare('member', member, 'exit')"
          >
            申请退出</button
          ><button
            v-if="can(member, 'removal')"
            class="text-button"
            :disabled="busy"
            @click="prepare('member', member, 'removal')"
          >
            申请移除
          </button>
        </div>
      </li>
    </ul>
    <h3>本队招募记录</h3>
    <div v-for="card in team.recruitments" :key="card.id" class="history-row">
      <div>
        <RouterLink
          :to="{ name: 'recruitment-detail', params: { id: card.id } }"
          >招募卡 #{{ card.id }}</RouterLink
        ><span class="tag neutral">{{ label(card.status) }}</span>
        <p class="timestamp">
          剩余 {{ card.remaining_slots }} 人 · 到期
          {{ formatUpdatedAt(recruitmentDeadline(card)) }}
        </p>
      </div>
      <div class="button-row">
        <RouterLink
          v-if="can(card, 'edit')"
          :to="{ name: 'recruitment-edit', params: { id: card.id } }"
          >编辑</RouterLink
        ><button
          v-if="can(card, 'close')"
          class="text-button"
          :disabled="busy"
          @click="prepare('close', card)"
        >
          关闭本轮招募
        </button>
      </div>
    </div>
    <div class="button-row">
      <RouterLink
        v-if="can(team, 'publish')"
        class="action-button secondary"
        :to="{ name: 'recruitment-publish', query: { team_id: team.id } }"
        >发布本队新一轮招募</RouterLink
      ><button
        v-if="can(team, 'dissolve')"
        class="action-button secondary"
        :disabled="busy"
        @click="prepare('dissolve', team)"
      >
        申请整队解散
      </button>
    </div>
    <template
      v-for="[type, requests] in [
        ['departure', team.departure_requests],
        ['dissolution', team.dissolution_requests],
      ]"
      :key="type"
      ><section
        v-for="request in requests"
        :key="request.id"
        class="request-record"
      >
        <h3>
          {{
            type === 'departure' ? `${label(request.kind)}申请` : '整队解散申请'
          }}
          #{{ request.id }}
          <span class="tag neutral">{{ label(request.status) }}</span>
        </h3>
        <p v-if="type === 'departure'" class="muted">
          目标成员关系 #{{ request.membership_id
          }}{{
            request.is_initiator
              ? ' · 我发起'
              : request.is_responder
                ? request.status === 'pending'
                  ? ' · 待我回应'
                  : ' · 回应方为本人'
                : ''
          }}
        </p>
        <p class="timestamp">
          发起：{{ formatUpdatedAt(request.created_at) }} · 回应截止：{{
            formatUpdatedAt(request.deadline_at)
          }}
        </p>
        <p v-if="request.status === 'pending'" class="notice-text">
          {{
            type === 'departure'
              ? '明确拒绝将结束本次请求并保留成员关系；24 小时未回应则自动完成。'
              : '全部同意，或 24 小时到期且无人明确拒绝时完成解散；任一成员拒绝则保留队伍。等待期间暂停新增申请、入队及编辑。'
          }}
        </p>
        <ul v-if="request.responses?.length" class="compact-list">
          <li v-for="response in request.responses" :key="response.public_code">
            {{ response.public_code }}：{{
              response.excluded_at
                ? '已退出，不再需要回应'
                : response.response === 'agree'
                  ? '同意'
                  : response.response === 'reject'
                    ? '拒绝'
                    : '未回应'
            }}
          </li>
        </ul>
        <div class="button-row">
          <button
            v-if="can(request, 'respond')"
            class="action-button secondary"
            :disabled="busy"
            @click="prepare(type, request, 'respond', 'agree')"
          >
            同意</button
          ><button
            v-if="can(request, 'respond')"
            class="action-button secondary"
            :disabled="busy"
            @click="prepare(type, request, 'respond', 'reject')"
          >
            拒绝</button
          ><button
            v-if="can(request, 'withdraw')"
            class="text-button"
            :disabled="busy"
            @click="prepare(type, request, 'withdraw')"
          >
            撤回本次请求
          </button>
        </div>
      </section></template
    >
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <section v-if="pending" class="action-confirm">
      <h3>确认本次操作</h3>
      <p v-if="pending.type === 'close'">
        关闭本轮招募会结束未完成申请并收回相应联系授权，已有正式成员关系保留。本卡不能通过编辑重新开启。
      </p>
      <p v-else-if="pending.type === 'dissolve'">
        整队解散需其他平台成员全部同意，或固定 24
        小时内无人拒绝。没有其他成员时将立即解散。完成后结束全队平台关系和联系授权，无法恢复；不取消官方报名。
      </p>
      <p v-else-if="pending.type === 'member'">
        发起{{
          pending.action === 'exit' ? '退出' : '移除'
        }}请求，等待对方回应；明确拒绝会保留成员关系，24 小时未回应则完成。
      </p>
      <p v-else>
        确认{{
          pending.action === 'withdraw'
            ? '撤回本次请求'
            : pending.response === 'agree'
              ? '同意本次请求'
              : '拒绝本次请求并保留队伍关系'
        }}。
      </p>
      <div class="button-row">
        <button class="action-button" :disabled="busy" @click="run">
          {{ busy ? '处理中…' : '确认操作' }}</button
        ><button
          class="action-button secondary"
          :disabled="busy"
          @click="pending = null"
        >
          取消
        </button>
      </div>
    </section>
  </article>
</template>
