<template>
  <div v-if="session" class="min-h-screen pb-16 bg-slate-50">
    <!-- 共享防焦虑倒计时条（重学期间不重置 expiresAt） -->
    <StealthTimerBar
      :title="`数学每日三题 · ${gradeLabel}`"
      :expires-at="session.expires_at"
      :clock-offset="session.clockOffset || 0"
      :hide-threshold="session.stealth_hide_threshold || 600"
      :urgent-threshold="session.urgent_pulse_threshold || 120"
      :paused="phase === 'passed' || phase === 'expired'"
      @expired="handleExpired"
      @exit="confirmExit"
    />

    <!-- 作答阶段 -->
    <div v-if="phase === 'solving'" class="px-4 pt-5 space-y-4">
      <div
        v-for="(q, idx) in questions"
        :key="q.id"
        class="bg-white rounded-3xl p-5 shadow-sm border border-slate-100"
      >
        <div class="flex items-center justify-between mb-2.5">
          <span class="text-xs font-black text-teal-700 bg-teal-50 px-2.5 py-0.5 rounded-full">
            第 {{ idx + 1 }} 题 · {{ q.topic_tag }}
          </span>
          <span class="text-[11px] text-slate-400">
            {{ q.question_type === 'choice' ? '选择题' : '填空题' }}
          </span>
        </div>

        <div class="text-[15px] text-slate-800 leading-relaxed">
          <MathText :content="q.stem" />
        </div>

        <!-- 选择题选项 -->
        <div v-if="q.question_type === 'choice'" class="mt-4 space-y-2">
          <button
            v-for="opt in q.options"
            :key="opt"
            type="button"
            class="w-full text-left px-4 py-3 rounded-2xl border text-sm transition flex items-center gap-2"
            :class="answers[q.id] === extractOptionKey(opt)
              ? 'bg-teal-600 text-white border-teal-600 font-bold shadow-sm'
              : 'bg-slate-50 text-slate-700 border-slate-200 hover:border-teal-300'"
            @click="answers[q.id] = extractOptionKey(opt)"
          >
            <MathText :content="formatOptionLatex(opt)" />
          </button>
        </div>

        <!-- 填空题输入 -->
        <div v-else class="mt-4">
          <input
            v-model="answers[q.id]"
            type="text"
            placeholder="请输入最终答案（如 -1 或 55）"
            class="w-full px-4 py-3 rounded-2xl bg-slate-50 border border-slate-200 focus:border-teal-500 focus:bg-white focus:outline-none text-base font-bold text-slate-900"
          />
        </div>
      </div>

      <van-button
        block
        round
        type="primary"
        color="#0d9488"
        size="large"
        class="font-bold"
        :loading="submitting"
        @click="submitAnswers"
      >
        提交校验（对 +2 / 错 -1）
      </van-button>
    </div>

    <!-- 错题解析与重学闭环 -->
    <div v-else-if="phase === 'wrong'" class="px-4 pt-5">
      <div class="bg-rose-50 border border-rose-200 rounded-3xl p-4 text-center">
        <div class="text-lg font-black text-rose-700">
          本轮答对 {{ lastResult.correct_count }} 题，答错 {{ lastResult.wrong_count }} 题
        </div>
        <p class="text-xs text-rose-600 mt-1">
          请研读下方分步解析后点击“重新学习本组”，总 30 分钟倒计时继续运行不重置。
        </p>
      </div>

      <div class="mt-4 space-y-4">
        <div
          v-for="(item, idx) in lastResult.results"
          :key="item.question_id"
          class="bg-white rounded-3xl p-5 border"
          :class="item.is_correct ? 'border-emerald-200' : 'border-rose-300 shadow-sm'"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-500">第 {{ idx + 1 }} 题 · {{ item.topic_tag }}</span>
            <span
              class="text-xs font-bold px-2 py-0.5 rounded-full"
              :class="item.is_correct ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'"
            >
              {{ item.is_correct ? '✓ 正确' : '✗ 错误' }}
            </span>
          </div>

          <div class="text-sm text-slate-800">
            <MathText :content="item.stem" />
          </div>

          <div v-if="!item.is_correct" class="mt-3 text-xs text-rose-600 font-semibold">
            你的作答：{{ item.user_input || '（未填）' }} ｜ 标准答案：{{ item.correct_answer }}
          </div>

          <div class="mt-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-100 text-xs text-slate-700">
            <div class="font-bold text-teal-700 mb-1">分步详细解析：</div>
            <MathText :content="item.analysis" />
          </div>
        </div>
      </div>

      <van-button
        block
        round
        type="primary"
        color="#f59e0b"
        size="large"
        class="mt-6 font-bold"
        @click="restartFullGroup"
      >
        重新学习本组（全部重来）
      </van-button>
    </div>

    <!-- 全对通关 -->
    <div v-else-if="phase === 'passed'" class="px-4 pt-10 text-center">
      <div class="bg-white rounded-3xl p-7 shadow-sm border border-emerald-100">
        <div class="text-5xl mb-3">🎯</div>
        <h2 class="text-2xl font-black text-slate-900">数学每日三题全对通关！</h2>
        <p class="text-xs text-slate-500 mt-2">
          用时 {{ formatDuration(lastResult.duration_sec) }} · 当前总积分 {{ store.totalPoints }} 分
        </p>
        <div
          v-if="lastResult.daily_bonus > 0"
          class="mt-3 inline-block px-3.5 py-1 rounded-full bg-amber-100 text-amber-800 text-xs font-bold"
        >
          🎉 已获得每日首次通关奖励 +{{ lastResult.daily_bonus }} 分
        </div>
        <van-button
          block
          round
          type="primary"
          color="#0d9488"
          class="mt-6 font-bold"
          @click="store.clearActiveSession()"
        >
          返回学习大厅
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import { useStudyStore } from '../stores/studyStore'
import StealthTimerBar from '../components/StealthTimerBar.vue'
import MathText from '../components/MathText.vue'

