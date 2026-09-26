<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  ensureCsrf,
  getSessionProfile,
  requestPasswordReset,
  resetPassword,
  saveContacts,
  sendVerification,
  signIn,
  signOut,
  verifyEmail,
} from '../api/accounts'
import { accountErrorMessages } from '../utils/account'
import { formatUpdatedAt } from '../utils/competition'
import AppIcon from '../components/AppIcon.vue'

const user = ref(null)
const initializing = ref(true)
const initializationFailed = ref(false)
const mode = ref('login')
const busy = ref('')
const errors = ref([])
const message = ref('')
const cooldown = ref(0)
const credentials = reactive({
  email: '',
  password: '',
  confirm: '',
  resetKey: '',
})
const contacts = reactive({ wechat_id: '', phone_number: '' })
const verificationCode = ref('')
const title = computed(
  () =>
    ({
      login: '登录',
      signup: '注册账号',
      recover: '找回密码',
      reset: '设置新密码',
    })[mode.value],
)
const reasonLabels = {
  email_unverified: '学校邮箱待验证',
  contact_required: '联系方式待补充',
  account_restricted: '账号暂时限制新增发布和申请',
  account_disabled: '账号已停用',
  login_required: '请先登录',
}
let timer

function updateUser(profile) {
  user.value = profile
  contacts.wechat_id = profile?.wechat_id || ''
  contacts.phone_number = profile?.phone_number || ''
}

function clearPasswords() {
  credentials.password = ''
  credentials.confirm = ''
  credentials.resetKey = ''
}

function clearSignedOutState() {
  updateUser(null)
  clearPasswords()
  verificationCode.value = ''
  credentials.email = ''
  cooldown.value = 0
  mode.value = 'login'
  message.value = ''
  initializationFailed.value = false
}

function selectMode(next) {
  if (busy.value) return
  mode.value = next
  errors.value = []
  message.value = ''
  clearPasswords()
}

async function loadSession() {
  initializing.value = true
  initializationFailed.value = false
  errors.value = []
  try {
    await ensureCsrf()
    const profile = await getSessionProfile()
    if (profile) updateUser(profile)
    else clearSignedOutState()
  } catch (error) {
    if (error.sessionExpired) clearSignedOutState()
    else initializationFailed.value = true
    errors.value = accountErrorMessages(error)
  } finally {
    initializing.value = false
  }
}

async function runAction(name, action) {
  if (busy.value) return
  busy.value = name
  errors.value = []
  message.value = ''
  try {
    await ensureCsrf()
    await action()
  } catch (error) {
    if (error.sessionExpired) clearSignedOutState()
    errors.value = accountErrorMessages(error, name)
    if (error.response?.status === 429 && ['send', 'recover'].includes(name))
      cooldown.value = 60
  } finally {
    busy.value = ''
  }
}

async function submitCredentials() {
  const email = credentials.email.trim().toLowerCase()
  if (!/^[^@\s]+@tongji\.edu\.cn$/.test(email)) {
    errors.value = ['请使用 @tongji.edu.cn 学校邮箱。']
    return
  }
  if (
    ['signup', 'reset'].includes(mode.value) &&
    credentials.password !== credentials.confirm
  ) {
    errors.value = ['两次输入的密码不一致。']
    return
  }
  const currentMode = mode.value
  await runAction(currentMode, async () => {
    if (currentMode === 'recover') {
      await requestPasswordReset(email)
      mode.value = 'reset'
      cooldown.value = 60
      message.value =
        '如该邮箱已注册，将收到重置验证码。请在本页面输入，并在 10 分钟内完成。'
    } else if (currentMode === 'reset') {
      await resetPassword(credentials.resetKey.trim(), credentials.password)
      clearPasswords()
      mode.value = 'login'
      message.value = '密码已更新，请使用新密码登录。'
    } else {
      updateUser(
        await signIn(email, credentials.password, currentMode === 'signup'),
      )
      clearPasswords()
      message.value =
        currentMode === 'signup'
          ? '注册成功，请继续验证学校邮箱。'
          : '登录成功。'
    }
  })
}

function submitContacts() {
  return runAction('contacts', async () => {
    updateUser(
      await saveContacts({
        wechat_id: contacts.wechat_id.trim(),
        phone_number: contacts.phone_number.trim(),
      }),
    )
    message.value = '联系方式已保存。'
  })
}

function sendCode() {
  return runAction('send', async () => {
    await sendVerification(user.value.email)
    cooldown.value = 60
    message.value =
      '验证码已发送。本次验证从首次发送起 10 分钟有效，重发不会延长有效期，请使用最新收到的验证码。'
  })
}

