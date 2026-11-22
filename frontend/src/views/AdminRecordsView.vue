<template>
  <div class="min-h-screen pb-10 px-4 pt-4 bg-slate-50">
    <!-- 顶部栏 -->
    <div class="bg-slate-900 text-white rounded-2xl p-4 flex items-center justify-between gap-2">
      <div class="min-w-0">
        <div class="text-xs text-slate-400">
          {{ viewMode === 'learners' ? '管理员看板 · 学习人总览' : '全局学习记录明细' }}
        </div>
        <div class="text-base font-black mt-0.5 truncate">
          {{ viewMode === 'learners' ? `共 ${learners.length} 位学习人` : `共 ${records.length} 条批次 · ${users.length} 位用户` }}
        </div>
      </div>
      <div class="flex items-center gap-1.5 shrink-0">
        <button
          v-if="viewMode === 'learners'"
          type="button"
          class="px-2.5 py-1.5 rounded-xl bg-indigo-500/30 text-indigo-100 text-xs font-bold"
          @click="openAllRecords"
        >
          全部记录
        </button>
        <button
          v-else
          type="button"
          class="px-2.5 py-1.5 rounded-xl bg-indigo-500/30 text-indigo-100 text-xs font-bold"
          @click="viewMode = 'learners'"
        >
          ← 学习人
        </button>
        <button
          type="button"
          class="px-2.5 py-1.5 rounded-xl bg-amber-500/20 text-amber-200 text-xs font-bold"
          @click="cleanupInvalid"
        >
          清理无效
        </button>
        <button
          type="button"
          class="px-2.5 py-1.5 rounded-xl bg-white/15 text-xs font-bold"
          @click="store.logout()"
        >
          退出
        </button>
      </div>
    </div>

    <!-- 模式 A：学习人卡片列表（默认首页） -->
    <div v-if="viewMode === 'learners'" class="mt-3 space-y-3">
      <div
        v-for="u in learners"
        :key="u.referral_code"
        class="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden"
      >
        <!-- 卡片头部：点击展开/收起分年级统计 -->
        <button
          type="button"
          class="w-full p-4 text-left transition active:bg-slate-50"
          @click="toggleLearner(u.referral_code)"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-sm font-black text-slate-900 truncate">
                {{ u.nickname || u.referral_code }}
              </span>
              <span
                v-if="u.nickname"
                class="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 shrink-0"
              >
                {{ u.referral_code }}
              </span>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <span class="text-xs font-black text-amber-600">🪙 {{ u.total_points }} 分</span>
              <span class="text-xs text-slate-400">
                {{ expandedUser === u.referral_code ? '▲' : '▼' }}
              </span>
            </div>
          </div>

          <!-- 三级词库总览角标 -->
          <div class="mt-3 grid grid-cols-3 gap-2 text-center">
            <div class="rounded-xl bg-slate-50 border border-slate-100 py-2 px-1">
              <div class="text-[10px] text-slate-400">一级（生词）</div>
              <div class="text-sm font-black text-slate-700 mt-0.5">{{ u.tiers_total.level_1 }}</div>
            </div>
            <div class="rounded-xl bg-amber-50/70 border border-amber-100 py-2 px-1">
              <div class="text-[10px] text-amber-700">二级（巩固）</div>
              <div class="text-sm font-black text-amber-700 mt-0.5">{{ u.tiers_total.level_2 }}</div>
            </div>
            <div class="rounded-xl bg-emerald-50/70 border border-emerald-100 py-2 px-1">
              <div class="text-[10px] text-emerald-700">三级（掌握）</div>
              <div class="text-sm font-black text-emerald-700 mt-0.5">{{ u.tiers_total.level_3 }}</div>
            </div>
          </div>
        </button>

        <!-- 展开区：分年级（学段）词库量 + 查看学习记录按钮 -->
        <div
          v-if="expandedUser === u.referral_code"
          class="px-4 pb-4 pt-3 border-t border-slate-100 bg-slate-50/60"
        >
          <div class="text-[11px] font-bold text-slate-500 mb-2">分学段/年级掌握详情</div>
          <div class="space-y-1.5">
            <div
              v-for="st in u.stages"
              :key="st.grade_stage"
              class="bg-white rounded-xl px-3 py-2 border border-slate-100 flex items-center justify-between text-xs"
            >
              <span class="font-bold text-slate-700">{{ st.label }}</span>
              <div class="flex items-center gap-3 tabular-nums text-[11px]">
                <span class="text-slate-500">一级 <b>{{ st.level_1 }}</b></span>
                <span class="text-amber-700">二级 <b>{{ st.level_2 }}</b></span>
                <span class="text-emerald-700">三级 <b>{{ st.level_3 }}</b></span>
              </div>
            </div>
          </div>

          <button
            type="button"
            class="mt-3 w-full py-2.5 rounded-xl bg-indigo-600 text-white text-xs font-bold shadow-sm active:scale-[0.99] transition"
            @click.stop="openLearnerRecords(u.referral_code)"
          >
            📋 查看学习记录 →
          </button>
        </div>
      </div>

      <div v-if="!learners.length" class="text-center text-xs text-slate-400 py-10">
        暂无学习人数据
      </div>
    </div>

    <!-- 模式 B：每日学习记录列表 -->
    <template v-else>
      <!-- 视图切换与筛选栏 -->
      <div class="mt-3 flex items-center justify-between gap-2">
        <div class="flex bg-white p-1 rounded-xl border border-slate-200 text-xs font-bold">
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg transition"
            :class="recordsSubMode === 'list' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600'"
            @click="recordsSubMode = 'list'"
          >
            📋 列表视图
          </button>
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg transition"
            :class="recordsSubMode === 'calendar' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600'"
            @click="openCalendarView"
          >
            📅 日历视图
          </button>
        </div>

        <button
          v-if="filters.date && recordsSubMode === 'list'"
          type="button"
          class="px-2.5 py-1.5 rounded-xl bg-indigo-50 text-indigo-700 text-xs font-bold border border-indigo-200"
          @click="filters.date = ''; loadRecords()"
        >
          {{ filters.date }} ×
        </button>
      </div>

      <!-- 筛选栏：日期 / 用户 / 科目 -->
      <div class="mt-2.5 bg-white rounded-2xl p-3 border border-slate-100 grid grid-cols-3 gap-2 text-xs">
        <input
          v-model="filters.date"
          type="date"
          class="px-2 py-1.5 rounded-lg border border-slate-200 bg-slate-50"
          @change="onFilterChange"
        />
        <select
          v-model="filters.user_code"
          class="px-2 py-1.5 rounded-lg border border-slate-200 bg-slate-50"
          @change="onFilterChange"
        >
          <option value="">全部用户</option>
          <option v-for="u in users" :key="u.referral_code" :value="u.referral_code">
            {{ u.nickname ? `${u.nickname} (${u.referral_code})` : u.referral_code }}
          </option>
        </select>
        <select
          v-model="filters.subject"
          class="px-2 py-1.5 rounded-lg border border-slate-200 bg-slate-50"
          @change="onFilterChange"
        >
          <option value="">全部科目</option>
          <option value="english">英语</option>
          <option value="math">数学</option>
        </select>
      </div>

      <!-- 日历视图 -->
      <div v-if="recordsSubMode === 'calendar'" class="mt-3 bg-white rounded-3xl p-4 shadow-sm border border-slate-100">
        <div class="flex items-center justify-between mb-3">
          <button
            type="button"
            class="px-3 py-1.5 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold active:scale-95"
            @click="shiftMonth(-1)"
          >
            ◀ 上个月
          </button>
          <span class="text-sm font-black text-slate-900">{{ calendarMonthLabel }}</span>
          <button
            type="button"
            class="px-3 py-1.5 rounded-xl bg-slate-100 text-slate-700 text-xs font-bold active:scale-95"
            @click="shiftMonth(1)"
          >
            下个月 ▶
          </button>
        </div>

        <!-- 配色图例 -->
        <div class="flex items-center justify-center gap-4 text-[11px] text-slate-600 mb-3 pb-2.5 border-b border-slate-100">
          <span class="flex items-center gap-1"><i class="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></i>完美通过</span>
          <span class="flex items-center gap-1"><i class="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block"></i>通关未满分</span>
          <span class="flex items-center gap-1"><i class="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block"></i>未通关</span>
        </div>

        <!-- 星期表头 -->
        <div class="grid grid-cols-7 gap-1.5 text-center text-[11px] font-bold text-slate-400 mb-1.5">
          <span v-for="w in ['日', '一', '二', '三', '四', '五', '六']" :key="w">{{ w }}</span>
        </div>

        <!-- 当月日期平铺网格 -->
        <div class="grid grid-cols-7 gap-1.5">
          <div v-for="blank in calendarLeadingBlanks" :key="`b-${blank}`" class="h-11"></div>
          <button
            v-for="cell in calendarCells"
            :key="cell.dateStr"
            type="button"
            class="h-11 rounded-xl flex flex-col items-center justify-center text-xs font-bold transition active:scale-95 border"
            :class="calendarCellClass(cell)"
            @click="selectCalendarDate(cell.dateStr)"
          >
            <span>{{ cell.day }}</span>
            <span v-if="cell.count > 0" class="text-[9px] leading-none opacity-90 mt-0.5">{{ cell.count }}次</span>
          </button>
        </div>
      </div>

      <!-- 每日记录列表 -->
      <div v-else class="mt-3 space-y-3">
      <div
        v-for="r in records"
        :key="r.session_id"
        class="bg-white rounded-2xl p-4 shadow-sm border border-slate-100"
      >
        <div class="flex items-center justify-between">
          <div class="text-xs font-black text-slate-800">
            {{ r.nickname || r.referral_code }}
            <span v-if="r.nickname" class="font-normal text-slate-400 ml-1">({{ r.referral_code }})</span>
          </div>
          <span class="text-[11px] font-bold px-2 py-0.5 rounded-full" :class="statusBadge(r.status)">
            {{ statusText(r.status) }}
          </span>
        </div>

        <div class="mt-1.5 text-[11px] text-slate-500 flex flex-wrap gap-x-3 gap-y-1">
          <span>📅 {{ r.started_at_str || r.created_date }}</span>
          <span>📚 {{ r.subject === 'english' ? '英语' : '数学' }} · {{ stageLabel(r.stage_or_grade) }}</span>
          <span>⏱ 耗时 {{ formatDuration(r.duration_minutes) }}</span>
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
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { showToast } from 'vant'
import api from '../api/client'
import { useStudyStore } from '../stores/studyStore'
import MathText from '../components/MathText.vue'

