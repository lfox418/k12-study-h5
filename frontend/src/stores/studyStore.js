import { defineStore } from 'pinia'
import api, {
  clearStoredReferralCode,
  getStoredReferralCode,
  setStoredReferralCode
} from '../api/client'

export const useStudyStore = defineStore('study', {
  state: () => ({
    referralCode: getStoredReferralCode(),
    phone: null,
    totalPoints: 0,
    isAdmin: false,
    todayEnglishPassed: false,
    todayMathPassed: false,
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

  actions: {
    async restoreSession() {
      const code = getStoredReferralCode()
      if (!code || code.length !== 6) {
        this.isAuthenticated = false
        if (this.isAdmin) this.activeTab = 'admin'
        return false
      }
      try {
        const profile = await api.get('/user/profile')
        this.applyProfile(profile)
        this.isAuthenticated = true
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
      this.activeTab = 'hall'
      return res.profile
    },

    applyProfile(profile) {
      if (!profile) return
      this.referralCode = profile.referral_code
      this.phone = profile.phone || null
      this.isAdmin = Boolean(profile.is_admin)
      this.totalPoints = profile.total_points ?? 0
      this.todayEnglishPassed = Boolean(profile.today_english_passed)
      this.todayMathPassed = Boolean(profile.today_math_passed)
    },

    async refreshProfile() {
      if (!this.isAuthenticated) return
      const profile = await api.get('/user/profile')
      this.applyProfile(profile)
    },

    async bindPhone(phone) {
      const res = await api.put('/user/phone', { phone })
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
      this.phone = null
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
