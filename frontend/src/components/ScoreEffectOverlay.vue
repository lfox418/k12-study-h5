<template>
  <transition name="van-fade">
    <div
      v-if="store.effectState.visible"
      class="fixed inset-0 z-50 pointer-events-none flex flex-col items-center justify-center bg-slate-900/20 backdrop-blur-[1px]"
    >
      <!-- 屏幕中央巨大 3D 质感立体数字 -->
      <div
        class="text-center px-6 py-4 rounded-3xl"
        :class="store.effectState.type === 'bonus' ? 'score-3d-text' : 'score-penalty-text'"
      >
        <div class="text-5xl font-black tracking-tight">
          {{ store.effectState.headline }}
        </div>
        <div
          v-if="store.effectState.subline"
          class="mt-2 inline-block px-4 py-1.5 rounded-full text-sm font-bold shadow-lg"
          :class="store.effectState.type === 'bonus'
            ? 'bg-amber-400 text-amber-950'
            : 'bg-rose-600 text-white'"
        >
          {{ store.effectState.subline }}
        </div>
      </div>

      <!-- 金币飞入顶部“我的积分”胶囊动效 -->
      <template v-if="store.effectState.type === 'bonus'">
        <div
          v-for="coin in coins"
          :key="coin.id"
          class="flying-coin"
          :style="{
            '--tx': coin.tx,
            '--ty': coin.ty,
            animationDelay: coin.delay
          }"
        >
          ¥
        </div>
      </template>
    </div>
  </transition>
</template>

<script setup>
import { watch } from 'vue'
import confetti from 'canvas-confetti'
import { useStudyStore } from '../stores/studyStore'
import { playPenaltyTone, playSuccessChime } from '../utils/sound'

const store = useStudyStore()

const coins = [
  { id: 1, tx: '120px', ty: '-340px', delay: '0ms' },
  { id: 2, tx: '105px', ty: '-360px', delay: '70ms' },
  { id: 3, tx: '135px', ty: '-325px', delay: '140ms' },
  { id: 4, tx: '115px', ty: '-350px', delay: '210ms' },
  { id: 5, tx: '125px', ty: '-335px', delay: '280ms' }
]

watch(
  () => store.effectState.visible,
  (val) => {
    if (!val) return
    if (store.effectState.type === 'bonus') {
      const isGrand = store.effectState.subline.includes('每日通关奖励')
      playSuccessChime(isGrand)
      // canvas-confetti 全屏礼花 + 星星雨
      confetti({
        particleCount: isGrand ? 110 : 65,
        spread: 85,
        origin: { y: 0.6 },
        colors: ['#facc15', '#4f46e5', '#10b981', '#f97316', '#ec4899']
      })
      if (isGrand) {
        setTimeout(() => {
          confetti({
            particleCount: 55,
            spread: 110,
            shapes: ['star'],
            origin: { y: 0.45 },
            colors: ['#fde047', '#f59e0b', '#fef08a']
          })
        }, 260)
      }
    } else {
      playPenaltyTone()
    }
  }
)
</script>