const store = useStudyStore()
const session = computed(() => store.activeSession)
const questions = computed(() => session.value?.items || [])

const gradeMap = { grade_7: '初一', grade_8: '初二', grade_9: '初三' }
const gradeLabel = computed(() => gradeMap[session.value?.stage_or_grade] || '')

const phase = ref('solving') // 'solving' | 'wrong' | 'passed' | 'expired'
const answers = reactive({})
const submitting = ref(false)
const lastResult = ref(null)

function extractOptionKey(opt) {
  return String(opt).trim().charAt(0).toUpperCase()
}

function formatOptionLatex(opt) {
  // 若选项含 LaTeX 命令但未包 $，自动包裹便于 KaTeX 渲染
  const str = String(opt)
  if (str.includes('$')) return str
  if (/[\\^_]/.test(str)) {
    const prefix = str.slice(0, 3)
    const body = str.slice(3).trim()
    return `${prefix}$${body}$`
  }
  return str
}

async function submitAnswers() {
  submitting.value = true
  try {
    const payload = questions.value.map((q) => ({
      question_id: q.id,
      user_input: answers[q.id] || ''
    }))
    const res = await store.submitSession(session.value.session_id, payload)
    lastResult.value = res

    if (res.is_expired || res.status === 'expired') {
      await handleExpired()
      return
    }

    const netDelta = (res.raw_score_delta ?? res.score_delta)
    if (res.all_correct) {
      phase.value = 'passed'
      store.triggerEffect({
        type: 'bonus',
        headline: `+${res.score_delta} 分！`,
        subline: res.daily_bonus > 0 ? `每日通关奖励 +${res.daily_bonus} 分！` : '三题全对通关！'
      })
    } else {
      phase.value = 'wrong'
      if (netDelta > 0) {
        store.triggerEffect({
          type: 'bonus',
          headline: `+${netDelta} 分`,
          subline: `答错 ${res.wrong_count} 题，看懂解析后全部重做`
        })
      } else {
        store.triggerEffect({
          type: 'penalty',
          headline: `${netDelta} 分，继续加油！`,
          subline: `答错 ${res.wrong_count} 题，研读解析后重新挑战`
        })
      }
    }
  } catch (err) {
    showToast(err.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

function restartFullGroup() {
  // 全部重来，严格保持原 session 与 expires_at 不重置
  questions.value.forEach((q) => {
    answers[q.id] = ''
  })
  phase.value = 'solving'
}

async function handleExpired() {
  if (phase.value === 'expired') return
  phase.value = 'expired'
  try {
    await store.checkExpiry(session.value.session_id)
  } catch {
    // ignore
  }
  await showDialog({
    title: '超时作废',
    message: '超时未完成，本次成绩作废。不发放通关积分，请重新开启新批次。',
    confirmButtonText: '返回大厅'
  })
  store.clearActiveSession()
}

async function confirmExit() {
  if (phase.value === 'passed' || phase.value === 'expired') {
    store.clearActiveSession()
    return
  }
  try {
    await showConfirmDialog({
      title: '确认返回大厅？',
      message: '当前数学批次尚未通关，退出后需重新开启。'
    })
    store.clearActiveSession()
  } catch {
    // cancel
  }
}

function formatDuration(sec) {
  if (!sec) return '0秒'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}
</script>