const store = useStudyStore()
const viewMode = ref('learners') // 'learners' | 'records'
const recordsSubMode = ref('list') // 'list' | 'calendar'
const learners = ref([])
const expandedUser = ref(null)
const users = ref([])
const records = ref([])
const filters = reactive({ date: '', user_code: '', subject: '' })

const nowDate = new Date()
const calendarYear = ref(nowDate.getFullYear())
const calendarMonth = ref(nowDate.getMonth() + 1) // 1..12
const calendarDays = ref({})

const calendarMonthStr = computed(
  () => `${calendarYear.value}-${String(calendarMonth.value).padStart(2, '0')}`
)
const calendarMonthLabel = computed(() => `${calendarYear.value}年${calendarMonth.value}月`)
const calendarLeadingBlanks = computed(() => new Date(calendarYear.value, calendarMonth.value - 1, 1).getDay())
const calendarCells = computed(() => {
  const daysInMonth = new Date(calendarYear.value, calendarMonth.value, 0).getDate()
  const list = []
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${calendarMonthStr.value}-${String(d).padStart(2, '0')}`
    const info = calendarDays.value[dateStr]
    list.push({
      day: d,
      dateStr,
      status: info?.status || null,
      count: info?.count || 0
    })
  }
  return list
})

function calendarCellClass(cell) {
  if (cell.status === 'green') return 'bg-emerald-500 text-white border-emerald-600 shadow-sm'
  if (cell.status === 'orange') return 'bg-amber-400 text-amber-950 border-amber-500 shadow-sm'
  if (cell.status === 'red') return 'bg-rose-500 text-white border-rose-600 shadow-sm'
  return 'bg-slate-50 text-slate-600 border-slate-100 hover:bg-slate-100'
}

async function loadCalendar() {
  const params = new URLSearchParams({ month: calendarMonthStr.value })
  if (filters.user_code) params.set('user_code', filters.user_code)
  if (filters.subject) params.set('subject', filters.subject)
  const data = await api.get(`/admin/calendar?${params.toString()}`)
  calendarDays.value = data.days || {}
}

async function openCalendarView() {
  recordsSubMode.value = 'calendar'
  await loadCalendar()
}

async function shiftMonth(delta) {
  let y = calendarYear.value
  let m = calendarMonth.value + delta
  if (m < 1) {
    m = 12
    y -= 1
  } else if (m > 12) {
    m = 1
    y += 1
  }
  calendarYear.value = y
  calendarMonth.value = m
  await loadCalendar()
}

async function selectCalendarDate(dateStr) {
  filters.date = dateStr
  recordsSubMode.value = 'list'
  await loadRecords()
}

async function onFilterChange() {
  if (recordsSubMode.value === 'calendar') {
    await loadCalendar()
  } else {
    await loadRecords()
  }
}

async function loadLearners() {
  const data = await api.get('/admin/learners')
  learners.value = data.learners || []
}

function toggleLearner(code) {
  expandedUser.value = expandedUser.value === code ? null : code
}

async function openLearnerRecords(code) {
  filters.user_code = code
  filters.date = ''
  viewMode.value = 'records'
  recordsSubMode.value = 'list'
  await loadRecords()
}

async function openAllRecords() {
  filters.user_code = ''
  filters.date = ''
  viewMode.value = 'records'
  recordsSubMode.value = 'list'
  await loadRecords()
}

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
async function cleanupInvalid() {
  try {
    const res = await api.delete('/admin/sessions/cleanup')
    showToast(`已清理 ${res.deleted_count ?? 0} 条无效记录`)
    await loadLearners()
    if (viewMode.value === 'records') {
      await loadRecords()
    }
  } catch (err) {
    showToast(err.message || '清理失败')
  }
}

function formatDuration(mins) {
  if (mins === null || mins === undefined) return '未完成'
  return `${mins} 分钟`
}

onMounted(loadLearners)
</script>