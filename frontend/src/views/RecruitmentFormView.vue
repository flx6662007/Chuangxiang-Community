<script setup>
import { recruitmentDeadline } from '../utils/teams'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSessionProfile } from '../api/accounts'
import { getCompetition, listCompetitions } from '../api/competitions'
import {
  createRecruitment,
  editRecruitment,
  getRecruitment,
  getRecruitmentOptions,
  getTeam,
  previewRecruitment,
} from '../api/teams'
import {
  can,
  cleanRecruitmentInput,
  recruitmentInput,
  teamError,
  withHistoricalOptions,
} from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
import OptionPicker from '../components/OptionPicker.vue'
const route = useRoute(),
  router = useRouter(),
  editing = computed(() => route.name === 'recruitment-edit')
const dictionaries = ref({}),
  record = ref(null),
  profile = ref(null),
  selected = ref(null),
  loading = ref(true),
  error = ref(''),
  busy = ref(false),
  conflict = ref(false),
  preview = ref(null),
  acknowledged = ref(false)
const form = reactive(recruitmentInput()),
  duration = ref(7),
  search = ref(''),
  candidates = ref([]),
  candidatePage = ref(1),
  candidateCount = ref(0),
  searching = ref(false),
  searched = ref(false),
  searchError = ref('')
const allowed = computed(() =>
  editing.value
    ? can(record.value, 'edit')
    : profile.value?.account_eligibility?.eligible === true,
)
let serial = 0,
  searchSerial = 0,
  controller,
  searchController
