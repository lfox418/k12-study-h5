<template>
  <div class="pb-24 px-4 pt-4">
    <!-- 顶部档案卡与免验证码手机号直绑 -->
    <section class="bg-white rounded-3xl p-5 shadow-sm border border-slate-100">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-xs text-slate-400">
            {{ store.nickname ? `推荐码：${store.referralCode}` : '专属推荐码档案' }}
          </div>
          <div class="text-2xl font-black tracking-wide text-indigo-600 mt-0.5">
            {{ store.displayName }}
          </div>
        </div>
        <div class="text-right">
          <div class="text-xs text-slate-400">双科共享总积分</div>
          <div class="text-2xl font-black text-amber-500">{{ store.totalPoints }} 分</div>
        </div>
      </div>

      <div class="mt-4 pt-4 border-t border-slate-100">
        <label class="block text-xs font-semibold text-slate-600 mb-2">
          绑定/修改昵称（全局唯一，绑定后用于全局展示）
        </label>
        <div class="flex gap-2">
          <input
            v-model="nicknameInput"
            type="text"
            maxlength="20"
            placeholder="请输入 2~20 位唯一昵称（中英文、数字、_-）"
            class="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-200 focus:border-indigo-500 focus:bg-white focus:outline-none text-sm font-medium"
          />
          <van-button
            round
            type="primary"
            color="#4f46e5"
            size="small"
            class="px-5 font-bold"
            :loading="savingNickname"
            @click="saveNickname"
          >
            保存
          </van-button>
        </div>
      </div>

      <div class="mt-3 flex justify-end">
        <button
          type="button"
          class="text-xs text-slate-400 hover:text-rose-500 underline"
          @click="store.logout()"
        >
          切换推荐码
        </button>
      </div>
    </section>

    <!-- 双科只读复习档案切换 -->
    <div class="mt-5">
      <van-tabs v-model:active="activeArchiveTab" color="#4f46e5" background="transparent" animated>
        <!-- 英语只读档案 -->
        <van-tab title="英语词库与历史" name="english">
          <!-- 外层：三张词库等级卡片垂直堆叠（默认全折叠 + 全局唯一展开互斥） -->
          <div class="mt-3 space-y-2.5">
            <div class="text-xs font-bold text-slate-500 px-1">
              分级词库清单（点击单词查看只读卡片 · 严禁测试与计分）
            </div>
            <div
              v-for="tier in tierConfigs"
              :key="tier.key"
              class="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden"
            >
              <!-- 外层卡片头部 -->
              <button
                type="button"
                class="w-full px-4 py-3.5 flex items-center justify-between text-left transition active:bg-slate-50"
                @click="toggleLevelCard(tier.key)"
              >
                <div class="flex items-center gap-2">
                  <span class="text-sm font-black" :class="tier.textClass">{{ tier.title }}</span>
                  <span class="text-[11px] font-bold px-2 py-0.5 rounded-full" :class="tier.badgeClass">
                    共 {{ (enArchive.tiers[tier.key] || []).length }} 词
                  </span>
                </div>
                <span class="text-xs text-slate-400 font-bold">
                  {{ activeLevelCard === tier.key ? '收起 ▲' : '展开 ▼' }}
                </span>
              </button>

              <!-- 内层：4 个学段折叠抽屉 -->
              <div v-if="activeLevelCard === tier.key" class="px-3 pb-3 pt-1 space-y-2 border-t border-slate-100 bg-slate-50/50">
                <div
                  v-for="stage in englishStageDrawers"
                  :key="`${tier.key}-${stage.value}`"
                  class="bg-white rounded-2xl border border-slate-200/80 overflow-hidden"
                >
                  <button
                    type="button"
                    class="w-full px-3.5 py-2.5 flex items-center justify-between text-left text-xs font-bold text-slate-700"
                    @click="toggleStageDrawer(tier.key, stage.value)"
                  >
                    <span>{{ stage.label }}</span>
                    <div class="flex items-center gap-2">
                      <span class="text-[11px] text-slate-500 font-semibold">
                        {{ getStageWords(tier.key, stage.value).length }} 词
                      </span>
                      <span class="text-[10px] text-slate-400">
                        {{ activeDrawerKey === `${tier.key}-${stage.value}` ? '▲' : '▼' }}
                      </span>
                    </div>
                  </button>

                  <div
                    v-if="activeDrawerKey === `${tier.key}-${stage.value}`"
                    class="px-3.5 pb-3 pt-2 border-t border-slate-100 flex flex-wrap gap-1.5"
                  >
                    <button
                      v-for="w in getStageWords(tier.key, stage.value)"
                      :key="w.id"
                      type="button"
                      class="px-2.5 py-1 rounded-lg text-xs font-semibold border transition active:scale-95"
                      :class="tier.chipClass"
                      @click="openReadonlyWord(w)"
                    >
                      {{ w.word }}
                    </button>
                    <span
                      v-if="!getStageWords(tier.key, stage.value).length"
                      class="text-xs text-slate-400"
                    >
                      该学段暂无单词
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-4 flex gap-1.5 overflow-x-auto pb-1">
            <button
              v-for="s in enStageFilters"
              :key="s.value"
              type="button"
              class="shrink-0 px-3 py-1.5 rounded-full text-xs font-bold border"
              :class="enFilter === s.value ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-200'"
              @click="enFilter = s.value; loadEnglishArchive()"
            >
              {{ s.label }}
            </button>
          </div>

          <!-- 英语历史批次（含耗时分钟、首次错词标红） -->
          <div class="mt-3 space-y-3">
            <div
              v-for="h in enArchive.history"
              :key="h.session_id"
              class="bg-white rounded-2xl p-4 shadow-sm border border-slate-100"
            >
              <div class="flex items-center justify-between text-xs">
                <span class="font-bold text-slate-700">{{ h.started_at_str || h.created_date }} · {{ stageLabel(h.grade_stage) }}</span>
                <span
                  class="px-2 py-0.5 rounded-full font-bold"
                  :class="statusBadge(h.status)"
                >
                  {{ statusText(h.status) }}
                </span>
              </div>
              <div class="text-[11px] text-slate-400 mt-1">
                耗时：{{ formatDurationMinutes(h.duration_minutes) }} · 提交 {{ h.attempt_count }} 次 · 净积分 {{ h.total_score_delta >= 0 ? '+' : '' }}{{ h.total_score_delta }}
              </div>
              <div class="mt-2.5 flex flex-wrap gap-1.5">
                <button
                  v-for="w in h.words"
                  :key="w.id"
                  type="button"
                  class="px-2 py-0.5 rounded-md text-xs font-semibold border"
                  :class="w.first_wrong
                    ? 'bg-rose-50 text-rose-600 border-rose-300'
                    : 'bg-slate-50 text-slate-700 border-slate-200'"
                  @click="openReadonlyWord(w)"
                >
                  {{ w.word }}
                </button>
              </div>
            </div>
            <div v-if="!enArchive.history.length" class="text-center text-xs text-slate-400 py-6">
              暂无英语学习历史批次
            </div>
            <van-button
              v-if="enArchive.hasMore"
              block
              plain
              round
              size="small"
              color="#4f46e5"
              @click="loadEnglishArchive(true)"
            >
              加载更多历史
            </van-button>
          </div>
        </van-tab>

        <!-- 数学只读档案与错题本 -->
        <van-tab title="数学错题本与历史" name="math">
          <div class="mt-3 flex gap-1.5 pb-1">
            <button
              v-for="g in mathGradeFilters"
              :key="g.value"
              type="button"
              class="px-3 py-1.5 rounded-full text-xs font-bold border"
              :class="mathFilter === g.value ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-slate-600 border-slate-200'"
              @click="mathFilter = g.value; loadMathArchive()"
            >
              {{ g.label }}
            </button>
          </div>

          <!-- 数学错题本（只读 LaTeX 分步解析） -->
          <div class="mt-3 bg-white rounded-3xl p-4 shadow-sm border border-slate-100">
            <div class="text-xs font-bold text-rose-600 mb-3">
              数学错题本（共 {{ mathArchive.wrong_book.length }} 题 · 只读解析不计分）
            </div>
            <div v-if="mathArchive.wrong_book.length" class="space-y-2.5">
              <div
                v-for="q in mathArchive.wrong_book"
                :key="q.id"
                class="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 cursor-pointer active:bg-slate-100"
                @click="openReadonlyMath(q)"
              >
                <div class="flex items-center justify-between text-[11px] mb-1">
                  <span class="font-bold text-teal-700">{{ q.topic_tag }}</span>
                  <span class="text-rose-500">累计错 {{ q.wrong_count }} 次 · 点击看解析</span>
                </div>
                <div class="text-xs text-slate-700 line-clamp-2">
                  <MathText :content="q.stem" />
                </div>
              </div>
            </div>
            <div v-else class="text-xs text-slate-400 text-center py-4">暂无错题记录，继续保持！</div>
          </div>

          <!-- 数学历史 3 题批次 -->
          <div class="mt-3 space-y-3">
            <div
              v-for="h in mathArchive.history"
              :key="h.session_id"
              class="bg-white rounded-2xl p-4 shadow-sm border border-slate-100"
            >
              <div class="flex items-center justify-between text-xs">
                <span class="font-bold text-slate-700">{{ h.started_at_str || h.created_date }} · {{ stageLabel(h.grade) }}</span>
                <span class="px-2 py-0.5 rounded-full font-bold" :class="statusBadge(h.status)">
                  {{ statusText(h.status) }}
                </span>
              </div>
              <div class="text-[11px] text-slate-400 mt-1">
                耗时：{{ formatDurationMinutes(h.duration_minutes) }} · 净积分 {{ h.total_score_delta >= 0 ? '+' : '' }}{{ h.total_score_delta }}
              </div>
              <div class="mt-2.5 space-y-1.5">
                <button
                  v-for="(q, idx) in h.questions"
                  :key="q.id"
                  type="button"
                  class="w-full text-left px-3 py-2 rounded-xl text-xs border flex items-center justify-between"
                  :class="q.first_wrong ? 'bg-rose-50 border-rose-200 text-rose-700' : 'bg-slate-50 border-slate-200 text-slate-700'"
                  @click="openReadonlyMath(q)"
                >
                  <span>第{{ idx + 1 }}题 · {{ q.topic_tag }}</span>
                  <span class="text-[11px] opacity-75">查看解析 ›</span>
                </button>
              </div>
            </div>
                <div v-if="!mathArchive.history.length" class="text-center text-xs text-slate-400 py-6">
              暂无数学学习历史批次
            </div>
            <van-button
              v-if="mathArchive.hasMore"
              block
              plain
              round
              size="small"
              color="#0d9488"
              @click="loadMathArchive(true)"
            >
              加载更多历史
            </van-button>
          </div>
        </van-tab>

        <!-- 积分流水明细 -->
        <van-tab title="积分明细" name="ledger">
          <div class="mt-3 space-y-2.5">
            <div
              v-for="item in ledgerState.items"
              :key="item.id"
              class="bg-white rounded-2xl p-3.5 shadow-sm border border-slate-100 flex items-center justify-between gap-3"
            >
              <div class="min-w-0">
                <div class="text-xs font-bold text-slate-800 truncate">{{ item.reason }}</div>
                <div class="text-[11px] text-slate-400 mt-0.5">
                  {{ item.created_at }} · 余额 {{ item.balance_after }} 分
                </div>
              </div>
              <div
                class="text-sm font-black shrink-0 tabular-nums"
                :class="item.delta >= 0 ? 'text-emerald-600' : 'text-rose-600'"
              >
                {{ item.delta >= 0 ? '+' : '' }}{{ item.delta }}
              </div>
            </div>
            <div v-if="!ledgerState.items.length" class="text-center text-xs text-slate-400 py-6">
              暂无积分变动记录
            </div>
            <van-button
              v-if="ledgerState.hasMore"
              block
              plain
              round
              size="small"
              color="#4f46e5"
              @click="loadPointLedger(true)"
            >
              加载更多明细
            </van-button>
          </div>
        </van-tab>
      </van-tabs>
    </div>

    <!-- 英语只读记忆卡片弹窗 -->
    <WordDetailModal v-model:show="wordModalOpen" :word-item="activeWord" />

    <!-- 数学只读 LaTeX 分步解析弹窗 -->
    <van-popup
      v-model:show="mathModalOpen"
      round
      position="bottom"
      :style="{ maxWidth: '480px', margin: '0 auto', left: 0, right: 0, maxHeight: '80vh', overflowY: 'auto' }"
    >
      <div v-if="activeMath" class="p-6">
        <span class="inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 mb-2">
          只读数学解析 · 不参与复核与计分
        </span>
        <div class="text-xs font-bold text-teal-700 mb-1">{{ activeMath.topic_tag }}</div>
        <div class="text-sm text-slate-900 leading-relaxed">
          <MathText :content="activeMath.stem" />
        </div>
        <div class="mt-3 text-xs font-bold text-emerald-700">
          标准答案：{{ activeMath.answer }}
        </div>
        <div class="mt-3 p-4 rounded-2xl bg-slate-50 border border-slate-100 text-xs text-slate-700 leading-relaxed">
          <div class="font-bold text-teal-700 mb-1">分步详细解析：</div>
          <MathText :content="activeMath.analysis" />
        </div>
        <van-button block round type="primary" color="#0d9488" class="mt-5" @click="mathModalOpen = false">
          关闭解析
        </van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { showToast } from 'vant'
