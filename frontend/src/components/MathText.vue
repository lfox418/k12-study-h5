<template>
  <span class="leading-relaxed break-words" v-html="renderedHtml"></span>
</template>

<script setup>
import { computed } from 'vue'
import { renderLatexText } from '../utils/latex'

const props = defineProps({
  content: { type: String, default: '' }
})

const renderedHtml = computed(() => renderLatexText(props.content))
</script>
