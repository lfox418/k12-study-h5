<template>
  <div v-if="session" class="min-h-screen pb-16 bg-slate-50">
    <!-- 共享防焦虑倒计时条（重学期间不重置 expiresAt） -->
    <StealthTimerBar
      :title="`英语背词 · ${stageLabel}`"
      :expires-at="session.expires_at"
      :clock-offset="session.clockOffset || 0"
      :hide-threshold="session.stealth_hide_threshold || 600"
      :urgent-threshold="session.urgent_pulse_threshold || 120"
      :paused="phase === 'passed' || phase === 'expired'"
      @expired="handleExpired"
      @exit="confirmExit"
    />

    <!-- 阶段 1：卡片沉浸记忆（支持浏览器原生 speechSynthesis 发音） -->
    <div v-if="phase === 'memorize'" class="px-4 pt-5">
      <div class="flex items-center justify-between text-xs text-slate-500 mb-3">
        <span>步骤 1/2 · 沉浸记忆卡片</span>
        <span class="font-bold text-indigo-600">{{ currentIndex + 1 }} / {{ words.length }}</span>
      </div>

      <div class="bg-white rounded-3xl p-6 shadow-sm border border-slate-100">
        <div class="flex items-start justify-between">
          <div>
            <h2 class="text-3xl font-black text-slate-900 tracking-tight">{{ currentWord.word }}</h2>
            <p class="text-sm font-mono text-indigo-600 mt-1">{{ currentWord.phonetic || '/—/' }}</p>
          </div>
          <button
            type="button"
            class="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-2xl active:scale-95 transition"
            @click="speakWord(currentWord.word)"
            >
                {{ ttsState.loadingText === currentWord.word ? '⏳' : '🔊' }}
          </button>
        </div>

        <div class="mt-5 p-4 rounded-2xl bg-slate-50 border border-slate-100">
          <div class="text-xs text-slate-400">中文释义</div>
          <div class="text-lg font-bold text-slate-800 mt-1">{{ currentWord.meaning }}</div>
        </div>

        <div v-if="currentWord.examples?.length" class="mt-4 space-y-2.5">
          <div class="text-xs font-semibold text-slate-400">双语例句</div>
          <div
            v-for="(ex, idx) in currentWord.examples"
            :key="idx"
            class="p-3.5 rounded-2xl bg-indigo-50/50 border border-indigo-100"
          >
            <div class="flex items-start justify-between gap-2">
              <p class="text-sm text-slate-800 leading-relaxed">{{ ex.en }}</p>
              <button type="button" class="text-indigo-600 shrink-0" @click="speakWord(ex.en)">
                {{ ttsState.loadingText === ex.en ? '⏳' : '🔊' }}
              </button>
            </div>
            <p v-if="ex.zh" class="text-xs text-slate-500 mt-1">{{ ex.zh }}</p>
          </div>
        </div>
      </div>

      <div class="mt-5 flex gap-3">
        <van-button
          round
          plain
          type="primary"
          color="#4f46e5"
          class="flex-1"
          :disabled="currentIndex === 0"
          @click="currentIndex--"
        >
          上一个
        </van-button>
        <van-button
          v-if="currentIndex < words.length - 1"
          round
          type="primary"
          color="#4f46e5"
          class="flex-1 font-bold"
          @click="nextWord"
        >
          下一个
        </van-button>
        <van-button
          v-else
          round
          type="primary"
          color="#10b981"
          class="flex-1 font-bold"
          @click="enterReview"
        >
          进入拼写复核 →
        </van-button>
      </div>
    </div>

    <!-- 阶段 2：复核测试（仅展示中文，要求输入英文，忽略大小写与首尾空格） -->
    <div v-else-if="phase === 'review'" class="px-4 pt-5">
      <div class="flex items-center justify-between mb-3">
        <span class="text-xs font-semibold text-slate-500">步骤 2/2 · 看中文拼写英文（需全对过关）</span>
        <span class="text-xs text-indigo-600 font-bold">共 {{ words.length }} 词</span>
      </div>

      <div class="space-y-3">
        <div
          v-for="(w, idx) in words"
          :key="w.id"
          class="bg-white rounded-2xl p-4 shadow-sm border border-slate-100"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-400">#{{ idx + 1 }}</span>
            <span class="text-sm font-bold text-slate-800">{{ w.meaning }}</span>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model="inputs[w.id]"
              type="text"
              autocapitalize="off"
              autocomplete="off"
              spellcheck="false"
              placeholder="请输入对应英文单词..."
              class="flex-1 min-w-0 px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-200 focus:border-indigo-500 focus:bg-white focus:outline-none text-base font-semibold text-slate-900"
            />
          </div>
          <div class="mt-2 flex justify-end">
            <button
              type="button"
              class="px-3 py-1.5 rounded-xl text-xs font-bold border transition flex items-center gap-1.5 active:scale-95"
              :class="usedHints[w.id]
                ? 'bg-amber-50 text-amber-700 border-amber-300'
                : 'bg-indigo-50 text-indigo-600 border-indigo-200 hover:bg-indigo-100'"
              @click="playAudioHint(w)"
            >
              <span>🔊</span>
              <span>{{ usedHints[w.id] ? '已使用语音提示（答对得 0.5 分）' : '听发音提示（积分减半）' }}</span>
            </button>
          </div>
        </div>
      </div>

      <van-button
        block
        round
        type="primary"
        color="#4f46e5"
        size="large"
        class="mt-6 font-bold"
        :loading="submitting"
        @click="submitReview"
      >
        提交校验（对 +1 / 错 -1）
      </van-button>
    </div>

    <!-- 阶段 3：存在错词 -> 展示错词详情与正确拼写 + “重新学习本组（全部重来）” -->
    <div v-else-if="phase === 'wrong'" class="px-4 pt-5">
      <div class="bg-rose-50 border border-rose-200 rounded-3xl p-4 text-center">
        <div class="text-lg font-black text-rose-700">
          本轮拼对 {{ lastResult.correct_count }} 词，拼错 {{ lastResult.wrong_count }} 词
        </div>
        <p class="text-xs text-rose-600 mt-1">
          必须本组 10 词全对才算过关！重学期间总 30 分钟倒计时继续运行不重置。
        </p>
      </div>

      <div class="mt-4 space-y-2.5">
        <div
          v-for="item in lastResult.results"
          :key="item.word_id"
          class="rounded-2xl p-3.5 border"
          :class="item.is_correct ? 'bg-emerald-50/50 border-emerald-200' : 'bg-white border-rose-300 shadow-sm'"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-base font-black" :class="item.is_correct ? 'text-emerald-700' : 'text-rose-700'">
                {{ item.word }}
              </span>
              <span class="text-xs font-mono text-slate-400">{{ item.phonetic }}</span>
            </div>
            <button type="button" class="text-indigo-600 text-sm" @click="speakWord(item.word)">🔊</button>
          </div>
          <div class="text-xs text-slate-600 mt-1">{{ item.meaning }}</div>
          <div v-if="!item.is_correct" class="text-xs text-rose-600 mt-1.5 font-semibold">
            你的拼写：{{ item.user_input || '（未填）' }} → 正确拼写：{{ item.word }}
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

    <!-- 阶段 4：全对通关 -->
    <div v-else-if="phase === 'passed'" class="px-4 pt-10 text-center">
      <div class="bg-white rounded-3xl p-7 shadow-sm border border-emerald-100">
        <div class="text-5xl mb-3">🏆</div>
        <h2 class="text-2xl font-black text-slate-900">英语 10 词全对通关！</h2>
        <p class="text-xs text-slate-500 mt-2">
          用时 {{ formatDurationMinutes(lastResult.duration_minutes, lastResult.duration_sec) }} · 当前总积分 {{ store.totalPoints }} 分
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
          color="#4f46e5"
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import { useStudyStore } from '../stores/studyStore'
import StealthTimerBar from '../components/StealthTimerBar.vue'
import { speakWord, ttsState } from '../utils/sound'