import api from '../api/client'
import { useStudyStore } from '../stores/studyStore'
import WordDetailModal from '../components/WordDetailModal.vue'
import MathText from '../components/MathText.vue'

const store = useStudyStore()
const nicknameInput = ref(store.nickname || '')
const savingNickname = ref(false)
const activeArchiveTab = ref('english')

const enFilter = ref('')
const mathFilter = ref('')

const enStageFilters = [
  { value: '', label: '全部学段' },
  { value: 'primary', label: '小学' },
  { value: 'grade_7', label: '初一' },
  { value: 'grade_8', label: '初二' },
  { value: 'grade_9', label: '初三' }
]

const mathGradeFilters = [
  { value: '', label: '全部年级' },
  { value: 'grade_7', label: '初一' },
  { value: 'grade_8', label: '初二' },
  { value: 'grade_9', label: '初三' }
]

const tierConfigs = [
  {
    key: 'level_1',
    title: '一级词库（生词本）',
    textClass: 'text-slate-700',
    badgeClass: 'bg-slate-100 text-slate-600',
    chipClass: 'bg-slate-50 text-slate-700 border-slate-200'
  },
  {
    key: 'level_2',
    title: '二级词库（巩固中）',
    textClass: 'text-amber-700',
    badgeClass: 'bg-amber-100 text-amber-800',
    chipClass: 'bg-amber-50 text-amber-800 border-amber-200'
  },
  {
    key: 'level_3',
    title: '三级词库（已掌握）',
    textClass: 'text-emerald-700',
    badgeClass: 'bg-emerald-100 text-emerald-700',
    chipClass: 'bg-emerald-50 text-emerald-700 border-emerald-200'
  }
]

