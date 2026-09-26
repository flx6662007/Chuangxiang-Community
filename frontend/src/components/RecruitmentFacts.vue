<script setup>
import { label, optionNames } from '../utils/teams'
defineProps({ revision: { type: Object, required: true } })
</script>
<template>
  <dl class="recruitment-facts">
    <div>
      <dt>申报已有成员</dt>
      <dd>{{ revision.existing_member_count }} 人（含招募者）</dd>
    </div>
    <div>
      <dt>本轮计划招募</dt>
      <dd>{{ revision.recruitment_quota }} 人</dd>
    </div>
    <div>
      <dt>团队已有能力</dt>
      <dd>{{ optionNames(revision.current_skills) }}</dd>
    </div>
    <div>
      <dt>所需角色</dt>
      <dd>{{ optionNames(revision.required_roles) }}</dd>
    </div>
    <div>
      <dt>所需技能</dt>
      <dd>{{ optionNames(revision.required_skills) }}</dd>
    </div>
    <div>
      <dt>基础要求</dt>
      <dd>{{ label(revision.foundation_requirement) }}</dd>
    </div>
    <div>
      <dt>每周投入</dt>
      <dd>{{ label(revision.weekly_effort) }}</dd>
    </div>
    <div>
      <dt>协作方式</dt>
      <dd>{{ label(revision.collaboration_mode) }}</dd>
    </div>
    <div v-if="revision.collaboration_mode !== 'online'">
      <dt>协作校区</dt>
      <dd>{{ optionNames(revision.campuses) }}</dd>
    </div>
    <div>
      <dt>合作目标</dt>
      <dd>{{ label(revision.collaboration_goal) }}</dd>
    </div>
    <div>
      <dt>合作时长</dt>
      <dd>{{ label(revision.expected_duration) }}</dd>
    </div>
  </dl>
</template>
