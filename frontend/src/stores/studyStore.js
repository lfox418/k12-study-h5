import { defineStore } from 'pinia'
import api, {
  clearStoredReferralCode,
  getStoredReferralCode,
  setStoredReferralCode
} from '../api/client'

export const useStudyStore = defineStore('study', {
  state: () => ({
    referralCode: getStoredReferralCode(),
    nickname: null,
    totalPoints: 0,
    isAdmin: false,
    todayEnglishPassed: false,
    todayMathPassed: false,
    quota: {
      english_used_minutes: 0,
      english_remaining_minutes: 30,
      math_used_minutes: 0,
      math_remaining_minutes: 10,
      total_used_minutes: 0,
      total_remaining_minutes: 40,
      english_locked: false,
      math_locked: false
    },
    isAuthenticated: false,
    activeTab: 'hall', // 'hall' | 'english' | 'math' | 'profile'
    activeSession: null, // 当前进行中的学习批次
    // 全局特效状态
    effectState: {
      visible: false,
      type: 'bonus', // 'bonus' | 'penalty'
      headline: '',
      subline: '',
      shaking: false
    }
  }),

  getters: {
    displayName: (state) => state.nickname || state.referralCode
  },

  actions: {
    async restoreSession() {
      const code = getStoredReferralCode()
      if (!code || code.length !== 6) {
        this.isAuthenticated = false
        return false
      }
      try {
        const profile = await api.get('/user/profile')
        this.applyProfile(profile)
        this.isAuthenticated = true
        this.activeSession = null
        this.activeTab = 'hall'
        return true
      } catch {
        this.logout()
        return false
      }
    },

    async verifyReferralCode(code) {
      const cleaned = (code || '').trim().toUpperCase()
      const res = await api.post('/auth/verify-code', { referral_code: cleaned })
      setStoredReferralCode(res.profile.referral_code)
      this.applyProfile(res.profile)
      this.isAuthenticated = true
      this.activeSession = null
      this.activeTab = 'hall'
      return res.profile
    },

    async restoreActiveSession() {
      try {
        const res = await api.get('/sessions/active')
        const data = res?.active_session
        if (data) {
          const localNow = Math.floor(Date.now() / 1000)
          data.clockOffset = (data.server_now || localNow) - localNow
          this.activeSession = data
          this.activeTab = data.subject
          return data
        }
      } catch {
        // 恢复失败不影响正常进入大厅
      }
      return null
    },

    applyProfile(profile) {
      if (!profile) return
      this.referralCode = profile.referral_code
      this.nickname = profile.nickname || null
      this.isAdmin = Boolean(profile.is_admin)
      this.totalPoints = Number(profile.total_points ?? 0)
      this.todayEnglishPassed = Boolean(profile.today_english_passed)
      this.todayMathPassed = Boolean(profile.today_math_passed)
      if (profile.quota) {
        this.quota = profile.quota
      }
    },

    async refreshProfile() {
      if (!this.isAuthenticated) return
      const profile = await api.get('/user/profile')
      this.applyProfile(profile)
    },

    async bindNickname(nickname) {
      const res = await api.put('/user/nickname', { nickname })
      this.applyProfile(res.profile)
      return res.profile
    },

    async startSession(subject, stageOrGrade) {
      const data = await api.post('/sessions/start', {
        subject,
        stage_or_grade: stageOrGrade
      })
      // 记录服务器时钟与本地时钟偏差，防止本地时间不准
      const localNow = Math.floor(Date.now() / 1000)
      data.clockOffset = (data.server_now || localNow) - localNow
      this.activeSession = data
      this.activeTab = subject
      return data
    },

    async submitSession(sessionId, answers) {
      const res = await api.post(`/sessions/${sessionId}/submit`, { answers })
      if (typeof res.total_points === 'number') {
        this.totalPoints = res.total_points
      }
      if (res.all_correct) {
        if (res.subject === 'english') this.todayEnglishPassed = true
        if (res.subject === 'math') this.todayMathPassed = true
      }
      return res
    },

    async checkExpiry(sessionId) {
      return api.post(`/sessions/${sessionId}/check-expiry`)
    },

    async sendQuotaHeartbeat(subject, deltaSeconds, sessionId = null) {
      if (!this.isAuthenticated || deltaSeconds <= 0) return null
      const res = await api.post('/quota/heartbeat', {
        subject,
        delta_seconds: Math.round(deltaSeconds),
        session_id: sessionId
      })
      if (res?.quota) {
        this.quota = res.quota
      }
      return res
    },

    sendQuotaBeacon(subject, deltaSeconds, sessionId = null) {
      if (!this.isAuthenticated || !this.referralCode || deltaSeconds <= 0) return
      if (typeof navigator === 'undefined' || !navigator.sendBeacon) return
      const apiBase = import.meta.env.VITE_API_BASE || '/api'
      const payload = JSON.stringify({
        subject,
        delta_seconds: Math.round(deltaSeconds),
        session_id: sessionId,
        referral_code: this.referralCode
      })
      const blob = new Blob([payload], { type: 'application/json' })
      navigator.sendBeacon(`${apiBase}/quota/heartbeat`, blob)
    },

    clearActiveSession() {
      this.activeSession = null
      this.activeTab = 'hall'
    },

    triggerEffect({ type, headline, subline = '' }) {
      this.effectState = {
        visible: true,
        type,
        headline,
        subline,
        shaking: type === 'penalty'
      }
      setTimeout(() => {
        this.effectState.shaking = false
      }, 500)
      setTimeout(() => {
        this.effectState.visible = false
      }, 2400)
    },

    logout() {
      clearStoredReferralCode()
      this.referralCode = ''
      this.nickname = null
      this.isAdmin = false
      this.totalPoints = 0
      this.todayEnglishPassed = false
      this.todayMathPassed = false
      this.isAuthenticated = false
      this.activeSession = null
      this.activeTab = 'hall'
    }
  }
})
