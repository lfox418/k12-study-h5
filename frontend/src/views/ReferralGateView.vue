<template>
  <div class="min-h-screen flex flex-col items-center justify-center px-6 bg-gradient-to-b from-indigo-600 via-indigo-700 to-slate-900 text-white">
    <div class="w-full max-w-sm bg-white text-slate-800 rounded-3xl shadow-2xl p-7">
      <div class="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-3xl mx-auto mb-4">
        🎓
      </div>
      <h1 class="text-xl font-black text-center text-slate-900">
        K12 双科自主学习系统
      </h1>
      <p class="text-xs text-center text-slate-500 mt-1.5">
        英语分级背词 · 初中数学每日三题
      </p>

      <div class="mt-6">
        <label class="block text-xs font-semibold text-slate-500 mb-2">
          请输入 6 位专属推荐码开启学习
        </label>
        <input
          v-model="code"
          type="text"
          maxlength="6"
          autocomplete="off"
          placeholder="例如：K12001"
          class="w-full text-center text-2xl font-black tracking-[0.35em] uppercase py-3.5 px-4 rounded-2xl border-2 border-slate-200 focus:border-indigo-500 focus:outline-none bg-slate-50 transition"
          @keyup.enter="handleUnlock"
        />
        <p v-if="errorMsg" class="text-xs text-rose-500 mt-2 text-center">
          {{ errorMsg }}
        </p>
      </div>

      <van-button
        block
        round
        type="primary"
        color="#4f46e5"
        size="large"
        class="mt-6 font-bold"
        :loading="loading"
        @click="handleUnlock"
      >
        开启今日学习
      </van-button>

      <div class="mt-5 pt-4 border-t border-slate-100 text-[11px] text-slate-400 text-center leading-relaxed">
        推荐码即您的独立多端学习档案 ID，关联双科进度与积分。<br />
        内测体验码：<span class="font-mono font-semibold text-indigo-600">K12001</span> / <span class="font-mono font-semibold text-indigo-600">STU888</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useStudyStore } from '../stores/studyStore'

const store = useStudyStore()
const code = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleUnlock() {
  const cleaned = code.value.trim().toUpperCase()
  if (!/^[A-Z0-9]{6}$/.test(cleaned)) {
    errorMsg.value = '请输入 6 位数字或字母组成的推荐码'
    return
  }
  errorMsg.value = ''
  loading.value = true
  try {
    await store.verifyReferralCode(cleaned)
  } catch (err) {
    errorMsg.value = err.message || '推荐码校验失败'
  } finally {
    loading.value = false
  }
}
</script>
