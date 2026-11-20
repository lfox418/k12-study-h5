/**
 * Web Audio API 零依赖合成音效模块
 * - playSuccessChime: 清脆多音阶升级/通关音效
 * - playPenaltyTone: 轻快温和的扣分提示音
 * - speakWord: 浏览器原生 speechSynthesis 英语发音
 */

let audioCtx = null

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
    ? [523.25, 659.25, 783.99, 1046.5, 1318.5] // C5-E5-G5-C6-E6 华丽通关音阶
    : [587.33, 739.99, 880.0] // D5-F#5-A5 清脆加分三和弦

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

export function speakWord(text) {
  const clean = (text || '').trim()
  if (!clean || typeof window === 'undefined') return

  try {
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }
    const apiBase = import.meta.env.VITE_API_BASE || '/api'
    const url = `${apiBase}/tts?word=${encodeURIComponent(clean)}`
    const audio = new Audio(url)
    currentAudio = audio
    const playPromise = audio.play()
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch((err) => {
        console.warn('Audio play failed:', err)
        alert(err.message)
        fallbackSpeechSynthesis(clean)
      })
    }
    audio.onerror = () => fallbackSpeechSynthesis(clean)
  } catch {
    fallbackSpeechSynthesis(clean)
  }
}