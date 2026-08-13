import { describe, expect, it } from 'vitest'
import { resolveInitialTheme } from './theme'

describe('resolveInitialTheme', () => {
  it('uses the stored theme when present, regardless of OS preference', () => {
    expect(resolveInitialTheme('light', false)).toBe('light')
    expect(resolveInitialTheme('dark', true)).toBe('dark')
  })

  it('falls back to OS preference when nothing is stored', () => {
    expect(resolveInitialTheme(null, true)).toBe('light')
    expect(resolveInitialTheme(null, false)).toBe('dark')
  })

  it('falls back to OS preference for an invalid/unrecognized stored value', () => {
    expect(resolveInitialTheme('sepia', true)).toBe('light')
    expect(resolveInitialTheme('', false)).toBe('dark')
  })
})