function submitVerification() {
  return runAction('verify', async () => {
    updateUser(await verifyEmail(verificationCode.value.trim()))
    verificationCode.value = ''
    if (user.value.school_email_verified) message.value = '学校邮箱验证成功。'
    else errors.value = ['暂未确认验证结果，请刷新账号状态。']
  })
}

function logout() {
  return runAction('logout', async () => {
    await signOut()
    clearSignedOutState()
    message.value = '已退出登录。'
  })
}

onMounted(() => {
  loadSession()
  timer = setInterval(() => {
    if (cooldown.value > 0) cooldown.value--
  }, 1000)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  clearPasswords()
})
</script>

<template>
  <section class="account-page" aria-labelledby="account-title">
    <header class="page-heading">
      <span class="section-kicker">MY ACCOUNT</span>
      <h1 id="account-title">我的账号</h1>
      <p>管理你的校园身份，准备下一次探索。</p>
    </header>
    <div v-if="errors.length" class="form-alert error" role="alert">
      <p v-for="(error, index) in errors" :key="index">{{ error }}</p>
      <button
        v-if="initializationFailed"
        class="action-button secondary"
        @click="loadSession"
      >
        重新加载
      </button>
    </div>
    <div v-if="message" class="form-alert success" role="status">
      {{ message }}
    </div>
    <div v-if="initializing" class="state-panel" role="status">
      正在加载账号状态…
    </div>
    <template v-else-if="!initializationFailed">
      <div v-if="!user" class="account-entry">
        <aside class="account-intro">
          <span class="service-icon"><AppIcon name="shield" :size="31" /></span>
          <h2>连接校园，<br />从一个好想法开始。</h2>
          <p>
            使用学校邮箱建立你的创享账号。<br />赛事信息无需登录，即可自由浏览。
          </p>
          <RouterLink class="more-link" :to="{ name: 'competitions' }"
            >先去发现赛事<AppIcon name="arrow" :size="17" /></RouterLink
          ><AppIcon class="account-intro-art" name="spark" :size="210" />
        </aside>
        <el-card class="account-panel" shadow="never">
          <div v-if="['login', 'signup'].includes(mode)" class="account-tabs">
            <button
              :class="{ active: mode === 'login' }"
              :disabled="!!busy"
              @click="selectMode('login')"
            >
              登录
            </button>
            <button
              :class="{ active: mode === 'signup' }"
              :disabled="!!busy"
              @click="selectMode('signup')"
            >
              注册
            </button>
          </div>
          <h2>{{ title }}</h2>
          <form class="account-form" @submit.prevent="submitCredentials">
            <label for="account-email">学校邮箱</label>
            <input
              id="account-email"
              v-model="credentials.email"
              type="email"
              autocomplete="username"
              maxlength="254"
              placeholder="你的邮箱@tongji.edu.cn"
              required
              :disabled="!!busy || mode === 'reset'"
            />
            <p class="field-hint">接受使用同济学校邮箱的各院系学生。</p>
            <template v-if="mode === 'reset'">
              <label for="reset-code">邮件中的重置验证码</label>
              <input
                id="reset-code"
                v-model="credentials.resetKey"
                autocomplete="one-time-code"
                maxlength="128"
                required
                :disabled="!!busy"
              />
            </template>
            <template v-if="mode !== 'recover'">
              <label for="account-password">{{
                mode === 'reset' ? '新密码' : '密码'
              }}</label>
              <input
                id="account-password"
                v-model="credentials.password"
                type="password"
                :autocomplete="
                  mode === 'login' ? 'current-password' : 'new-password'
                "
                :minlength="mode === 'login' ? undefined : 8"
                maxlength="256"
                required
                :disabled="!!busy"
              />
            </template>
            <template v-if="['signup', 'reset'].includes(mode)">
              <p class="field-hint">
                至少 8 位，请勿使用常见密码、纯数字或与邮箱相似的密码。
              </p>
              <label for="account-confirm">再次输入密码</label>
              <input
                id="account-confirm"
                v-model="credentials.confirm"
                type="password"
                autocomplete="new-password"
                maxlength="256"
                required
                :disabled="!!busy"
              />
            </template>
            <button
              class="action-button"
              type="submit"
              :disabled="!!busy || (mode === 'recover' && cooldown > 0)"
            >
              {{
                busy
                  ? '正在处理…'
                  : mode === 'recover'
                    ? cooldown > 0
                      ? `${cooldown} 秒后可再次发送`
                      : '发送重置验证码'
                    : mode === 'reset'
                      ? '保存新密码'
                      : title
              }}
            </button>
          </form>
          <div class="account-links">
            <button
              v-if="mode === 'login'"
              class="text-button"
              :disabled="!!busy"
              @click="selectMode('recover')"
            >
              忘记密码
            </button>
            <button
              v-if="['recover', 'reset'].includes(mode)"
              class="text-button"
              :disabled="!!busy"
              @click="selectMode('login')"
            >
              返回登录
            </button>
            <button
              v-if="mode === 'reset'"
              class="text-button"
              :disabled="!!busy || cooldown > 0"
              @click="selectMode('recover')"
            >
              {{
                cooldown > 0 ? `${cooldown} 秒后可重新发送` : '重新发送验证码'
              }}
            </button>
          </div>
        </el-card>
      </div>
      <template v-else>
        <el-card class="detail-section" shadow="never">
          <div class="account-heading">
            <h2>账号资料</h2>
            <button class="text-button" :disabled="!!busy" @click="logout">
              {{ busy === 'logout' ? '正在退出…' : '退出登录' }}
            </button>
          </div>
          <dl class="detail-facts">
            <div>
              <dt>系统代号</dt>
              <dd>{{ user.public_code }}</dd>
            </div>
            <div>
              <dt>学校邮箱</dt>
              <dd>{{ user.email }}</dd>
            </div>
            <div>
              <dt>邮箱核验</dt>
              <dd>{{ user.school_email_verified ? '已验证' : '待验证' }}</dd>
            </div>
          </dl>
          <div v-if="!user.school_email_verified" class="verification-box">
            <p class="muted">
              核验需要收取学校邮箱中的验证码。注册成功后，请点击下方按钮发送。
            </p>
            <button
              class="action-button secondary"
              :disabled="!!busy || cooldown > 0"
              @click="sendCode"
            >
              {{
                busy === 'send'
                  ? '正在发送…'
                  : cooldown > 0
                    ? `${cooldown} 秒后可重发`
                    : '发送 / 重发验证码'
              }}
            </button>
            <form
              class="verification-form"
              @submit.prevent="submitVerification"
            >
              <label for="email-code">6 位验证码</label>
              <input
                id="email-code"
                v-model="verificationCode"
                inputmode="numeric"
                pattern="[0-9]{6}"
                minlength="6"
                maxlength="6"
                autocomplete="one-time-code"
                required
                :disabled="!!busy"
              />
              <button class="action-button" :disabled="!!busy">
                {{ busy === 'verify' ? '正在验证…' : '验证邮箱' }}
              </button>
            </form>
            <p class="field-hint">
              本次验证从首次发送起 10
              分钟有效，重发不延长有效期。连续输错或超过重发次数后，请稍后重新发起验证。
            </p>
          </div>
        </el-card>
        <el-card class="detail-section" shadow="never">
          <h2>联系方式</h2>
          <p class="muted">
            微信号或手机号至少补充一项，用于后续组队联系。游客赛事页面不会展示这里的资料。
          </p>
          <form
            class="account-form contact-form"
            @submit.prevent="submitContacts"
          >
            <label for="wechat-id">微信号</label
            ><input
              id="wechat-id"
              v-model="contacts.wechat_id"
              maxlength="64"
              autocomplete="off"
              :disabled="!!busy"
            />
            <label for="phone-number">手机号</label
            ><input
              id="phone-number"
              v-model="contacts.phone_number"
              type="tel"
              maxlength="32"
              autocomplete="tel"
              :disabled="!!busy"
            />
            <button class="action-button" :disabled="!!busy">
              {{ busy === 'contacts' ? '正在保存…' : '保存联系方式' }}
            </button>
          </form>
        </el-card>
        <el-card class="detail-section" shadow="never">
          <h2>账号状态</h2>
          <p v-if="user.account_eligibility?.eligible">
            邮箱和联系方式已完善，账号当前满足新增发布与申请的基础条件。
          </p>
          <ul v-else class="account-reasons">
            <li
              v-for="reason in user.account_eligibility?.reasons || []"
              :key="reason"
            >
              {{ reasonLabels[reason] || '账号状态待核实' }}
            </li>
          </ul>
          <p v-if="user.account_eligibility?.restriction_ends_at" class="muted">
            限制到期：{{
              formatUpdatedAt(user.account_eligibility.restriction_ends_at)
            }}
          </p>
          <p class="muted">
            发布和申请还需符合赛事、队伍和名额条件；具体允许操作以最新状态为准。
          </p>
          <div class="stack-links">
            <RouterLink class="action-button secondary" to="/account/governance"
              >我的举报与申诉</RouterLink
            >
            <p class="field-hint">
              邮箱待核验或账号受限时，仍可查看记录并提交申诉。
            </p>
          </div>
          <button class="text-button" :disabled="!!busy" @click="loadSession">
            刷新账号状态
          </button>
        </el-card>
      </template>
    </template>
  </section>
</template>
