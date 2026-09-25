export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'verifact-theme'

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system'
}

export function readStoredTheme(): ThemePreference {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)
    if (isThemePreference(raw)) return raw
  } catch {
    /* ignore */
  }
  return 'system'
}

export function writeStoredTheme(preference: ThemePreference) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    /* ignore */
  }
}

export function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference === 'system' ? getSystemTheme() : preference
}

export function applyTheme(preference: ThemePreference) {
  const resolved = resolveTheme(preference)
  const root = document.documentElement
  root.setAttribute('data-theme', resolved)
  root.setAttribute('data-theme-preference', preference)
  root.style.colorScheme = resolved
}