function payload() {
  return {
    ...cleanRecruitmentInput(form),
    ...(editing.value
      ? { expected_version: record.value.version }
      : {
          competition_id: selected.value?.id,
          duration_days: Number(duration.value),
          ...(route.query.team_id
            ? { team_id: Number(route.query.team_id) }
            : {}),
        }),
  }
}
async function load() {
  const request = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  preview.value = null
  conflict.value = false
  try {
    const [options, user] = await Promise.all([
      getRecruitmentOptions(controller.signal),
      getSessionProfile(),
    ])
    if (request !== serial) return
    dictionaries.value = options
    profile.value = user
    if (editing.value) {
      const data = await getRecruitment(route.params.id, controller.signal)
      if (request !== serial) return
      record.value = data
      Object.assign(form, recruitmentInput(data))
      form.existing_member_count = data.current_existing_member_count
      selected.value = data.competition
      dictionaries.value = {
        ...options,
        roles: withHistoricalOptions(options.roles, data.required_roles),
        skills: withHistoricalOptions(options.skills, [
          ...data.current_skills,
          ...data.required_skills,
        ]),
        campuses: withHistoricalOptions(options.campuses, data.campuses),
      }
    } else if (route.query.team_id) {
      const team = await getTeam(route.query.team_id, controller.signal)
      if (request !== serial) return
      selected.value = team.competition
      form.existing_member_count =
        team.memberships.filter((member) => !member.ended_at).length || 1
    } else if (route.query.competition_id) {
      const competition = await getCompetition(
        route.query.competition_id,
        controller.signal,
      )
      if (request !== serial) return
      selected.value = competition
    }
  } catch (err) {
    if (request === serial && err.code !== 'ERR_CANCELED')
      error.value = teamError(err)
  } finally {
    if (request === serial) loading.value = false
  }
}
async function findCompetitions(page = 1) {
  const request = ++searchSerial
  searchController?.abort()
  searchController = new AbortController()
  searching.value = true
  searchError.value = ''
  try {
    const data = await listCompetitions(
      {
        search: search.value.trim(),
        page,
        page_size: 10,
        recruitment_open: true,
      },
      searchController.signal,
    )
    if (request === searchSerial) {
      searched.value = true
      candidates.value = data.results
      candidatePage.value = page
      candidateCount.value = data.count
    }
  } catch (err) {
    if (request === searchSerial && err.code !== 'ERR_CANCELED')
      searchError.value = teamError(err)
  } finally {
    if (request === searchSerial) searching.value = false
  }
}
async function submit() {
  if (busy.value || !allowed.value || conflict.value) return
  error.value = ''
  busy.value = true
  try {
    if (!editing.value && !preview.value) {
      preview.value = await previewRecruitment(payload())
      acknowledged.value = false
      return
    }
    if (!acknowledged.value) return
    const data = editing.value
      ? await editRecruitment(record.value.id, payload())
      : await createRecruitment(payload())
    await router.push({ name: 'recruitment-detail', params: { id: data.id } })
  } catch (err) {
    error.value = teamError(err)
    if (err.response?.status === 409) conflict.value = true
    preview.value = null
  } finally {
    busy.value = false
  }
}
watch(
  [form, duration, selected],
  () => {
    preview.value = null
    acknowledged.value = false
  },
  { deep: true },
)
watch(
  () => [
    route.name,
    route.params.id,
    route.query.team_id,
    route.query.competition_id,
  ],
  load,
  { immediate: true },
)
onBeforeUnmount(() => {
  serial++
  searchSerial++
  controller?.abort()
  searchController?.abort()
})
</script>
<template>
  <section class="recruitment-editor">
    <RouterLink class="back-link" to="/teams">← 团队广场</RouterLink>
    <header class="page-heading">
      <span class="section-kicker">BUILD A TEAM</span>
      <h1>{{ editing ? '编辑招募' : '发布招募' }}</h1>
      <p>选定赛事，填写固定条件，让期待更清楚。</p>
    </header>
    <div v-if="loading" class="state-panel" role="status">正在加载表单…</div>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <div v-if="!loading && !allowed" class="state-panel">
      <p>
        {{
          editing
            ? '当前无权编辑此招募，或招募状态已变化。'
            : '发布招募需登录、核验学校邮箱，并填写个人联系方式。'
        }}
      </p>
      <RouterLink class="action-button" to="/account">检查账号状态</RouterLink
      ><button class="action-button secondary" @click="load">重新加载</button>
    </div>
    <form v-else-if="!loading" class="team-panel" @submit.prevent="submit">
      <fieldset class="plain-fieldset" :disabled="busy || conflict">
        <legend class="form-section-title">1. 所属赛事</legend>
        <div v-if="selected" class="selected-competition">
          <div>
            <strong>{{ selected.title }}</strong>
            <p>
              {{ selected.edition }}
              <span v-if="editing">· 当前卡片版本 {{ record.version }}</span>
            </p>
          </div>
          <button
            v-if="!editing && !route.query.team_id"
            type="button"
            class="text-button"
            @click="selected = null"
          >
            更换赛事
          </button>
        </div>
        <div v-if="!editing && !route.query.team_id && !selected">
          <div class="inline-search">
            <label class="sr-only" for="select-competition-search"
              >搜索已收录赛事</label
            ><input
              id="select-competition-search"
              v-model="search"
              type="search"
              maxlength="200"
              placeholder="输入赛事名称"
              @keydown.enter.prevent="findCompetitions()"
            /><button
              class="action-button secondary"
              type="button"
              :disabled="searching"
              @click="findCompetitions()"
            >
              查找赛事
            </button>
          </div>
          <p class="muted">仅可选择已收录且允许招募的具体赛事届次。</p>
          <p v-if="searchError" role="alert">{{ searchError }}</p>
          <p v-if="searching" role="status">正在搜索…</p>
          <p v-else-if="searched && !candidates.length" class="notice-text">
            未找到可招募赛事。请换一个关键词，或检查赛事是否已收录并开放招募。
          </p>
          <ul v-else class="competition-picker">
            <li v-for="competition in candidates" :key="competition.id">
              <span>{{ competition.title }} · {{ competition.edition }}</span
              ><button
                type="button"
                class="text-button"
                :disabled="!competition.is_recruitment_open"
                @click="selected = competition"
              >
                {{ competition.is_recruitment_open ? '选择' : '未开放招募' }}
              </button>
            </li>
          </ul>
          <div v-if="candidateCount > 10" class="button-row">
            <button
              type="button"
              class="text-button"
              :disabled="candidatePage === 1"
              @click="findCompetitions(candidatePage - 1)"
            >
              上一页</button
            ><span
              >{{ candidatePage }} / {{ Math.ceil(candidateCount / 10) }}</span
            ><button
              type="button"
              class="text-button"
              :disabled="candidatePage * 10 >= candidateCount"
              @click="findCompetitions(candidatePage + 1)"
            >
              下一页
            </button>
          </div>
        </div>
      </fieldset>
      <fieldset class="plain-fieldset" :disabled="busy || conflict">
        <legend class="form-section-title">2. 人数与能力</legend>
        <div class="form-grid">
          <label class="form-field"
            ><span>申报已有成员数（含本人） *</span
            ><input
              v-model.number="form.existing_member_count"
              type="number"
              min="1"
              step="1"
              required /></label
          ><label class="form-field"
            ><span>本轮计划招募人数 *</span
            ><input
              v-model.number="form.recruitment_quota"
              type="number"
              :min="editing ? 0 : 1"
              step="1"
              required
          /></label>
        </div>
        <OptionPicker
          v-model="form.current_skills"
          :options="dictionaries.skills"
          label="团队已有能力（选填）"
          multiple
        /><OptionPicker
          v-model="form.required_roles"
          :options="dictionaries.roles"
          label="所需角色（选填）"
          multiple
        /><OptionPicker
          v-model="form.required_skills"
          :options="dictionaries.skills"
          label="所需技能（选填）"
          multiple
        />
      </fieldset>
      <fieldset class="plain-fieldset" :disabled="busy || conflict">
        <legend class="form-section-title">3. 合作安排</legend>
        <div class="form-grid">
          <OptionPicker
            v-model="form.foundation_requirement"
            :options="dictionaries.foundation_requirement"
            label="基础要求"
            required
          /><OptionPicker
            v-model="form.weekly_effort"
            :options="dictionaries.weekly_effort"
            label="每周投入"
            required
          /><OptionPicker
            v-model="form.collaboration_mode"
            :options="dictionaries.collaboration_mode"
            label="协作方式"
            required
          /><OptionPicker
            v-model="form.collaboration_goal"
            :options="dictionaries.collaboration_goal"
            label="合作目标（选填）"
          /><OptionPicker
            v-model="form.expected_duration"
            :options="dictionaries.expected_duration"
            label="入队后合作时长（选填）"
          /><OptionPicker
            v-if="!editing"
            v-model="duration"
            :options="dictionaries.duration_days"
            label="招募有效期"
            required
          />
        </div>
        <OptionPicker
          v-if="form.collaboration_mode && form.collaboration_mode !== 'online'"
          v-model="form.campuses"
          :options="dictionaries.campuses"
          label="协作校区（线下或混合必选）"
          multiple
        />
        <p v-if="editing" class="notice-text">
          编辑不延长有效期。本卡实际到期：{{
            formatUpdatedAt(recruitmentDeadline(record))
          }}。
        </p>
      </fieldset>
      <div v-if="preview" class="notice-text">
        <strong>已完成发布前校验</strong>
        <p>
          实际到期：{{
            formatUpdatedAt(recruitmentDeadline(preview))
          }}。若赛事招募截止更早，以该时间为准。
        </p>
      </div>
      <label v-if="editing || preview" class="consent-row"
        ><input
          v-model="acknowledged"
          type="checkbox"
          required
          :disabled="busy || conflict"
        /><span>{{
          editing
            ? '我已核对变更。实际修改将通知成员并挂起未完成申请，双方需要针对新条件重新确认。'
            : '我已核对赛事、人数、条件与实际到期时间，确认发布本轮招募。'
        }}</span></label
      >
      <div v-if="conflict" class="notice-text" role="alert">
        状态已变化。为避免覆盖新内容，已暂停提交。<button
          type="button"
          class="text-button"
          @click="load"
        >
          读取最新内容并重新核对
        </button>
      </div>
      <button
        class="action-button"
        :disabled="
          busy ||
          conflict ||
          !selected ||
          ((editing || preview) && !acknowledged)
        "
      >
        {{
          busy
            ? '处理中…'
            : editing
              ? '保存修改'
              : preview
                ? '确认发布'
                : '校验并预览有效期'
        }}
      </button>
    </form>
  </section>
</template>
