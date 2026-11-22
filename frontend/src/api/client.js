import axios from 'axios'

const STORAGE_KEY = 'k12_referral_code'

export function getStoredReferralCode() {
  return (localStorage.getItem(STORAGE_KEY) || '').trim().toUpperCase()
}

export function setStoredReferralCode(code) {
  localStorage.setItem(STORAGE_KEY, (code || '').trim().toUpperCase())
}

export function clearStoredReferralCode() {
  localStorage.removeItem(STORAGE_KEY)
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000
})

// 请求拦截器：强制注入 X-Referral-Code 请求头
api.interceptors.request.use((config) => {
  const code = getStoredReferralCode()
  if (code) {
    config.headers['X-Referral-Code'] = code
  }
  return config
})

// 响应拦截器：若推荐码失效/未授权，通知应用退回准入关卡
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err?.response?.status
    if (status === 401) {
      clearStoredReferralCode()
      window.dispatchEvent(new CustomEvent('k12:unauthorized'))
    }
    const detail = err?.response?.data?.detail || err.message || '网络请求失败'
    const wrapped = new Error(detail)
    wrapped.status = status
    return Promise.reject(wrapped)
  }
)

export default api
