<template>
  <div class="pb-24 px-4 pt-4">
    <!-- 顶部推荐码与右上角剩余时间 + “我的积分”胶囊 -->
    <div class="flex items-center justify-between gap-2 bg-white rounded-2xl p-3.5 shadow-sm border border-slate-100">
      <div class="flex items-center gap-2.5 min-w-0">
        <div class="w-10 h-10 shrink-0 rounded-xl bg-indigo-600 text-white font-black flex items-center justify-center text-sm">
          K12
        </div>
        <div class="min-w-0">
          <div class="text-xs text-slate-400 truncate">
            {{ store.nickname ? `推荐码 ${store.referralCode}` : '当前档案推荐码' }}
          </div>
          <div class="text-sm font-black tracking-wider text-slate-800 truncate">{{ store.displayName }}</div>
        </div>
      </div>

      <div class="flex flex-col items-end gap-1.5 shrink-0">
        <div
          class="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold"
          :class="store.quota.total_remaining_minutes <= 0
            ? 'bg-rose-100 text-rose-700'
            : store.quota.total_remaining_minutes <= 10
              ? 'bg-amber-100 text-amber-800'
              : 'bg-emerald-50 text-emerald-700'"
        >
          <span>⏱</span>
          <span>剩余 {{ store.quota.total_remaining_minutes }} 分钟</span>
        </div>
        <div
          id="my-points-capsule"
          class="flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-gradient-to-r from-amber-400 to-orange-400 text-amber-950 font-black text-sm shadow-sm"
        >
          <span>🪙</span>
          <span>{{ store.totalPoints }} 分</span>
        </div>
      </div>
    </div>

    <!-- 今日通关徽章与每日时间配额状态条 -->
    <div class="mt-3 grid grid-cols-2 gap-2.5">
      <div class="rounded-2xl p-3 bg-white border border-slate-100 flex items-center justify-between">
        <span class="text-xs font-semibold text-slate-600">英语每日+5</span>
        <span
          class="text-[11px] font-bold px-2 py-0.5 rounded-full"
          :class="store.todayEnglishPassed ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'"
        >
          {{ store.todayEnglishPassed ? '已领取' : '待通关' }}
        </span>
      </div>
      <div class="rounded-2xl p-3 bg-white border border-slate-100 flex items-center justify-between">
        <span class="text-xs font-semibold text-slate-600">数学每日+5</span>
        <span
          class="text-[11px] font-bold px-2 py-0.5 rounded-full"
          :class="store.todayMathPassed ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'"
        >
          {{ store.todayMathPassed ? '已领取' : '待通关' }}
        </span>
      </div>
    </div>

    <div class="mt-2.5 bg-white rounded-2xl px-3.5 py-2.5 border border-slate-100 flex items-center justify-between text-[11px] text-slate-600">
      <span>今日学习配额（上限 40 分钟）</span>
      <span class="font-bold text-indigo-600">
        已用 {{ store.quota.total_used_minutes }} 分钟 / 总剩余 {{ store.quota.total_remaining_minutes }} 分钟
      </span>
    </div>

    <!-- 科目 A：英语多学段分级背词 -->
    <section class="mt-5 bg-white rounded-3xl p-5 shadow-sm border border-indigo-100/80">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600">
            科目 A · 10词/轮 · 30分钟通关
          </span>
          <h2 class="text-lg font-black text-slate-900 mt-1.5">英语分级背词</h2>
        </div>
        <span class="text-3xl">📘</span>
      </div>
      <p class="text-xs text-slate-500 mt-1">
        三阶动态词库（一级6 + 二级3 + 三级1），听音记忆后拼写全对过关（+1/-1分）。
      </p>
      <div class="mt-2 text-[11px] font-semibold" :class="store.quota.english_locked ? 'text-rose-500' : 'text-indigo-600'">
        今日英语：已用 {{ store.quota.english_used_minutes }} 分钟 / 剩余 {{ store.quota.english_remaining_minutes }} 分钟
      </div>

      <div class="mt-4 grid grid-cols-2 gap-2">
        <button
          v-for="stage in englishStages"
          :key="stage.value"
          type="button"
          class="py-2.5 px-3 rounded-xl text-xs font-bold border transition text-left"
          :class="selectedEnglishStage === stage.value
            ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
            : 'bg-slate-50 text-slate-700 border-slate-200 hover:border-indigo-300'"
          @click="selectedEnglishStage = stage.value"
        >
          <div>{{ stage.label }}</div>
          <div class="text-[10px] font-normal opacity-80 mt-0.5">{{ stage.desc }}</div>
        </button>
      </div>

      <van-button
        block
        round
        type="primary"
        :color="store.quota.english_locked ? '#94a3b8' : '#4f46e5'"
        class="mt-4 font-bold"
        :disabled="store.quota.english_locked"
        :loading="startingSubject === 'english'"
        @click="beginStudy('english', selectedEnglishStage)"
      >
        {{ store.quota.english_locked ? '今日英语时长已用完（明日再来）' : '开始今日英语学习（10 词）' }}
      </van-button>
    </section>

    <!-- 科目 B：初中数学每日三题 -->
    <section class="mt-4 bg-white rounded-3xl p-5 shadow-sm border border-teal-100/80">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-teal-50 text-teal-700">
            科目 B · 3题/轮 · 10分钟通关
          </span>
          <h2 class="text-lg font-black text-slate-900 mt-1.5">初中数学每日三题</h2>
        </div>
        <span class="text-3xl">📐</span>
      </div>
      <p class="text-xs text-slate-500 mt-1">
        人教/北师大高频典型考点，优先抽取未做与错题，LaTeX 步步解析（+2/-1分）。
      </p>
      <div class="mt-2 text-[11px] font-semibold" :class="store.quota.math_locked ? 'text-rose-500' : 'text-teal-600'">
        今日数学：已用 {{ store.quota.math_used_minutes }} 分钟 / 剩余 {{ store.quota.math_remaining_minutes }} 分钟
      </div>

      <div class="mt-4 grid grid-cols-3 gap-2">
        <button
          v-for="grade in mathGrades"
          :key="grade.value"
          type="button"
          class="py-2.5 px-2 rounded-xl text-xs font-bold border transition text-center"
          :class="selectedMathGrade === grade.value
            ? 'bg-teal-600 text-white border-teal-600 shadow-sm'
            : 'bg-slate-50 text-slate-700 border-slate-200 hover:border-teal-300'"
          @click="selectedMathGrade = grade.value"
        >
          {{ grade.label }}
        </button>
      </div>

      <van-button
        block
        round
        type="primary"
        :color="store.quota.math_locked ? '#94a3b8' : '#0d9488'"
        class="mt-4 font-bold"
        :disabled="store.quota.math_locked"
        :loading="startingSubject === 'math'"
        @click="beginStudy('math', selectedMathGrade)"
      >
        {{ store.quota.math_locked ? '今日数学时长已用完（明日再来）' : '开始今日数学精练（3 题）' }}
      </van-button>
    </section>

    <div class="mt-4 p-3.5 rounded-2xl bg-slate-100/80 text-[11px] text-slate-500 leading-relaxed">
      <strong class="text-slate-700">低焦虑防超时引擎：</strong>
      前 20 分钟完全隐藏倒计时数字，让您从容沉浸学习；最后 10 分钟柔和浮现复核冲刺计时，30 分钟内实现“全对过关”即可赢取每日 +5 通关奖励。
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showToast } from 'vant'
import { useStudyStore } from '../stores/studyStore'

const store = useStudyStore()

const englishStages = [
  { value: 'primary', label: '小学必备词', desc: '600 核心基础' },
  { value: 'grade_7', label: '初一核心词', desc: '七年级同步' },
  { value: 'grade_8', label: '初二核心词', desc: '八年级进阶' },
  { value: 'grade_9', label: '初三中考词', desc: '中考冲刺高频' }
]

const mathGrades = [
  { value: 'grade_7', label: '初一数学' },
  { value: 'grade_8', label: '初二数学' },
  { value: 'grade_9', label: '初三数学' }
]

const selectedEnglishStage = ref('grade_7')
const selectedMathGrade = ref('grade_7')
const startingSubject = ref('')

async function beginStudy(subject, stageOrGrade) {
  startingSubject.value = subject
  try {
    await store.startSession(subject, stageOrGrade)
  } catch (err) {
    if (err.status === 403) {
      await store.refreshProfile()
    }
    showToast(err.message || '开启批次失败')
  } finally {
    startingSubject.value = ''
  }
}
</script>
