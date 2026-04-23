export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'juggfinder.theme'

export function getStoredTheme(): Theme | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (raw === 'light' || raw === 'dark') return raw
  return null
}

export function setStoredTheme(theme: Theme) {
  localStorage.setItem(STORAGE_KEY, theme)
  applyTheme(theme)
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
}

export function initTheme() {
  const stored = getStoredTheme()
  if (stored) return applyTheme(stored)
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)')?.matches
  applyTheme(prefersDark ? 'dark' : 'light')
}

export function toggleTheme() {
  const currentlyDark = document.documentElement.classList.contains('dark')
  const next: Theme = currentlyDark ? 'light' : 'dark'
  setStoredTheme(next)
  return next
}

