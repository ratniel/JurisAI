import { useEffect, useState } from 'react'

export type ThemeName = 'dark' | 'light'

const STORAGE_KEY = 'jurisai-theme'

function resolveInitialTheme(): ThemeName {
  if (typeof document === 'undefined') {
    return 'dark'
  }

  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') {
    return stored
  }

  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}

export function useTheme() {
  const [theme, setTheme] = useState<ThemeName>(resolveInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  return {
    theme,
    isDark: theme === 'dark',
    toggleTheme() {
      setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
    },
  }
}