const englishStageDrawers = [
  { value: 'primary', label: '小学核心词（primary）' },
  { value: 'grade_7', label: '初一核心词（grade_7）' },
  { value: 'grade_8', label: '初二核心词（grade_8）' },
  { value: 'grade_9', label: '初三核心词（grade_9）' }
]

const activeLevelCard = ref(null)
const activeDrawerKey = ref(null)

function toggleLevelCard(levelKey) {
  if (activeLevelCard.value === levelKey) {
    activeLevelCard.value = null
    activeDrawerKey.value = null
  } else {
    activeLevelCard.value = levelKey
    activeDrawerKey.value = null
  }
}

function toggleStageDrawer(levelKey, stageValue) {
  const key = `${levelKey}-${stageValue}`
  if (activeDrawerKey.value === key) {
    activeDrawerKey.value = null
  } else {
    activeLevelCard.value = levelKey
    activeDrawerKey.value = key
  }
}

function getStageWords(levelKey, stageValue) {
  const list = enArchive.tiers[levelKey] || []
  return list.filter((w) => w.grade_stage === stageValue)
}

function formatDurationMinutes(mins) {
  if (mins === null || mins === undefined) return '未完成'
  return `${mins} 分钟`
}

const enArchive = reactive({ history: [], hasMore: false, tiers: { level_1: [], level_2: [], level_3: [] } })
const mathArchive = reactive({ history: [], hasMore: false, wrong_book: [] })
const ledgerState = reactive({ items: [], hasMore: false })

