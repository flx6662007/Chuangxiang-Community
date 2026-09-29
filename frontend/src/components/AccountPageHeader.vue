<script setup>
defineProps({
  eyebrow: { type: String, required: true },
  title: { type: String, required: true },
  accent: { type: String, required: true },
  description: { type: String, required: true },
  index: { type: String, default: '01' },
  showNav: { type: Boolean, default: true },
})

const links = [
  { to: { name: 'account' }, label: '账户总览' },
  { to: { name: 'my-teams' }, label: '我的组队' },
  { to: { name: 'notifications' }, label: '系统通知' },
  { to: { name: 'governance' }, label: '我的举报与申诉' },
]
</script>

<template>
  <header class="information-hero account-hero">
    <div class="information-hero-inner">
      <p class="information-eyebrow">CHUANGXIANG / {{ eyebrow }}</p>
      <span class="information-index">ACCOUNT / {{ index }}</span>
      <h1>{{ title }}<span>{{ accent }}</span></h1>
      <p>{{ description }}</p>
    </div>
  </header>
  <nav v-if="showNav" class="account-section-nav" aria-label="账户栏目">
    <div class="account-section-nav-inner">
      <RouterLink
        v-for="link in links"
        :key="link.to.name"
        :to="link.to"
        exact-active-class="selected"
      >{{ link.label }}</RouterLink>
    </div>
  </nav>
</template>