const store = useStudyStore()
const session = computed(() => store.activeSession)
const words = computed(() => session.value?.items || [])

const stageMap = {
  primary: '小学必备词',
  grade_7: '初一核心词',
  grade_8: '初二核心词',
  grade_9: '初三中考词'
}
const stageLabel = computed(() => stageMap[session.value?.stage_or_grade] || '')

const phase = ref('memorize') // 'memorize' | 'review' | 'wrong' | 'passed' | 'expired'
const currentIndex = ref(0)
const inputs = reactive({})
const usedHints = reactive({})
const submitting = ref(false)
const lastResult = ref(null)

let heartbeatTimer = null
let lastSyncTs = Math.floor(Date.now() / 1000)

const currentWord = computed(() => words.value[currentIndex.value] || {})

function playAudioHint(w) {
  usedHints[w.id] = true
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel()
      const utter = new SpeechSynthesisUtterance(w.word)
      utter.lang = 'en-US'
      utter.rate = 0.92
      window.speechSynthesis.speak(utter)
      return
    } catch {
      // 降级到后端 TTS
    }
  }
  speakWord(w.word)
}

function nextWord() {
  if (currentIndex.value < words.value.length - 1) {
    currentIndex.value++
    speakWord(words.value[currentIndex.value]?.word || '')
  }
}

function enterReview() {
  words.value.forEach((w) => {
    inputs[w.id] = ''
    usedHints[w.id] = false
  })
  phase.value = 'review'
}

