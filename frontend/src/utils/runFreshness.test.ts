import { describe, expect, it } from 'vitest'
import { STALE_EVENT_THRESHOLD_MS, isEventLive } from './runFreshness'

describe('isEventLive', () => {
  const now = new Date('2026-08-07T12:00:00Z').getTime()

  it('treats a just-logged event as live', () => {
    expect(isEventLive('2026-08-07T11:59:58Z', now)).toBe(true)
  })

  it('treats an event right at the threshold boundary as no longer live', () => {
    const exactlyAtThreshold = new Date(now - STALE_EVENT_THRESHOLD_MS).toISOString()
    expect(isEventLive(exactlyAtThreshold, now)).toBe(false)
  })

  it('treats an event just under the threshold as still live', () => {
    const justUnder = new Date(now - STALE_EVENT_THRESHOLD_MS + 1000).toISOString()
    expect(isEventLive(justUnder, now)).toBe(true)
  })

  it('treats an event from hours ago as not live — the actual bug this fixes', () => {
    expect(isEventLive('2026-08-05T22:33:45Z', now)).toBe(false)
  })

  it('treats an unparseable timestamp as not live rather than assuming it is', () => {
    expect(isEventLive('not-a-date', now)).toBe(false)
  })

  it('respects a custom threshold', () => {
    const tenSecondsAgo = new Date(now - 10_000).toISOString()
    expect(isEventLive(tenSecondsAgo, now, 5_000)).toBe(false)
    expect(isEventLive(tenSecondsAgo, now, 15_000)).toBe(true)
  })
})
