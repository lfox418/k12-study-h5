<template>
  <van-popup
    :show="show"
    round
    position="bottom"
    :style="{ maxWidth: '480px', margin: '0 auto', left: 0, right: 0 }"
    @update:show="$emit('update:show', $event)"
  >
    <div v-if="wordItem" class="p-6">
      <div class="flex items-start justify-between">
        <div>
          <span class="inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 mb-2">
            只读记忆卡片 · 不参与复核与计分
          </span>
          <h3 class="text-3xl font-black text-slate-900 tracking-tight">{{ wordItem.word }}</h3>
          <p class="text-sm text-indigo-600 font-mono mt-1">{{ wordItem.phonetic || '/—/' }}</p>
        </div>
        <button
          type="button"
          class="w-11 h-11 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-xl active:scale-95 transition"
          title="朗读发音"
          @click="speakWord(wordItem.word)"
        >
          🔊
        </button>
      </div>

      <div class="mt-4 p-3.5 rounded-2xl bg-slate-50 border border-slate-100">
        <div class="text-xs text-slate-400 mb-1">核心释义</div>
        <div class="text-base font-semibold text-slate-800">{{ wordItem.meaning }}</div>
      </div>

      <div v-if="wordItem.examples?.length" class="mt-4 space-y-2.5">
        <div class="text-xs font-semibold text-slate-400">场景例句</div>
        <div
          v-for="(ex, i) in wordItem.examples"
          :key="i"
          class="p-3 rounded-xl bg-indigo-50/50 border border-indigo-100/70"
        >
          <div class="flex items-start justify-between gap-2">
            <p class="text-sm text-slate-800 leading-snug">{{ ex.en }}</p>
            <button
              type="button"
              class="shrink-0 text-indigo-600 text-sm px-1.5"
              @click="speakWord(ex.en)"
              >
                {{ ttsState.loadingText === currentWord.word ? '⏳' : '🔊' }}
            </button>
          </div>
          <p v-if="ex.zh" class="text-xs text-slate-500 mt-1">{{ ex.zh }}</p>
        </div>
      </div>

      <van-button
        block
        round
        type="primary"
        color="#4f46e5"
        class="mt-6"
        @click="$emit('update:show', false)"
      >
        关闭卡片
      </van-button>
    </div>
  </van-popup>
</template>

<script setup>
import { speakWord, ttsState } from '../utils/sound'

defineProps({
  show: { type: Boolean, default: false },
  wordItem: { type: Object, default: null }
})

defineEmits(['update:show'])
</script>