async function handleQuotaCircuitBreaker(message) {
  if (phase.value === 'expired') return
  phase.value = 'expired'
  stopHeartbeat()
  await showDialog({
    title: '今日学习时长已达上限',
    message: message || '今日英语或双科总学习时长已达上限，当前学习已终止，请明日再来。',
    confirmButtonText: '返回大厅'
  })
  await store.refreshProfile()
  store.clearActiveSession()
}

async function flushHeartbeat(useBeacon = false) {
  if (!session.value || phase.value === 'passed' || phase.value === 'expired') return
  const nowSec = Math.floor(Date.now() / 1000)
  const delta = Math.max(0, nowSec - lastSyncTs)
  if (delta <= 0) return
  lastSyncTs = nowSec
  if (useBeacon) {
    store.sendQuotaBeacon('english', delta, session.value.session_id)
    return
  }
  try {
    await store.sendQuotaHeartbeat('english', delta, session.value.session_id)
  } catch (err) {
    if (err.status === 403) {
      await handleQuotaCircuitBreaker(err.message)
    }
  }
}

function handleVisibilityOrUnload() {
  if (document.visibilityState === 'hidden') {
    flushHeartbeat(true)
  } else {
    lastSyncTs = Math.floor(Date.now() / 1000)
  }
}

function handlePageHide() {
  flushHeartbeat(true)
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

onMounted(() => {
  lastSyncTs = Math.floor(Date.now() / 1000)
  heartbeatTimer = setInterval(() => flushHeartbeat(false), 10000)
  document.addEventListener('visibilitychange', handleVisibilityOrUnload)
  window.addEventListener('pagehide', handlePageHide)
})

onBeforeUnmount(() => {
  stopHeartbeat()
  document.removeEventListener('visibilitychange', handleVisibilityOrUnload)
  window.removeEventListener('pagehide', handlePageHide)
})

async function submitReview() {
  submitting.value = true
  try {
    await flushHeartbeat(false)
    if (phase.value === 'expired') return

    const answers = words.value.map((w) => ({
      word_id: w.id,
      user_answer: inputs[w.id] || '',
      used_audio_hint: Boolean(usedHints[w.id])
    }))
    const res = await store.submitSession(session.value.session_id, answers)
    lastResult.value = res

    if (res.is_expired || res.status === 'expired') {
      await handleExpired()
      return
    }

    const netDelta = Number(res.raw_score_delta ?? res.score_delta)
    if (res.all_correct) {
      phase.value = 'passed'
      stopHeartbeat()
      store.triggerEffect({
        type: 'bonus',
        headline: `+${Number(res.score_delta)} 分！`,
        subline: res.daily_bonus > 0 ? `每日通关奖励 +${Number(res.daily_bonus)} 分！` : '本轮 10 词全对通关！'
      })
    } else {
      phase.value = 'wrong'
      if (netDelta > 0) {
        store.triggerEffect({
          type: 'bonus',
          headline: `+${netDelta} 分`,
          subline: `还有 ${res.wrong_count} 个错词，重学即可通关`
        })
      } else {
        store.triggerEffect({
          type: 'penalty',
          headline: `${netDelta} 分，继续加油！`,
          subline: `本轮拼错 ${res.wrong_count} 词，请查看正确拼写后重学`
        })
      }
    }
  } catch (err) {
    if (err.status === 403) {
      await handleQuotaCircuitBreaker(err.message)
    } else {
      showToast(err.message || '提交失败')
    }
  } finally {
    submitting.value = false
  }
}

function restartFullGroup() {
  // 全部重来，严格保持原 session 与原 expires_at 不重置，同时重置语音提示标记
  currentIndex.value = 0
  words.value.forEach((w) => {
    inputs[w.id] = ''
    usedHints[w.id] = false
  })
  phase.value = 'memorize'
}

async function handleExpired() {
  if (phase.value === 'expired') return
  phase.value = 'expired'
  stopHeartbeat()
  try {
    await store.checkExpiry(session.value.session_id)
  } catch {
    // ignore
  }
  await showDialog({
    title: '超时作废',
    message: '超时未完成，本次成绩作废。不计入熟练度晋升、不发放通关积分，请重新开启新批次。',
    confirmButtonText: '返回大厅'
  })
  await store.refreshProfile()
  store.clearActiveSession()
}

async function confirmExit() {
  if (phase.value === 'passed' || phase.value === 'expired') {
    await store.refreshProfile()
    store.clearActiveSession()
    return
  }
  try {
    await showConfirmDialog({
      title: '确认返回大厅？',
      message: '当前批次尚未通关，已消耗的学习时长将永久计入今日配额。'
    })
    await flushHeartbeat(false)
    stopHeartbeat()
    await store.refreshProfile()
    store.clearActiveSession()
  } catch {
    // 取消
  }
}

function formatDurationMinutes(mins, sec) {
  if (mins !== null && mins !== undefined) return `${mins} 分钟`
  if (!sec) return '0 分钟'
  return `${Math.max(1, Math.floor(sec / 60))} 分钟`
}
</script>
