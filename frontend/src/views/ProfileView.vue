<template>
  <div class="pb-24 px-4 pt-4">
    <!-- 顶部档案卡与免验证码手机号直绑 -->
    <section class="bg-white rounded-3xl p-5 shadow-sm border border-slate-100">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-xs text-slate-400">专属推荐码档案</div>
          <div class="text-2xl font-black tracking-widest text-indigo-600 mt-0.5">
            {{ store.referralCode }}
          </div>
        </div>
        <div class="text-right">
          <div class="text-xs text-slate-400">双科共享总积分</div>
          <div class="text-2xl font-black text-amber-500">{{ store.totalPoints }} 分</div>
        </div>
      </div>

      <div class="mt-4 pt-4 border-t border-slate-100">
        <label class="block text-xs font-semibold text-slate-600 mb-2">
          绑定/修改手机号（内部自用，免短信验证码）
        </label>
        <div class="flex gap-2">
          <input
            v-model="phoneInput"
            type="tel"
            maxlength="11"
            placeholder="请输入 11 位中国大陆手机号"
            class="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-200 focus:border-indigo-500 focus:bg-white focus:outline-none text-sm font-medium"
          />
          <van-button
            round
            type="primary"
            color="#4f46e5"
            size="small"
            class="px-5 font-bold"
            :loading="savingPhone"
            @click="savePhone"
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
          <div class="mt-3 flex gap-1.5 overflow-x-auto pb-1">
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

          <!-- 一/二/三级词库只读清单 -->
          <div class="mt-3 bg-white rounded-3xl p-4 shadow-sm border border-slate-100">
            <div class="text-xs font-bold text-slate-500 mb-3">
              三阶动态词库清单（点击单词查看只读卡片 · 严禁测试与计分）
            </div>
            <div v-for="tier in tierConfigs" :key="tier.key" class="mb-3 last:mb-0">
              <div class="flex items-center justify-between text-xs font-bold mb-1.5" :class="tier.textClass">
                <span>{{ tier.title }}</span>
                <span>{{ (enArchive.tiers[tier.key] || []).length }} 词</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="w in enArchive.tiers[tier.key] || []"
                  :key="w.id"
                  type="button"
                  class="px-2.5 py-1 rounded-lg text-xs font-semibold border transition active:scale-95"
                  :class="tier.chipClass"
                  @click="openReadonlyWord(w)"
                >
                  {{ w.word }}
                </button>
                <span v-if="!(enArchive.tiers[tier.key] || []).length" class="text-xs text-slate-400">暂无单词</span>
              </div>
            </div>
          </div>

          <!-- 英语历史批次（含耗时、首次错词标红） -->
          <div class="mt-3 space-y-3">
            <div
              v-for="h in enArchive.history"
              :key="h.session_id"
              class="bg-white rounded-2xl p-4 shadow-sm border border-slate-100"
            >
              <div class="flex items-center justify-between text-xs">
                <span class="font-bold text-slate-700">{{ h.created_date }} · {{ stageLabel(h.grade_stage) }}</span>
                <span
                  class="px-2 py-0.5 rounded-full font-bold"
                  :class="statusBadge(h.status)"
                >
                  {{ statusText(h.status) }}
                </span>
              </div>
              <div class="text-[11px] text-slate-400 mt-1">
                耗时：{{ h.duration_sec ? `${h.duration_sec}秒` : '未完成' }} · 提交 {{ h.attempt_count }} 次 · 净积分 {{ h.total_score_delta >= 0 ? '+' : '' }}{{ h.total_score_delta }}
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
                <span class="font-bold text-slate-700">{{ h.created_date }} · {{ stageLabel(h.grade) }}</span>
                <span class="px-2 py-0.5 rounded-full font-bold" :class="statusBadge(h.status)">
                  {{ statusText(h.status) }}
                </span>
              </div>
              <div class="text-[11px] text-slate-400 mt-1">
                耗时：{{ h.duration_sec ? `${h.duration_sec}秒` : '未完成' }} · 净积分 {{ h.total_score_delta >= 0 ? '+' : '' }}{{ h.total_score_delta }}
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
const phoneInput = ref(store.phone || '')
const savingPhone = ref(false)
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
  { key: 'level_3', title: '三级熟练词库', textClass: 'text-emerald-700', chipClass: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  { key: 'level_2', title: '二级巩固词库', textClass: 'text-amber-700', chipClass: 'bg-amber-50 text-amber-800 border-amber-200' },
  { key: 'level_1', title: '一级新词词库', textClass: 'text-slate-600', chipClass: 'bg-slate-50 text-slate-700 border-slate-200' }
]

const enArchive = reactive({ history: [], tiers: { level_1: [], level_2: [], level_3: [] } })
const mathArchive = reactive({ history: [], wrong_book: [] })

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

async function savePhone() {
  const cleaned = phoneInput.value.trim()
  if (!/^1[3-9]\d{9}$/.test(cleaned)) {
    showToast('请输入有效的 11 位中国大陆手机号')
    return
  }
  savingPhone.value = true
  try {
    await store.bindPhone(cleaned)
    showToast('手机号绑定已保存')
  } catch (err) {
    showToast(err.message || '保存失败')
  } finally {
    savingPhone.value = false
  }
}

async function loadEnglishArchive() {
  const query = enFilter.value ? `?grade_stage=${enFilter.value}` : ''
  const data = await api.get(`/archive/english${query}`)
  enArchive.history = data.history || []
  enArchive.tiers = data.tiers || { level_1: [], level_2: [], level_3: [] }
}

async function loadMathArchive() {
  const query = mathFilter.value ? `?grade=${mathFilter.value}` : ''
  const data = await api.get(`/archive/math${query}`)
  mathArchive.history = data.history || []
  mathArchive.wrong_book = data.wrong_book || []
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
  phoneInput.value = store.phone || ''
  await Promise.all([loadEnglishArchive(), loadMathArchive()])
})
</script>
