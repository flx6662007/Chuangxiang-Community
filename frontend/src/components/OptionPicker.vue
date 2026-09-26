<script setup>
defineProps({
  modelValue: { type: [String, Array, Number], required: true },
  options: { type: Array, default: () => [] },
  multiple: Boolean,
  required: Boolean,
  disabled: Boolean,
  label: String,
})
defineEmits(['update:modelValue'])
</script>
<template>
  <fieldset v-if="multiple" class="option-picker" :disabled="disabled">
    <legend>{{ label }}</legend>
    <div class="checkbox-options">
      <label
        v-for="option in options"
        :key="option.code"
        :class="{ selected: modelValue.includes(option.code) }"
      >
        <input
          type="checkbox"
          :value="option.code"
          :checked="modelValue.includes(option.code)"
          :disabled="option.inactive && !modelValue.includes(option.code)"
          @change="
            $emit(
              'update:modelValue',
              $event.target.checked
                ? [...modelValue, option.code]
                : modelValue.filter((value) => value !== option.code),
            )
          "
        />{{ option.name }}
      </label>
      <span v-if="!options.length" class="muted">暂无可选项</span>
    </div>
  </fieldset>
  <label v-else class="form-field"
    ><span
      >{{ label }}<span v-if="required" class="required-mark"> *</span></span
    >
    <select
      :value="modelValue"
      :required="required"
      :disabled="disabled"
      @change="$emit('update:modelValue', $event.target.value)"
    >
      <option value="">{{ required ? '请选择' : '未选择' }}</option>
      <option v-for="option in options" :key="option.code" :value="option.code">
        {{ option.name }}
      </option>
    </select>
  </label>
</template>
