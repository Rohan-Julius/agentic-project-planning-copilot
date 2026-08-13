import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { applyTheme, readStoredTheme, resolveInitialTheme, storeTheme, type Theme } from '../utils/theme'

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() =>
    resolveInitialTheme(readStoredTheme(), window.matchMedia('(prefers-color-scheme: light)').matches),
  )

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    // Only follow OS changes live if the user hasn't made an explicit choice yet — once
    // they toggle, that choice is the source of truth until they toggle again.
    if (readStoredTheme()) return
    const media = window.matchMedia('(prefers-color-scheme: light)')
    function handleChange(event: MediaQueryListEvent) {
      setTheme(event.matches ? 'light' : 'dark')
    }
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    storeTheme(next)
  }

  const label = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'

  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-label={label} title={label}>
      {theme === 'dark' ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </button>
  )
}
