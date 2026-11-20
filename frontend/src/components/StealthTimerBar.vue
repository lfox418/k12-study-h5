<template>
  <div class="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-slate-100 px-4 py-2.5 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="text-slate-500 hover:text-slate-800 text-sm font-medium px-2 py-1 rounded-lg bg-slate-100"
        @click="$emit('exit')"
      >
        返回大厅
      </button>
      <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
        {{ title }}
      </span>
    </div>

    <!-- 前 20 分钟（剩余 > 10 分钟）：完全隐藏倒计时数字，呈现平和状态 -->
    <transition name="van-slide-down" mode="out-in">
      <div
        v-if="remaining > hideThreshold"
        key="stealth"
        class="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium"
      >
        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        <span>沉浸学习中</span>
      </div>

      <!-- 最后 10 分钟（剩余 <= 10 分钟）：柔和滑出倒计时胶囊；最后 2 分钟红色呼吸脉冲 -->
      <div
        v-else
        key="sprint"
        class="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tabular-nums transition-colors"
        :class="remaining <= urgentThreshold
          ? 'bg-rose-600 text-white animate-urgent-pulse'
          : 'bg-amber-100 text-amber-800 border border-amber-300'"
      >
        <span>⏱</span>
        <span>剩余 {{ formattedTime }}</span>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  expiresAt: { type: Number, required: true },
  clockOffset: { type: Number, default: 0 },
  hideThreshold: { type: Number, default: 600 },   // 10 分钟 = 600 秒
  urgentThreshold: { type: Number, default: 120 }, // 2 分钟 = 120 秒
  paused: { type: Boolean, default: false }
})

const emit = defineEmits(['expired', 'exit'])

const remaining = ref(1800)
let timer = null
let expiredEmitted = false

function tick() {
  if (props.paused) return
  const serverNow = Math.floor(Date.now() / 1000) + props.clockOffset
  const diff = Math.max(0, props.expiresAt - serverNow)
  remaining.value = diff
  if (diff <= 0 && !expiredEmitted) {
    expiredEmitted = true
    emit('expired')
  }
}

const formattedTime = computed(() => {
  const m = Math.floor(remaining.value / 60)
  const s = remaining.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

onMounted(() => {
  tick()
  timer = setInterval(tick, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>
