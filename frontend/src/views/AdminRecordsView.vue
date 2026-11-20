<template>
  <div class="min-h-screen pb-10 px-4 pt-4 bg-slate-50">
    <div class="bg-slate-900 text-white rounded-2xl p-4 flex items-center justify-between">
      <div>
        <div class="text-xs text-slate-400">全局学习记录看板</div>
        <div class="text-base font-black mt-0.5">共 {{ records.length }} 条批次 · {{ users.length }} 位用户</div>
      </div>
      <button
        type="button"
        class="px-3 py-1.5 rounded-xl bg-white/15 text-xs font-bold"
        @click="store.logout()"
      >
        退出
      </button>
    </div>

    <!-- 筛选栏：日期 / 用户 / 科目 -->
    <div class="mt-3 bg-white rounded-2xl p-3 border border-slate-100 grid grid-cols-3 gap-2 text-xs">
      <input
        v-model="filters.date"
        type="date"
        class="px-2 py-1.5 rounded-lg border border-slate-200 bg-slate-50"
        @change="loadRecords"
      />
      <select
        v-model="filters.user_code"
        class="px-2 py-1.5 rounded-lg border border-slate-200 bg-slate-50"
        @change="loadRecords"
      >
        <option value="">全部用户</option>
        <option v-for="u in users" :key="u.referral_code" :value="u.referral_code">
          {{ u.referral_code }}{{ u.phone ? ` (${u.phone.slice(-4)})` : '' }}
        </option>
      </select>
      <select
        v-model="filters.subject"
        class="px-2 py-1.5 rounded-lg border border-slate-200 bg-slate-50"
        @change="loadRecords"
      >
        <option value="">全部科目</option>
        <option value="english">英语</option>
        <option value="math">数学</option>
      </select>
    </div>

    <!-- 每日记录列表 -->
    <div class="mt-3 space-y-3">
      <div
        v-for="r in records"
        :key="r.session_id"
        class="bg-white rounded-2xl p-4 shadow-sm border border-slate-100"
      >
        <div class="flex items-center justify-between">
          <div class="text-xs font-black text-slate-800">
            {{ r.referral_code }}
            <span v-if="r.phone" class="font-normal text-slate-400 ml-1">{{ r.phone }}</span>
          </div>
          <span class="text-[11px] font-bold px-2 py-0.5 rounded-full" :class="statusBadge(r.status)">
            {{ statusText(r.status) }}
          </span>
        </div>

        <div class="mt-1.5 text-[11px] text-slate-500 flex flex-wrap gap-x-3 gap-y-1">
          <span>📅 {{ r.created_date }}</span>
          <span>📚 {{ r.subject === 'english' ? '英语' : '数学' }} · {{ stageLabel(r.stage_or_grade) }}</span>
          <span>⏱ 耗时 {{ formatDuration(r.duration_sec) }}</span>
          <span>🔁 提交 {{ r.attempt_count }} 次（首错 {{ r.first_wrong_count }}）</span>
          <span>🪙 净积分 {{ r.total_score_delta >= 0 ? '+' : '' }}{{ r.total_score_delta }}</span>
        </div>

        <!-- 抽题明细与复核结果 -->
        <div v-if="r.subject === 'english'" class="mt-2.5 flex flex-wrap gap-1.5">
          <span
            v-for="w in r.items"
            :key="w.id"
            class="px-2 py-0.5 rounded-md text-xs font-semibold border"
            :class="w.first_wrong
              ? 'bg-rose-50 text-rose-600 border-rose-300'
              : 'bg-emerald-50 text-emerald-700 border-emerald-200'"
          >
            {{ w.word }}
          </span>
        </div>

        <div v-else class="mt-2.5 space-y-1.5">
          <div
            v-for="(q, idx) in r.items"
            :key="q.id"
            class="p-2.5 rounded-xl border text-xs"
            :class="q.first_wrong ? 'bg-rose-50/70 border-rose-200' : 'bg-slate-50 border-slate-200'"
          >
            <div class="flex items-center justify-between font-bold mb-1">
              <span class="text-teal-700">第{{ idx + 1 }}题 · {{ q.topic_tag }}</span>
              <span :class="q.first_wrong ? 'text-rose-600' : 'text-emerald-600'">
                {{ q.first_wrong ? '首次答错' : '一次答对' }}
              </span>
            </div>
            <MathText :content="q.stem" />
          </div>
        </div>
      </div>

      <div v-if="!records.length" class="text-center text-xs text-slate-400 py-10">
        当前筛选条件下暂无学习记录
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api/client'
import { useStudyStore } from '../stores/studyStore'
import MathText from '../components/MathText.vue'

const store = useStudyStore()
const users = ref([])
const records = ref([])
const filters = reactive({ date: '', user_code: '', subject: '' })

async function loadRecords() {
  const params = new URLSearchParams()
  if (filters.date) params.set('date', filters.date)
  if (filters.user_code) params.set('user_code', filters.user_code)
  if (filters.subject) params.set('subject', filters.subject)
  const qs = params.toString()
  const data = await api.get(`/admin/daily-records${qs ? `?${qs}` : ''}`)
  users.value = data.users || []
  records.value = data.records || []
}

function stageLabel(code) {
  return { primary: '小学', grade_7: '初一', grade_8: '初二', grade_9: '初三' }[code] || code
}
function statusText(st) {
  return { passed: '已通关', expired: '超时作废', in_progress: '进行中' }[st] || st
}
function statusBadge(st) {
  if (st === 'passed') return 'bg-emerald-100 text-emerald-700'
  if (st === 'expired') return 'bg-rose-100 text-rose-700'
  return 'bg-amber-100 text-amber-700'
}
function formatDuration(sec) {
  if (!sec) return '未完成'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

onMounted(loadRecords)
</script>