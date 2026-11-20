<template>
  <div class="h5-shell" :class="{ 'animate-screen-shake': store.effectState.shaking }">
    <!-- 启动校验加载态 -->
    <div v-if="booting" class="min-h-screen flex items-center justify-center text-slate-400 text-sm">
      正在校验推荐码档案...
    </div>

    <!-- 全局强制前置关卡：未通过 6 位推荐码校验前严禁进入任何科目页面 -->
    <ReferralGateView v-else-if="!store.isAuthenticated" />
    <!-- 隐藏推荐码：直接进入全局每日记录看板 -->
    <AdminRecordsView v-else-if="store.isAdmin" />
    <!-- 已授权主界面 -->
    <template v-else>
      <HallView v-if="store.activeTab === 'hall'" />
      <EnglishStudyView v-else-if="store.activeTab === 'english'" />
      <MathStudyView v-else-if="store.activeTab === 'math'" />
      <ProfileView v-else-if="store.activeTab === 'profile'" />

      <!-- 底部导航（仅在大厅与个人中心显示，学习沉浸态隐藏防干扰） -->
      <div
        v-if="store.activeTab === 'hall' || store.activeTab === 'profile'"
        class="fixed bottom-0 left-0 right-0 max-w-[480px] mx-auto bg-white/95 backdrop-blur border-t border-slate-200 flex z-30"
      >
        <button
          type="button"
          class="flex-1 py-3 flex flex-col items-center text-xs font-bold transition"
          :class="store.activeTab === 'hall' ? 'text-indigo-600' : 'text-slate-400'"
          @click="store.activeTab = 'hall'; store.refreshProfile()"
        >
          <span class="text-lg">🏠</span>
          <span>学习大厅</span>
        </button>
        <button
          type="button"
          class="flex-1 py-3 flex flex-col items-center text-xs font-bold transition"
          :class="store.activeTab === 'profile' ? 'text-indigo-600' : 'text-slate-400'"
          @click="store.activeTab = 'profile'"
        >
          <span class="text-lg">👤</span>
          <span>个人中心</span>
        </button>
      </div>
    </template>

    <!-- 全屏游戏化加分/扣分特效层 -->
    <ScoreEffectOverlay />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useStudyStore } from './stores/studyStore'
import ReferralGateView from './views/ReferralGateView.vue'
import HallView from './views/HallView.vue'
import EnglishStudyView from './views/EnglishStudyView.vue'
import MathStudyView from './views/MathStudyView.vue'
import ProfileView from './views/ProfileView.vue'
import ScoreEffectOverlay from './components/ScoreEffectOverlay.vue'
import AdminRecordsView from './views/AdminRecordsView.vue'
const store = useStudyStore()
const booting = ref(true)

function handleUnauthorized() {
  store.logout()
}

onMounted(async () => {
  window.addEventListener('k12:unauthorized', handleUnauthorized)
  await store.restoreSession()
  booting.value = false
})

onBeforeUnmount(() => {
  window.removeEventListener('k12:unauthorized', handleUnauthorized)
})
</script>
