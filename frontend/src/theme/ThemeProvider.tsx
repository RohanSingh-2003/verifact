import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  applyTheme,
  readStoredTheme,
  writeStoredTheme,
  type ResolvedTheme,
  type ThemePreference,
  resolveTheme,
} from '../lib/theme'

interface ThemeContextValue {
  preference: ThemePreference
  resolved: ResolvedTheme
  setPreference: (preference: ThemePreference) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => readStoredTheme())
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(readStoredTheme()))

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next)
    writeStoredTheme(next)
    applyTheme(next)
    setResolved(resolveTheme(next))
  }, [])

  useEffect(() => {
    applyTheme(preference)
    setResolved(resolveTheme(preference))
  }, [preference])

  useEffect(() => {
    if (preference !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      applyTheme('system')
      setResolved(resolveTheme('system'))
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [preference])

  const value = useMemo(
    () => ({ preference, resolved, setPreference }),
    [preference, resolved, setPreference],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return ctx
}
