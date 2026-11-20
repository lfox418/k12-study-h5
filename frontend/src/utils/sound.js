import { reactive } from 'vue'
export const ttsState = reactive({
  loadingText: '',
  playingText: ''
})
let audioCtx = null
let currentAudio = null



function getAudioContext() {
  if (typeof window === 'undefined') return null
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return null
  if (!audioCtx) {
    audioCtx = new Ctx()
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
  return audioCtx
}

export function playSuccessChime(isGrandPass = false) {
  const ctx = getAudioContext()
  if (!ctx) return

  const notes = isGrandPass
    ? [523.25, 659.25, 783.99, 1046.5, 1318.5]
    : [587.33, 739.99, 880.0]

  const now = ctx.currentTime
  notes.forEach((freq, idx) => {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'triangle'
    osc.frequency.setValueAtTime(freq, now + idx * 0.08)

    gain.gain.setValueAtTime(0.001, now + idx * 0.08)
    gain.gain.exponentialRampToValueAtTime(0.18, now + idx * 0.08 + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.28)

    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start(now + idx * 0.08)
    osc.stop(now + idx * 0.08 + 0.3)
  })
}

export function playPenaltyTone() {
  const ctx = getAudioContext()
  if (!ctx) return

  const now = ctx.currentTime
  const freqs = [330, 261.63]
  freqs.forEach((freq, idx) => {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, now + idx * 0.1)

    gain.gain.setValueAtTime(0.001, now + idx * 0.1)
    gain.gain.exponentialRampToValueAtTime(0.14, now + idx * 0.1 + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.1 + 0.22)

    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start(now + idx * 0.1)
    osc.stop(now + idx * 0.1 + 0.24)
  })
}

function fallbackSpeechSynthesis(text) {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
  try {
    window.speechSynthesis.cancel()
    const utter = new SpeechSynthesisUtterance(text)
    utter.lang = 'en-US'
    utter.rate = 0.92
    window.speechSynthesis.speak(utter)
  } catch {
    // 忽略浏览器发音权限限制
  }
}

export function speakWord(text) {
  const clean = (text || '').trim()
  if (!clean || typeof window === 'undefined') return

  // 正在加载中时直接忽略连续点击
  if (ttsState.loadingText) return

  try {
    if (currentAudio) {
      currentAudio.onended = null
      currentAudio.onerror = null
      currentAudio.pause()
      currentAudio = null
    }

    ttsState.loadingText = clean
    ttsState.playingText = ''

    const apiBase = import.meta.env.VITE_API_BASE || '/api'
    const url = `${apiBase}/tts?word=${encodeURIComponent(clean)}`
    const audio = new Audio(url)
    currentAudio = audio

    audio.onplaying = () => {
      ttsState.loadingText = ''
      ttsState.playingText = clean
    }
    audio.onended = () => {
      ttsState.loadingText = ''
      ttsState.playingText = ''
    }
    audio.onerror = () => {
      ttsState.loadingText = ''
      ttsState.playingText = ''
      fallbackSpeechSynthesis(clean)
    }

    const playPromise = audio.play()
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch((err) => {
        ttsState.loadingText = ''
        ttsState.playingText = ''
        if (err?.name !== 'AbortError') {
          fallbackSpeechSynthesis(clean)
        }
      })
    }
  } catch {
    ttsState.loadingText = ''
    ttsState.playingText = ''
    fallbackSpeechSynthesis(clean)
  }
}

