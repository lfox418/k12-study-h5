<template>
  <div class="pb-24 px-4 pt-4">
    <!-- 顶部推荐码与“我的积分”胶囊 -->
    <div class="flex items-center justify-between bg-white rounded-2xl p-3.5 shadow-sm border border-slate-100">
      <div class="flex items-center gap-2.5">
        <div class="w-10 h-10 rounded-xl bg-indigo-600 text-white font-black flex items-center justify-center text-sm">
          K12
        </div>
        <div>
          <div class="text-xs text-slate-400">当前档案推荐码</div>
          <div class="text-sm font-black tracking-wider text-slate-800">{{ store.referralCode }}</div>
        </div>
      </div>

      <div
        id="my-points-capsule"
        class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-gradient-to-r from-amber-400 to-orange-400 text-amber-950 font-black text-sm shadow-sm"
      >
        <span>🪙</span>
        <span>{{ store.totalPoints }} 分</span>
      </div>
    </div>

    <!-- 今日通关徽章状态条 -->
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
        color="#4f46e5"
        class="mt-4 font-bold"
        :loading="startingSubject === 'english'"
        @click="beginStudy('english', selectedEnglishStage)"
      >
        开始今日英语学习（10 词）
      </van-button>
    </section>

    <!-- 科目 B：初中数学每日三题 -->
    <section class="mt-4 bg-white rounded-3xl p-5 shadow-sm border border-teal-100/80">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-teal-50 text-teal-700">
            科目 B · 3题/轮 · 30分钟通关
          </span>
          <h2 class="text-lg font-black text-slate-900 mt-1.5">初中数学每日三题</h2>
        </div>
        <span class="text-3xl">📐</span>
      </div>
      <p class="text-xs text-slate-500 mt-1">
        人教/北师大高频典型考点，优先抽取未做与错题，LaTeX 步步解析（+2/-1分）。
      </p>

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
        color="#0d9488"
        class="mt-4 font-bold"
        :loading="startingSubject === 'math'"
        @click="beginStudy('math', selectedMathGrade)"
      >
        开始今日数学精练（3 题）
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
    showToast(err.message || '开启批次失败')
  } finally {
    startingSubject.value = ''
  }
}
</script>