const wordModalOpen = ref(false)
const activeWord = ref(null)
const mathModalOpen = ref(false)
const activeMath = ref(null)

function openReadonlyWord(w) {
  activeWord.value = w
  wordModalOpen.value = true
}

function openReadonlyMath(q) {
  activeMath.value = q
  mathModalOpen.value = true
}

async function saveNickname() {
  const cleaned = nicknameInput.value.trim()
  if (!/^[\u4e00-\u9fa5A-Za-z0-9_-]{2,20}$/.test(cleaned)) {
    showToast('请输入 2~20 位有效昵称（仅支持中英文、数字、_-）')
    return
  }
  savingNickname.value = true
  try {
    await store.bindNickname(cleaned)
    showToast('昵称绑定已保存')
  } catch (err) {
    showToast(err.message || '保存失败')
  } finally {
    savingNickname.value = false
  }
}

async function loadEnglishArchive(append = false) {
  const params = new URLSearchParams({ limit: '30', offset: String(append ? enArchive.history.length : 0) })
  if (enFilter.value) params.set('grade_stage', enFilter.value)
  const data = await api.get(`/archive/english?${params.toString()}`)
  const rows = data.history || []
  enArchive.history = append ? [...enArchive.history, ...rows] : rows
  enArchive.hasMore = Boolean(data.has_more)
  // 词库清单始终保持全学段完整数据（若筛选了学段，则单独拉取全量 tiers）
  if (!enFilter.value) {
    enArchive.tiers = data.tiers || { level_1: [], level_2: [], level_3: [] }
  } else if (!append) {
    const allData = await api.get('/archive/english?limit=1&offset=0')
    enArchive.tiers = allData.tiers || { level_1: [], level_2: [], level_3: [] }
  }
}

async function loadMathArchive(append = false) {
  const params = new URLSearchParams({ limit: '30', offset: String(append ? mathArchive.history.length : 0) })
  if (mathFilter.value) params.set('grade', mathFilter.value)
  const data = await api.get(`/archive/math?${params.toString()}`)
  const rows = data.history || []
  mathArchive.history = append ? [...mathArchive.history, ...rows] : rows
  mathArchive.hasMore = Boolean(data.has_more)
  mathArchive.wrong_book = data.wrong_book || []
}

async function loadPointLedger(append = false) {
  const offset = append ? ledgerState.items.length : 0
  const data = await api.get(`/user/point-ledger?limit=30&offset=${offset}`)
  const rows = data.items || []
  ledgerState.items = append ? [...ledgerState.items, ...rows] : rows
  ledgerState.hasMore = Boolean(data.has_more)
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

onMounted(async () => {
  nicknameInput.value = store.nickname || ''
  await Promise.all([loadEnglishArchive(), loadMathArchive(), loadPointLedger()])
})
</script>
