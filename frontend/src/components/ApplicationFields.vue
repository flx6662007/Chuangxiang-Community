<script setup>
import OptionPicker from './OptionPicker.vue'
defineProps({ modelValue: Object, dictionaries: Object, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
function update(form, key, value) {
  emit('update:modelValue', { ...form, [key]: value })
}
</script>
<template>
  <div class="application-fields">
    <OptionPicker
      :model-value="modelValue.desired_roles"
      :options="dictionaries.roles"
      label="意向角色（选填）"
      multiple
      :disabled="disabled"
      @update:model-value="update(modelValue, 'desired_roles', $event)"
    />
    <OptionPicker
      :model-value="modelValue.skills"
      :options="dictionaries.skills"
      label="已有技能（选填）"
      multiple
      :disabled="disabled"
      @update:model-value="update(modelValue, 'skills', $event)"
    />
    <OptionPicker
      :model-value="modelValue.weekly_effort"
      :options="dictionaries.weekly_effort"
      label="每周可投入时间"
      required
      :disabled="disabled"
      @update:model-value="update(modelValue, 'weekly_effort', $event)"
    />
  </div>
</template>
