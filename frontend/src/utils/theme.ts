/** Manual light/dark toggle, layered on top of the existing `prefers-color-scheme`
 * support in index.css — an explicit user choice (persisted here) always wins over the OS
 * setting; absent a stored choice, the OS setting still governs (see the anti-flash inline
 * script in index.html and the `@media (prefers-color-scheme: light)` block in index.css).
 */

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'theme'

function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark'
}

/** Pure — no DOM/storage access, so it's trivially testable. `stored` is whatever
 * `readStoredTheme()` returned; `prefersLight` is `matchMedia('(prefers-color-scheme:
 * light)').matches`.
 */
export function resolveInitialTheme(stored: string | null, prefersLight: boolean): Theme {
  if (isTheme(stored)) return stored
  return prefersLight ? 'light' : 'dark'
}

export function readStoredTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return isTheme(value) ? value : null
  } catch {
    // Storage disabled (e.g. private browsing) — just means no persisted choice.
    return null
  }
}

export function storeTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Nothing to do if storage isn't available — the toggle still works for this load.
  }
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme)
}
